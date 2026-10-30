"""Calls to the models on OpenRouter, with recorded responses.

Every request goes through `call()`, which runs in one of three modes (ANFA_MODE):

    replay  answer from fixtures/: no key, no cost, the same result every time
    live    call the model
    record  replay what is recorded; call the model for the rest and save its responses

A fixture is keyed by the request itself (model, input, settings), so a changed prompt or a
changed model misses its fixture instead of replaying an answer to a different question.
Embedding vectors are stored as base64 float32, the same numbers in a quarter of the space. An
image sent to a vision model is stored as its hash: the image itself is in corpus/figures/.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time

import numpy as np

from anfa.config import ROOT, SETTINGS

FIXTURES = ROOT / "fixtures"
MIN_INTERVAL = 3.2  # seconds between requests: OpenRouter allows 20 a minute to free models
_last_request = 0.0


class MissingFixture(RuntimeError):
    pass


class PaidModel(RuntimeError):
    pass


def _client():
    from openai import OpenAI

    if not SETTINGS.api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set: add it to .env, or use ANFA_MODE=replay.")
    return OpenAI(api_key=SETTINGS.api_key, base_url=SETTINGS.base_url)


def call(kind: str, request: dict) -> dict:
    """Run one request (kind 'embeddings', 'chat', or 'rerank') and return the response as a plain dict."""
    key = hashlib.sha256(json.dumps({"kind": kind, **request}, sort_keys=True).encode()).hexdigest()[:24]
    path = FIXTURES / kind / f"{key}.json"
    # Record mode records only what is missing: free accounts have a daily request limit.
    if SETTINGS.mode == "replay" or (SETTINGS.mode == "record" and path.exists()):
        if not path.exists():
            raise MissingFixture(f"No recorded response for this {kind} request ({path.name}). "
                                 "Run with ANFA_MODE=record (needs a key) to record it.")
        return _unpack(json.loads(path.read_text(encoding="utf-8"))["response"])

    # This project runs on free models only. A paid model would draw on the account's credits, so it is never called.
    if not str(request.get("model", "")).endswith(":free"):
        raise PaidModel(f"{request.get('model')} is not a free model (no ':free' suffix); refusing to send the request.")
    response = _pack(_with_retries(kind, request))
    if SETTINGS.mode == "record":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((json.dumps({"request": _without_images(request), "response": response}, indent=1) + "\n").encode("utf-8"))
    return _unpack(response)  # live and record see exactly the numbers that replay will


def _without_images(request: dict) -> dict:
    def strip(value):
        if isinstance(value, str) and value.startswith("data:image/"):
            return f"<image sha256:{hashlib.sha256(value.encode()).hexdigest()[:24]}>"
        if isinstance(value, dict):
            return {k: strip(v) for k, v in value.items()}
        if isinstance(value, list):
            return [strip(v) for v in value]
        return value

    return strip(request)


def _pack(response: dict) -> dict:
    data = [{**d, "embedding": base64.b64encode(np.asarray(d["embedding"], dtype="<f4").tobytes()).decode()}
            if isinstance(d.get("embedding"), list) else d for d in response.get("data") or []]
    return {**response, "data": data} if data else response


def _unpack(response: dict) -> dict:
    data = [{**d, "embedding": np.frombuffer(base64.b64decode(d["embedding"]), dtype="<f4").tolist()}
            if isinstance(d.get("embedding"), str) else d for d in response.get("data") or []]
    return {**response, "data": data} if data else response


def _rerank(request: dict) -> dict:
    # The OpenAI client has no rerank call; OpenRouter's endpoint takes a plain JSON POST.
    import urllib.request

    req = urllib.request.Request(
        f"{SETTINGS.base_url}/rerank", data=json.dumps(request).encode(),
        headers={"Authorization": f"Bearer {SETTINGS.api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as reply:
        response = json.load(reply)
    if not response.get("results"):
        raise RuntimeError(f"no results in rerank response: {response.get('error')}")
    return response


def _with_retries(kind: str, request: dict, attempts: int = 5) -> dict:
    # Free endpoints fail now and then (502s, rate limits). A real system paces its requests and retries with backoff.
    global _last_request
    client = _client()
    for attempt in range(attempts):
        time.sleep(max(0.0, _last_request + MIN_INTERVAL - time.monotonic()))
        _last_request = time.monotonic()
        try:
            if kind == "rerank":
                return _rerank(request)
            if kind == "embeddings":
                response = client.embeddings.create(**request).model_dump()
                if not response.get("data"):
                    raise RuntimeError(f"empty embeddings response: {response.get('error')}")
                return response
            response = client.chat.completions.create(**request).model_dump()
            # A provider error can come back as a normal response with no choices: it is a failure, not an answer.
            if not response.get("choices") or not response["choices"][0]["message"].get("content"):
                raise RuntimeError(f"no answer in chat response: {response.get('error')}")
            return response
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(5 * 2 ** attempt)
    raise AssertionError("unreachable")
