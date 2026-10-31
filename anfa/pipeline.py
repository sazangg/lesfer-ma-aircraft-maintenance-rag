"""The assistant: prepare documents once, then answer questions.

Part 3 (document preparation) and Part 4 (evidence units): each kind of content gets a searched
form and a supplied form.

    Preparing:  parsed documents -> structured documents (+ ingestion report)
                -> searchable pieces (embedded) + blocks (stored) -> Postgres
    Answering:  question -> embedding -> top-k pieces -> the block each belongs to, once
                -> prompt -> model -> answer

Part 5 replaces the single vector search with a retrieval stage (anfa/retrieval.py):

    AD number lookup  ┐
    keyword (BM25)    ├─> reciprocal rank fusion -> rerank -> top-k
    vector search     ┘

Part 6 makes the evidence apply to the aircraft asked about (anfa/situation.py):

    question -> situation (aircraft, model), read and checked by code
             -> every search filtered to pieces that apply to it
             -> "our 172S", several match, evidence differs per aircraft? -> ask which, stop
             -> blocks labelled [S1], [S2] ... -> model
             -> code checks each label and turns it into a source reference

Preparing is a separate step (`python -m anfa ingest`): embedding the collection costs calls and
time, so it runs once and the index lives in Postgres.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from anfa.chunking import Chunk
from anfa.convert import IngestReport, StructuredDocument, convert, load_corrections
from anfa.corpus import ParsedDocument
from anfa.evidence import evidence_units
from anfa.real import OpenRouterDescriber, OpenRouterEmbedder, OpenRouterGenerator, OpenRouterReranker
from anfa.retrieval import ad_numbers, reciprocal_rank_fusion
from anfa.situation import Situation, fleet_from, situation_from, which_aircraft
from anfa.store import SCHEMA, TERMS, PgVectorIndex

# Pieces of a directive named in the question that the reranker reads (nearest to the question first).
LOOKUP = 20

INSTRUCTIONS = """Answer the question using the supplied sources.
Cite the source label, for example [S1], beside each claim it supports.
If the sources don't establish an answer, say so."""


@dataclass
class User:
    name: str
    groups: set[str]


MECHANIC = User("mechanic", {"employees", "staff"})


@dataclass
class Trace:
    """Everything that happened for one question. Later parts check these fields."""

    question: str
    situation: Situation = field(default_factory=Situation)
    retrieved: list[tuple[str, float]] = field(default_factory=list)
    context: list[Chunk] = field(default_factory=list)
    citations: dict[str, str] = field(default_factory=dict)
    prompt: str = ""
    raw_answer: str = ""
    answer: str = ""
    status: str = "answered"


class Assistant:
    def __init__(self, k: int = 5, candidates: int = 10, min_score: float = 0.0):
        self.k = k  # pieces supplied to the model (before expanding to blocks)
        self.candidates = candidates  # pieces each search contributes to the shortlist
        self.min_score = min_score  # Part 7: a reranked piece scoring below this is not supplied
        self.reranker = OpenRouterReranker()
        self.embedder, self.generator, self.index = OpenRouterEmbedder(), OpenRouterGenerator(), PgVectorIndex()
        self.describer = OpenRouterDescriber()
        self.reports: list[IngestReport] = []

    # Preparing the documents ------------------------------------------------

    def convert(self, documents: list[ParsedDocument], corrections: dict | None = None) -> list[StructuredDocument]:
        corrections = load_corrections() if corrections is None else corrections
        converted = [convert(doc, self.describer, corrections) for doc in documents]
        self.reports = [doc.report for doc in converted]
        return converted

    def units(self, documents: list[ParsedDocument]) -> tuple[list[Chunk], list[Chunk]]:
        return _units(self.convert(documents))

    def ingest(self, documents: list[ParsedDocument]) -> int:
        """Embed and store every searched piece, and store the blocks and the fleet. Skipped when
        the index already holds exactly these."""
        converted = self.convert(documents)
        searchable, blocks = _units(converted)
        fleet = fleet_from(converted)
        fingerprint = hashlib.sha256(
            # The schema is part of it: an index built by an earlier checkpoint lacks newer columns.
            "\n".join([SCHEMA, TERMS, self.embedder.model, str(self.embedder.dimensions)]
                      + [f"{c.id}\t{c.parent_id}\t{c.search_text}\t{sorted(c.meta.items())}" for c in searchable]
                      + [f"{b.id}\t{b.text}" for b in blocks] + [str(a) for a in fleet]).encode()
        ).hexdigest()
        if self.index.fingerprint() == fingerprint:
            return 0
        self.index.reset(fingerprint)
        self.index.add(searchable, self.embedder.embed_documents([c.search_text or c.text for c in searchable]))
        self.index.add_blocks(blocks)
        self.index.add_fleet(fleet)
        return len(searchable)

    # Answering a question ---------------------------------------------------

    def ask(self, question: str, user: User = MECHANIC) -> Trace:
        trace = self.prepare(question, user)
        if trace.status != "answered":
            return trace
        trace.raw_answer = self.generator.generate(trace.prompt)
        trace.answer, unknown = resolve_citations(trace.raw_answer, trace.citations)
        if unknown:
            trace.status = "format_error"
            trace.answer = f"The answer cited sources that weren't supplied ({', '.join(unknown)}) and was withheld."
        return trace

    def prepare(self, question: str, user: User = MECHANIC) -> Trace:
        """Everything up to the prompt: what the model would receive. Measuring retrieval stops here."""
        trace = Trace(question)
        trace.situation = situation_from(question, self.index.fleet(), self.index.models())

        hits = self.retrieve(question, user, trace.situation)
        trace.retrieved = [(chunk.id, round(score, 3)) for score, chunk in hits]

        if choices := which_aircraft(trace.situation, [chunk for _, chunk in hits]):
            trace.status = "needs_details"
            trace.answer = ("Which aircraft is this about? The evidence differs from one aircraft to the next, "
                            "and these match: " + ", ".join(f"{a.registration} (S/N {a.serial})" for a in choices) + ".")
            return trace

        trace.context = self.supplied_blocks([chunk for _, chunk in hits], user)
        trace.citations = {f"S{n}": block.ref for n, block in enumerate(trace.context, start=1)}
        trace.prompt = build_prompt(INSTRUCTIONS, question, trace.situation, trace.context)
        return trace

    def retrieve(self, question: str, user: User, situation: Situation | None = None) -> list[tuple[float, Chunk]]:
        """The top-k pieces for the question. Access and the situation filter every search."""
        groups, vector = user.groups, self.embedder.embed_query(question)

        # An AD number in the question: that directive's pieces join the shortlist, and its two best
        # come first. The reranker picks them: every piece of a directive looks alike to vector search,
        # which ranked AD 2012-22-01's applicability 13th of 35 (Part 7).
        codes = ad_numbers(question)
        named = [c for _, c in self.index.search(vector, groups, LOOKUP, codes, situation)] if codes else []

        lexical = [c for _, c in self.index.keyword_search(question, groups, self.candidates, situation)]
        dense = [c for _, c in self.index.search(vector, groups, self.candidates, situation=situation)]
        shortlist = named + [c for c in reciprocal_rank_fusion(lexical, dense) if c.id not in {n.id for n in named}]

        scores = self.reranker.score(question, [c.search_text or c.text for c in shortlist])
        ranked = sorted(zip(scores, shortlist), key=lambda pair: (-pair[0], pair[1].id))
        first = [(score, c) for score, c in ranked if c in named][:2]
        rest = [(score, c) for score, c in ranked if (score, c) not in first and score >= self.min_score]
        return (first + rest)[: self.k]

    def supplied_blocks(self, hits: list[Chunk], user: User) -> list[Chunk]:
        """Replace each searched piece by the block it belongs to, once."""
        blocks = self.index.blocks([c.parent_id for c in hits if c.parent_id], user.groups)
        context: list[Chunk] = []
        for chunk in hits:
            block = blocks.get(chunk.parent_id, chunk)
            if block.id not in {c.id for c in context}:
                context.append(block)
        return context


def _units(documents: list[StructuredDocument]) -> tuple[list[Chunk], list[Chunk]]:
    searchable: list[Chunk] = []
    blocks: list[Chunk] = []
    for doc in documents:
        pieces, doc_blocks = evidence_units(doc)
        searchable += pieces
        blocks += doc_blocks
    return searchable, blocks


def build_prompt(instructions: str, question: str, situation: Situation, context: list[Chunk]) -> str:
    known = f"{situation.facts()}\n\n" if situation.facts() else ""
    sources = "\n\n".join(f"[S{n}] {_name(c.ref)}\n{c.text}" for n, c in enumerate(context, start=1))
    return f"{instructions}\n\nQuestion:\n{question}\n\n{known}{sources}"


def resolve_citations(answer: str, citations: dict[str, str]) -> tuple[str, list[str]]:
    """Turn [S1] into the source it labels. The model picks a label; code supplies the reference."""
    labels = [label for group in LABELS.findall(answer) for label in re.findall(r"S\d+", group)]
    unknown = sorted({label for label in labels if label not in citations}, key=lambda x: int(x[1:]))

    def name(match: re.Match) -> str:
        found = re.findall(r"S\d+", match.group(1))
        if any(label not in citations for label in found):
            return match.group(0)
        return "[" + "; ".join(_name(citations[label]) for label in found) + "]"

    return LABELS.sub(name, answer), unknown


# "[S1]", several in one bracket ("[S1, S3]"), or in parentheses: the model was asked for the
# first and writes all three.
LABELS = re.compile(r"[\[(](S\d+(?:\s*(?:[,;]|and)\s*S\d+)*)[\])]")


def _name(ref: str) -> str:
    source_id, section = ref.split("#", 1)
    return f"{source_id}, section {section}" if section else source_id
