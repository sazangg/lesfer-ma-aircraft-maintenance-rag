"""Part 5: finding the evidence when one search misses it.

    AD number in the question -> that directive's own pieces ----------------------------┐
    question -> keyword search (BM25, 10) ┐                                                ├-> top 5
             -> vector search (10) -------┴-> reciprocal rank fusion -> reranker ----------┘

Vector search finds passages that mean what the question means, and treats "2000-04-01" as one
more number. Keyword search finds the exact terms, and misses a passage that says it differently.
Reciprocal rank fusion merges the two lists by position, because their scores are on different
scales. The reranker then reads the question with each candidate and orders them.
"""

from __future__ import annotations

import re

from anfa.chunking import Chunk

AD_NUMBER = re.compile(r"\b(?:19|20)?\d{2}-\d{2}-\d{2}\b")


def ad_numbers(question: str) -> list[str]:
    return sorted(set(AD_NUMBER.findall(question)))


def reciprocal_rank_fusion(*rankings: list[Chunk], k: int = 60) -> list[Chunk]:
    """Each list gives a chunk 1 / (k + rank); chunks are ordered by their total."""
    scores: dict[str, float] = {}
    chunks: dict[str, Chunk] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1 / (k + rank)
            chunks[chunk.id] = chunk
    return [chunks[i] for i in sorted(scores, key=lambda i: (-scores[i], i))]
