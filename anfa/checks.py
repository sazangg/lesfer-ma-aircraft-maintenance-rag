"""Run the cases against the current checkpoint.

Each case says which checkpoint should first pass it. The runner reports:

    PASS        the case passes, as expected
    KNOWN GAP   the case fails and a later part is meant to close it
    REGRESSION  the case fails although this checkpoint should pass it
    EARLY PASS  the case passes before the part meant to close it

Known gaps are not failures of the checkpoint. They are the reason for the next article.

Most checks look at the evidence that reached the model, not at the wording of the answer: a
passage either arrived or it didn't. Text is compared ignoring case, spacing, and punctuation
other than '-' and '.', so a check still holds when a later part renders a table differently.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from anfa import CHECKPOINT
from anfa.pipeline import Assistant, Trace

CASES_FILE = Path(__file__).resolve().parent.parent / "cases" / "cases.json"
TRACES_DIR = Path(__file__).resolve().parent.parent / "traces"


def part_number(checkpoint: str) -> int:
    return int(checkpoint.removeprefix("part-"))


def norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9.\-]+", " ", text.lower()).split())


def evaluate(trace: Trace, check: dict) -> tuple[bool, str]:
    sources = [chunk.source_id for chunk in trace.context]
    passages = [norm(chunk.text) for chunk in trace.context]
    kind = check["type"]
    if kind == "includes_sources":
        missing = [s for s in check["sources"] if s not in sources]
        return not missing, (f"missing {len(missing)} of {len(check['sources'])}: {missing}" if missing
                             else f"all {len(check['sources'])} supplied")
    if kind == "excludes_sources":
        present = [s for s in check["sources"] if s in sources]
        return not present, f"also supplied {present}" if present else "none supplied"
    if kind == "first_source":
        first = sources[0] if sources else None
        return first == check["source"], f"first is {first}"
    if kind == "includes_text":
        ok = any(norm(check["text"]) in p for p in passages)
        return ok, f"'{check['text']}' {'supplied' if ok else 'not supplied'}"
    if kind == "same_passage":
        ok = any(all(norm(t) in p for t in check["texts"]) for p in passages)
        return ok, f"{check['texts']} {'together in one passage' if ok else 'not in the same passage'}"
    if kind == "every_passage_with":
        with_text = [p for p in passages if norm(check["contains"]) in p]
        if not with_text:
            return False, f"'{check['contains']}' not supplied"
        ok = all(norm(check["also"]) in p for p in with_text)
        return ok, (f"every passage with '{check['contains']}' names '{check['also']}'" if ok
                    else f"a passage with '{check['contains']}' doesn't name '{check['also']}'")
    if kind == "status":
        return trace.status == check["equals"], f"status {trace.status}"
    if kind == "answer_contains":
        missing = [t for t in check["texts"] if norm(t) not in norm(trace.answer)]
        return not missing, f"answer lacks {missing}" if missing else "answer has all"
    if kind == "complete_by":
        complete_by = getattr(trace, "complete_by", None)
        ok = complete_by == check["route"]
        return ok, "completeness guaranteed" if ok else "completeness not guaranteed"
    raise ValueError(f"unknown check type {kind}")


@dataclass
class Result:
    case_id: str
    label: str
    detail: str


def run(assistant: Assistant, save_traces: bool = False) -> list[Result]:
    current = part_number(CHECKPOINT)
    cases = json.loads(CASES_FILE.read_text(encoding="utf-8"))["cases"]
    results = []
    for case in cases:
        trace = assistant.ask(case["question"])
        outcomes = [evaluate(trace, check) for check in case["checks"]]
        passed = all(ok for ok, _ in outcomes)
        due = part_number(case["expected_from"])
        if passed:
            label = "PASS" if current >= due else "EARLY PASS"
        else:
            label = "REGRESSION" if current >= due else f"KNOWN GAP -> {case['expected_from']}"
        results.append(Result(case["id"], label, "; ".join(d for _, d in outcomes)))
        if save_traces:
            _save(case["id"], trace)
    return results


def _save(case_id: str, trace: Trace) -> None:
    directory = TRACES_DIR / CHECKPOINT
    directory.mkdir(parents=True, exist_ok=True)
    record = {
        "question": trace.question,
        "retrieved": trace.retrieved,
        "context": [{"ref": c.ref, "id": c.id, "text": c.text} for c in trace.context],
        "prompt": trace.prompt,
        "answer": trace.answer,
        "status": trace.status,
    }
    (directory / f"{case_id}.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
