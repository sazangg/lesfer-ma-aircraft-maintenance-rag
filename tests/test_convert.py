"""Part 3: the converter, on the real parse. No model is called: figures get a stub description."""

from __future__ import annotations

import copy

import pytest

from anfa.convert import convert, load_corrections, repair_ad_numbers
from anfa.corpus import load_corpus
from anfa.pipeline import rendered_sections


class StubDescriber:
    def describe(self, image, caption, document):
        return f"described {image.name}"


@pytest.fixture(scope="module")
def docs():
    return {d.source_id: d for d in load_corpus()}


@pytest.fixture(scope="module")
def corrections():
    return load_corrections()


def text(doc, corrections, describer=None) -> str:
    return "\n".join(s.text for s in rendered_sections(convert(doc, describer, corrections)))


def test_table_7_1_row_has_its_own_values(docs, corrections):
    assert "| 8-36 | 12-15 | 7-9 | 20 | 12 |" in text(docs["AC-43.13-1B-CH7"], corrections)
    raw = text(docs["AC-43.13-1B-CH7"], {})
    assert "| 8-36 | FOLLOWING TORQUE 12-15 |" in raw


def test_table_caption_and_note_stay_with_the_table(docs, corrections):
    rendered = text(docs["AC-43.13-1B-CH7"], corrections)
    caption = rendered.index("TABLE 7-1. Recommended torque values")
    assert rendered.index("| 8-36 |") > caption
    assert "equal face bearing areas" in rendered


def test_correction_written_against_another_parse_is_not_applied(docs, corrections):
    doc = copy.deepcopy(docs["WO-SCAN"])
    next(e for e in doc.elements if e["id"] == "e9")["text"] = "Approved for return to service: A.Tazi"
    result = convert(doc, None, corrections)
    assert any(n.startswith("e9: the parse changed") for n in result.report.needs_review)
    assert "Approved for return to service: A.Tazi" in "\n".join(s.text for s in rendered_sections(result))


def test_scanned_signatures_are_corrected(docs, corrections):
    rendered = text(docs["WO-SCAN"], corrections)
    assert rendered.count("Approved for return to service: A. Tazi") == 2
    assert "Approved for return to service: K. Bennani" in rendered
    assert "Work order WO-2026-0388" in rendered
    assert "alaou" not in rendered.replace("Y. Alaoui", "")


def test_directive_keeps_only_its_own_rule(docs, corrections):
    rendered = text(docs["AD-2008-03-02"], corrections)
    assert "TFE731" not in rendered
    for line in ("VerDate", "with RULES", "BILLING CODE", "[FR Doc."):
        assert line not in text(docs["AD-2013-11-11"], corrections)


def test_ad_numbers_split_at_a_line_break():
    assert repair_ad_numbers("supersedes AD 200324-13, which") == ("supersedes AD 2003-24-13, which", 1)
    assert repair_ad_numbers("issued AD 2003-2413 to") == ("issued AD 2003-24-13 to", 1)
    # A correction notice quotes the misprint; EASA numbers its directives this way.
    assert repair_ad_numbers("to read ''39-13369; AD 200323-05''.")[1] == 0
    assert repair_ad_numbers("European Aviation Safety Agency AD 2007-0232, dated")[1] == 0


def test_tcds_section_heading(docs, corrections):
    sections = convert(docs["TCDS-3A12-R89"], None, corrections).sections
    assert any(s.number == "IV" and s.title.startswith("Model 172D") for s in sections)


def test_slide_notes_come_back_from_the_source_file(docs, corrections):
    assert "Speaker notes: The 50-hour allowance in paragraph (g)(6) of AD 2013-11-11 applied once" in text(
        docs["TRAIN-AD"], corrections)


def test_logbook_pages_are_one_table(docs, corrections):
    result = convert(docs["LOG-CN-TFA"], None, corrections)
    tables = [e for s in result.sections for e in s.elements if e.kind == "table"]
    assert len(tables) == 1 and result.report.merged_tables == 2


def test_sheet_names_become_table_scope(docs, corrections):
    rendered = text(docs["FLEET-2026-10"], corrections)
    for sheet in ("Sheet: Fleet", "Sheet: Equipment", "Sheet: Time-controlled parts"):
        assert sheet in rendered


def test_figures_are_described(docs, corrections):
    result = convert(docs["AC-43.13-1B-CH7"], StubDescriber(), corrections)
    assert result.report.described_figures == 32
    assert "Figure description: described AC-43.13-1B-CH7-fig1.png" in "\n".join(
        s.text for s in rendered_sections(result))


def test_unchecked_ocr_is_reported(docs, corrections):
    assert any("pages 1-31" in n for n in convert(docs["NACA-TM-579"], None, corrections).report.needs_review)
    assert not convert(docs["WO-SCAN"], None, corrections).report.needs_review
    # Printed pages whose figures the parser OCR'd are not scans.
    assert not convert(docs["AC-43-9C"], None, corrections).report.needs_review
