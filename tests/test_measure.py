"""Part 7: the measuring code. No model is called."""

from __future__ import annotations

from anfa.chunking import Chunk
from anfa.judge import Judge
from anfa.measure import meets, retrieval_row
from anfa.pipeline import Trace


def block(source: str, text: str) -> Chunk:
    return Chunk(f"{source}-b", text, source, "", {})


def test_a_block_meets_a_need_by_source_and_phrases():
    need = {"source": "TCDS-3A12-R89", "texts": ["172S", "Rated 180 Horsepower"]}
    assert meets(block("TCDS-3A12-R89", "Model 172S ... Engine Lycoming IO-360-L2A, Rated 180 Horsepower"), need)
    assert not meets(block("TCDS-3A12-R89", "Model 172R ... Rated 160 Horsepower"), need)


def test_a_correction_can_stand_in_for_its_directive():
    need = {"source": ["AD-2020-16-08", "AD-2020-16-08-CORRECTION"], "texts": ["2.10 or 2.10.1"]}
    assert meets(block("AD-2020-16-08-CORRECTION", "Software version 2.10 or 2.10.1 is installed"), need)


def test_recall_precision_and_first_relevant():
    case = {"id": "X", "relevant": [{"source": "A", "texts": ["one"]}, {"source": "B"}]}
    trace = Trace("q", context=[block("C", "noise"), block("A", "one two"), block("D", "noise")], prompt="x" * 400)
    row = retrieval_row(case, trace)
    assert (row.hit, row.recall, round(row.precision, 2), row.first, row.tokens) == (1.0, 0.5, 0.33, 2, 100)
    assert row.missing == ["B"]


class Reply:
    def __init__(self, text: str):
        self.text = text

    def generate(self, prompt: str) -> str:
        return self.text


def test_the_judge_verdict_is_read_from_its_reply():
    assert Judge(Reply("VERDICT: **unsupported**\nThe sources give 180.")).verdict("q", "a", ["s"])[0] == "unsupported"
    assert Judge(Reply("I think it is fine.")).verdict("q", "a", ["s"])[0] == "unreadable"
