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

Preparing is a separate step (`python -m anfa ingest`): embedding the collection costs calls and
time, so it runs once and the index lives in Postgres.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from anfa.chunking import Chunk
from anfa.convert import IngestReport, StructuredDocument, convert, load_corrections
from anfa.corpus import ParsedDocument
from anfa.evidence import evidence_units
from anfa.real import OpenRouterDescriber, OpenRouterEmbedder, OpenRouterGenerator, OpenRouterReranker
from anfa.retrieval import ad_numbers, reciprocal_rank_fusion
from anfa.store import SCHEMA, TERMS, PgVectorIndex

INSTRUCTIONS = """Answer the question using the supplied passages.
Identify the source of your answer.
If the passages don't establish an answer, say so."""


@dataclass
class User:
    name: str
    groups: set[str]


MECHANIC = User("mechanic", {"employees", "staff"})


@dataclass
class Trace:
    """Everything that happened for one question. Later parts check these fields."""

    question: str
    retrieved: list[tuple[str, float]] = field(default_factory=list)
    context: list[Chunk] = field(default_factory=list)
    prompt: str = ""
    answer: str = ""
    status: str = "answered"


class Assistant:
    def __init__(self, k: int = 5, candidates: int = 10):
        self.k = k  # pieces supplied to the model (before expanding to blocks)
        self.candidates = candidates  # pieces each search contributes to the shortlist
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
        searchable: list[Chunk] = []
        blocks: list[Chunk] = []
        for doc in self.convert(documents):
            pieces, doc_blocks = evidence_units(doc)
            searchable += pieces
            blocks += doc_blocks
        return searchable, blocks

    def ingest(self, documents: list[ParsedDocument]) -> int:
        """Embed and store every searched piece, and store the blocks. Skipped when the index
        already holds exactly these."""
        searchable, blocks = self.units(documents)
        fingerprint = hashlib.sha256(
            # The schema is part of it: an index built by an earlier checkpoint lacks newer columns.
            "\n".join([SCHEMA, TERMS, self.embedder.model, str(self.embedder.dimensions)]
                      + [f"{c.id}\t{c.parent_id}\t{c.search_text}" for c in searchable]
                      + [f"{b.id}\t{b.text}" for b in blocks]).encode()
        ).hexdigest()
        if self.index.fingerprint() == fingerprint:
            return 0
        self.index.reset(fingerprint)
        self.index.add(searchable, self.embedder.embed_documents([c.search_text or c.text for c in searchable]))
        self.index.add_blocks(blocks)
        return len(searchable)

    # Answering a question ---------------------------------------------------

    def ask(self, question: str, user: User = MECHANIC) -> Trace:
        trace = Trace(question)

        hits = self.retrieve(question, user)
        trace.retrieved = [(chunk.id, round(score, 3)) for score, chunk in hits]
        trace.context = self.supplied_blocks([chunk for _, chunk in hits], user)

        trace.prompt = build_prompt(INSTRUCTIONS, question, trace.context)
        trace.answer = self.generator.generate(trace.prompt)
        return trace

    def retrieve(self, question: str, user: User) -> list[tuple[float, Chunk]]:
        """The top-k pieces for the question. Access is enforced inside every search."""
        groups, vector = user.groups, self.embedder.embed_query(question)

        # An AD number in the question: that directive's own pieces come first, best match first.
        exact = [c for _, c in self.index.search(vector, groups, 2, ad_numbers(question))] if ad_numbers(question) else []

        lexical = [c for _, c in self.index.keyword_search(question, groups, self.candidates)]
        dense = [c for _, c in self.index.search(vector, groups, self.candidates)]
        shortlist = [c for c in reciprocal_rank_fusion(lexical, dense) if c.id not in {e.id for e in exact}]

        scores = self.reranker.score(question, [c.search_text or c.text for c in shortlist])
        ranked = sorted(zip(scores, shortlist), key=lambda pair: (-pair[0], pair[1].id))
        return ([(float("inf"), c) for c in exact] + ranked)[: self.k]

    def supplied_blocks(self, hits: list[Chunk], user: User) -> list[Chunk]:
        """Replace each searched piece by the block it belongs to, once."""
        blocks = self.index.blocks([c.parent_id for c in hits if c.parent_id], user.groups)
        context: list[Chunk] = []
        for chunk in hits:
            block = blocks.get(chunk.parent_id, chunk)
            if block.id not in {c.id for c in context}:
                context.append(block)
        return context


def build_prompt(instructions: str, question: str, context: list[Chunk]) -> str:
    sources = "\n\n".join(f"Source: {c.source_id}, section {c.section}\n{c.text}" for c in context)
    return f"{instructions}\n\nQuestion:\n{question}\n\n{sources}"
