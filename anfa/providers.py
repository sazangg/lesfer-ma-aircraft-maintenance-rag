"""Interfaces for the model-backed parts of the system.

The pipeline only depends on these protocols; anfa.real implements them on OpenRouter. Another
provider, or a local model, plugs in by implementing the same methods.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Embedder(Protocol):
    """Retrieval embedding models embed a question and a passage differently, so the two are
    separate calls."""

    def embed_query(self, text: str) -> list[float]: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class Generator(Protocol):
    def generate(self, prompt: str) -> str: ...


class Reranker(Protocol):
    """Reads the question with each candidate passage and scores how well the passage answers it."""

    def score(self, question: str, passages: list[str]) -> list[float]: ...


class Describer(Protocol):
    """A vision model that turns a figure into text: what it shows, and the values printed in it.
    None means it produced no usable description."""

    def describe(self, image: Path, caption: str, document: str) -> str | None: ...
