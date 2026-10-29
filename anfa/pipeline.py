"""The assistant: prepare documents once, then answer questions.

Part 1 (naive RAG):

    Preparing:  parsed documents -> plain text -> size-based chunks -> embeddings -> vector index
    Answering:  question -> embedding -> top-k chunks -> prompt -> model -> answer

Preparing is a separate step (`python -m anfa ingest`): embedding the collection costs calls and
time, so it runs once and the index lives in Postgres.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from anfa.chunking import Chunk, size_based_chunks
from anfa.corpus import ParsedDocument
from anfa.extract import plain_text_sections
from anfa.real import OpenRouterEmbedder, OpenRouterGenerator
from anfa.store import PgVectorIndex

INSTRUCTIONS = """Answer the question using the supplied passages.
Identify the source of your answer.
If the passages don't establish an answer, say so."""

# About 200 words: long enough to hold a paragraph of a directive, short enough to search.
CHUNK_CHARS = 1200


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

    # Preparing the documents ------------------------------------------------

    def chunks(self, documents: list[ParsedDocument]) -> list[Chunk]:
        return [chunk for doc in documents
                for chunk in size_based_chunks(doc.source_id, doc.meta, plain_text_sections(doc), CHUNK_CHARS)]

    def ingest(self, documents: list[ParsedDocument]) -> int:
        """Embed and store every chunk. Skipped when the index already holds exactly these chunks."""
        chunks = self.chunks(documents)
        fingerprint = hashlib.sha256(
            "\n".join([self.embedder.model, str(self.embedder.dimensions)]
                      + [f"{c.id}\t{c.text}" for c in chunks]).encode()
        ).hexdigest()
        if self.index.fingerprint() == fingerprint:
            return 0
        self.index.reset(fingerprint)
        self.index.add(chunks, self.embedder.embed_documents([c.text for c in chunks]))
        return len(chunks)

    # Answering a question ---------------------------------------------------

    def ask(self, question: str, user: User = MECHANIC) -> Trace:
        trace = Trace(question)

        # Access is enforced before any passage can reach the prompt.
        hits = self.index.search(self.embedder.embed_query(question), user.groups, self.k)
        trace.retrieved = [(chunk.id, round(score, 3)) for score, chunk in hits]
        trace.context = [chunk for _, chunk in hits]

        trace.prompt = build_prompt(INSTRUCTIONS, question, trace.context)
        trace.answer = self.generator.generate(trace.prompt)
        return trace


def build_prompt(instructions: str, question: str, context: list[Chunk]) -> str:
    sources = "\n\n".join(f"Source: {c.source_id}, section {c.section}\n{c.text}" for c in context)
    return f"{instructions}\n\nQuestion:\n{question}\n\n{sources}"
