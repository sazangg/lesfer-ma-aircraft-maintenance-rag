"""The assistant: prepare documents once, then answer questions.

Part 3 (document preparation) and Part 4 (evidence units): each kind of content gets a searched
form and a supplied form.

    Preparing:  parsed documents -> structured documents (+ ingestion report)
                -> searchable pieces (embedded) + blocks (stored) -> Postgres
    Answering:  question -> embedding -> top-k pieces -> the block each belongs to, once
                -> prompt -> model -> answer

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
from anfa.real import OpenRouterDescriber, OpenRouterEmbedder, OpenRouterGenerator
from anfa.store import PgVectorIndex

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
    def __init__(self, k: int = 5):
        self.k = k
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
            "\n".join([self.embedder.model, str(self.embedder.dimensions)]
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

        # Access is enforced before any passage can reach the prompt.
        hits = self.index.search(self.embedder.embed_query(question), user.groups, self.k)
        trace.retrieved = [(chunk.id, round(score, 3)) for score, chunk in hits]
        trace.context = self.supplied_blocks([chunk for _, chunk in hits], user)

        trace.prompt = build_prompt(INSTRUCTIONS, question, trace.context)
        trace.answer = self.generator.generate(trace.prompt)
        return trace

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
