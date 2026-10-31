"""Part 7: judging answers, and checking the judge first.

The evidence checks can't tell whether an answer's wording is right. For that, teams use a judge:
another language model asked "do the sources support this answer?". A judge is itself a model
making judgments, so before trusting its scores, compare its verdicts with labels given to the
same answers (`cases/judged_answers.json`).

The labelled answers are written to be right or wrong in known ways: a correct answer, the same
answer with another aircraft's value, a paraphrase, a reversed part number, a right number the
supplied sources don't contain. The sources are what the assistant supplies for the question.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from anfa.checks import CASES_FILE
from anfa.pipeline import Assistant
from anfa.real import OpenRouterGenerator

JUDGED_FILE = CASES_FILE.parent / "judged_answers.json"

JUDGE = """You check answers written by a maintenance assistant against the sources it was given.

Question:
{question}

Sources:
{sources}

Answer to check:
{answer}

Is every claim in the answer supported by the sources? A claim the sources don't state is
unsupported, even if it may be true. Reply with one line, "VERDICT: supported" or
"VERDICT: unsupported", then one sentence saying why."""


class Judge:
    def __init__(self, generator: OpenRouterGenerator | None = None):
        self.generator = generator or OpenRouterGenerator()

    def verdict(self, question: str, answer: str, sources: list[str]) -> tuple[str, str]:
        reply = self.generator.generate(JUDGE.format(
            question=question, answer=answer, sources="\n\n".join(f"[S{n}]\n{s}" for n, s in enumerate(sources, start=1))))
        found = re.search(r"VERDICT:\s*\**\s*(supported|unsupported)", reply, re.IGNORECASE)
        return (found.group(1).lower() if found else "unreadable"), reply.strip()


@dataclass
class Calibration:
    answer_id: str
    label: str
    judge: str
    note: str
    reason: str


def calibrate(assistant: Assistant, judge: Judge, path: Path = JUDGED_FILE) -> list[Calibration]:
    results = []
    for item in json.loads(path.read_text(encoding="utf-8"))["answers"]:
        sources = [block.text for block in assistant.prepare(item["question"]).context]
        verdict, reason = judge.verdict(item["question"], item["answer"], sources)
        results.append(Calibration(item["id"], item["label"], verdict, item["note"], reason))
    return results
