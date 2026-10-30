"""Real model-backed providers: the embedding, language, vision, and reranking models, on OpenRouter.

They implement the interfaces in anfa/providers.py.
"""

from __future__ import annotations

import base64
from pathlib import Path

from anfa.config import SETTINGS
from anfa.models import call


class OpenRouterEmbedder:
    """Retrieval embedding models embed questions and passages differently.

    Nemotron takes an `input_type`; without one, a text is embedded as a query. Embedding the
    documents that way gives no error, only worse search, so both sides are always explicit.

    Texts go 100 to a request: a free OpenRouter account allows 50 requests a day to free models.
    """

    def __init__(self, model: str = SETTINGS.embed_model, dimensions: int = SETTINGS.embed_dimensions,
                 batch: int = 100):
        self.model, self.dimensions, self.batch = model, dimensions, batch

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch):
            response = call("embeddings", {
                "model": self.model, "input": texts[start:start + self.batch],
                "dimensions": self.dimensions, "extra_body": {"input_type": input_type},
            })
            vectors += [item["embedding"] for item in sorted(response["data"], key=lambda d: d["index"])]
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query")[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "passage")


class OpenRouterGenerator:
    # The model reasons before it answers, and its reasoning counts against max_tokens: at 1,500 a long
    # list answer was cut off mid-sentence.
    def __init__(self, model: str = SETTINGS.chat_model, max_tokens: int = 4000):
        self.model, self.max_tokens = model, max_tokens

    def generate(self, prompt: str) -> str:
        response = call("chat", {
            "model": self.model, "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens, "temperature": 0,
        })
        choice = response["choices"][0]
        # A description that ran to the token limit is a loop ("81 IN. CABLE, 81-1/4 IN. CABLE, ..."),
        # not a transcription: 9 of 170 figures. None tells the converter to ask a person.
        if choice["finish_reason"] == "length":
            return None
        return (choice["message"].get("content") or "").strip()


DESCRIBE = """This figure is from {document}.{caption}
Describe it for a mechanic who can't see it: say what it shows, then transcribe every label,
value, unit, part number, and note printed in it. Don't add anything that isn't in the figure.
If it shows nothing of use (a logo, a signature, a blank area), say so in one sentence."""


class OpenRouterDescriber:
    """Describes a figure with a vision model, so what it shows can be searched and quoted."""

    def __init__(self, model: str = SETTINGS.vision_model, max_tokens: int = 4000):
        self.model, self.max_tokens = model, max_tokens

    def describe(self, image: Path, caption: str, document: str) -> str | None:
        data = base64.b64encode(image.read_bytes()).decode()
        prompt = DESCRIBE.format(document=document, caption=f' Its caption: "{caption}".' if caption else "")
        # Transcribing a figure needs no reasoning. With it on, the model sometimes spent all 4,000
        # tokens thinking and returned no description; with it off, a figure takes seconds.
        response = call("chat", {
            "model": self.model, "max_tokens": self.max_tokens, "temperature": 0,
            "extra_body": {"reasoning": {"enabled": False}},
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{data}"}},
            ]}],
        })
        choice = response["choices"][0]
        # A description that ran to the token limit is a loop ("81 IN. CABLE, 81-1/4 IN. CABLE, ..."),
        # not a transcription: 9 of 170 figures. None tells the converter to ask a person.
        if choice["finish_reason"] == "length":
            return None
        return (choice["message"].get("content") or "").strip()


class OpenRouterReranker:
    """Scores each candidate passage against the question, reading the two together."""

    def __init__(self, model: str = SETTINGS.rerank_model):
        self.model = model

    def score(self, question: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        response = call("rerank", {"model": self.model, "query": question, "documents": passages})
        scores = [0.0] * len(passages)
        for result in response["results"]:
            scores[result["index"]] = result["relevance_score"]
        return scores
