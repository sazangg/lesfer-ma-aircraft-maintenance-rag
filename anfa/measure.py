"""Part 7: measure the assistant, not just pass or fail.

The check runner answers "does this case pass?". Measuring asks how well each stage works and
where it is weak:

    hit         did any of the evidence the question needs reach the model?
    recall      how much of that evidence reached it?
    precision   how much of what reached it is that evidence?
    first       the rank of the first block that is
    tokens      roughly what the prompt costs

Then the same numbers by kind of question, so one average can't hide a weak spot; on held-out
questions nobody tuned the system on; and on rewordings of key questions.

What a question needs is written in the case as `relevant`: a source, and phrases that one supplied
block from that source must contain. A source and phrases, not a section number: most directives'
sections have no number, and "the 172S section" is told apart from "the 172R section" by its text.

Retrieval is measured on what the model would receive (`Assistant.prepare`): no answer is
generated, so measuring costs one embedding and one rerank request per question.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from anfa.checks import CASES_FILE, evaluate, norm
from anfa.chunking import Chunk
from anfa.pipeline import Assistant, Trace

HELD_OUT_FILE = CASES_FILE.parent / "held_out.json"


def approx_tokens(text: str) -> int:
    """About four characters per token for English text: a rough rule, not a tokenizer."""
    return max(1, len(text) // 4)


def meets(block: Chunk, need: dict) -> bool:
    # A list of sources: any of them will do (a directive, or the correction that republishes it).
    sources = need["source"] if isinstance(need["source"], list) else [need["source"]]
    return block.source_id in sources and all(norm(t) in norm(block.text) for t in need.get("texts", []))


def _name(need: dict) -> str:
    source = " or ".join(need["source"]) if isinstance(need["source"], list) else need["source"]
    return source + (f" {need['texts']}" if need.get("texts") else "")


@dataclass
class Row:
    case_id: str
    kind: str
    status: str
    hit: float | None
    recall: float | None
    precision: float | None
    first: int | None
    blocks: int
    tokens: int
    missing: list[str]


def retrieval_row(case: dict, trace: Trace) -> Row:
    needs, supplied = case["relevant"], trace.context
    met = [n for n in needs if any(meets(b, n) for b in supplied)]
    useful = [any(meets(b, n) for n in needs) for b in supplied]
    missing = [_name(n) for n in needs if n not in met]
    return Row(case["id"], case.get("kind", "?"), trace.status,
               hit=1.0 if met else 0.0,
               recall=len(met) / len(needs),
               precision=sum(useful) / len(supplied) if supplied else 0.0,
               first=next((i for i, u in enumerate(useful, start=1) if u), None),
               blocks=len(supplied), tokens=approx_tokens(trace.prompt) if trace.prompt else 0, missing=missing)


def measured_cases(path: Path) -> list[dict]:
    """The cases annotated with what they need. A case that should ask back, or must find nothing, has none."""
    return [c for c in json.loads(path.read_text(encoding="utf-8"))["cases"] if c.get("relevant")]


def measure(assistant: Assistant, path: Path) -> list[Row]:
    return [retrieval_row(case, assistant.prepare(case["question"])) for case in measured_cases(path)]


def mean(values: list[float | None]) -> float | None:
    scored = [v for v in values if v is not None]
    return sum(scored) / len(scored) if scored else None


def by_kind(rows: list[Row]) -> dict[str, dict[str, float | None]]:
    kinds: dict[str, list[Row]] = {}
    for row in rows:
        kinds.setdefault(row.kind, []).append(row)
    return {kind: {"questions": len(group), "hit": mean([r.hit for r in group]),
                   "recall": mean([r.recall for r in group]), "precision": mean([r.precision for r in group])}
            for kind, group in sorted(kinds.items())}


def stability(assistant: Assistant, path: Path) -> list[tuple[str, str, bool, str]]:
    """Run each case's own checks on its rewordings. Only evidence and status checks: no answer is generated."""
    results = []
    for case in json.loads(path.read_text(encoding="utf-8"))["cases"]:
        for variant in case.get("variants", []):
            trace = assistant.prepare(variant)
            outcomes = [evaluate(trace, check) for check in case["checks"]]
            results.append((case["id"], variant, all(ok for ok, _ in outcomes), "; ".join(d for _, d in outcomes)))
    return results


def export_ragas(assistant: Assistant, path: Path, out: Path) -> int:
    """One JSON line per question, with the field names Ragas expects. This one generates answers."""
    lines = []
    for case in measured_cases(path):
        trace = assistant.ask(case["question"])
        lines.append(json.dumps({
            "user_input": case["question"],
            "retrieved_contexts": [block.text for block in trace.context],
            "response": trace.answer,
            "reference": case.get("behavior", ""),
        }, ensure_ascii=False))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)
