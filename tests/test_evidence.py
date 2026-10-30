"""Part 4: searched pieces and supplied blocks, on the real documents. No model is called."""

from __future__ import annotations

import pytest

from anfa.convert import convert, load_corrections
from anfa.corpus import load_corpus
from anfa.evidence import BLOCK_CHARS, evidence_units


@pytest.fixture(scope="module")
def units():
    docs = {d.source_id: d for d in load_corpus()}
    corrections = load_corrections()

    def build(source_id: str):
        searchable, blocks = evidence_units(convert(docs[source_id], None, corrections))
        return searchable, {b.id: b for b in blocks}

    return build


def test_a_tcds_section_is_supplied_with_its_model(units):
    searchable, blocks = units("TCDS-3A12-R89")
    engine = next(c for c in searchable if "IO-360-L2A" in c.text and "180" in c.text and c.section == "XII")
    supplied = blocks[engine.parent_id].text
    assert "Model 172S" in supplied and "Rated 180 Horsepower" in supplied


def test_a_work_order_paragraph_is_searched_with_its_aircraft(units):
    searchable, _ = units("WO-2025-0095")
    work = next(c for c in searchable if "Replaced engine oil pressure switch" in c.text)
    assert "CN-TFD" in work.search_text and "CN-TFD" not in work.text


def test_a_logbook_row_is_searched_alone_with_its_column_names(units):
    searchable, blocks = units("LOG-CN-TFE")
    row = next(c for c in searchable if "WO-2024-0284" in c.text)
    assert "Work order: WO-2024-0284" in row.search_text
    assert "| Date | Airframe hours | Work order | Entry | Signed |" in blocks[row.parent_id].text


def test_a_torque_row_brings_its_header_caption_and_note(units):
    searchable, blocks = units("AC-43.13-1B-CH7")
    row = next(c for c in searchable if c.text.startswith("| 8-36 |"))
    table = blocks[row.parent_id].text
    assert "TABLE 7-1. Recommended torque values" in table
    assert "Thread size | Recommended for installation" in table
    assert "equal face bearing areas" in table


def test_a_figure_block_points_to_its_image_and_page(units):
    searchable, blocks = units("AC-43.13-1B-CH7")
    figure = next(b for b in blocks.values() if b.meta["element"] == "figure")
    assert "Image: figures/AC-43.13-1B-CH7-fig1.png (page " in figure.text


def test_slide_notes_are_searched_and_supplied(units):
    searchable, blocks = units("TRAIN-AD")
    slide = next(c for c in searchable if c.text == "The engine oil pressure switch")
    assert "applied once" in slide.search_text and "applied once" in blocks[slide.parent_id].text


def test_long_tables_are_split_with_their_header(units):
    _, blocks = units("AC-43.13-1B-CH7")
    tables = [b.text for b in blocks.values() if b.meta["element"] == "table"]
    assert all(len(t) <= BLOCK_CHARS + 400 for t in tables)  # the heading lines come on top


def test_each_scanned_page_is_searched_as_its_own_work_order(units):
    searchable, _ = units("WO-SCAN")
    work = [c.search_text for c in searchable if c.text.startswith("Replaced engine oil pressure switch")]
    assert "CN-TFE" in work[0] and "CN-TFA" in work[1]
