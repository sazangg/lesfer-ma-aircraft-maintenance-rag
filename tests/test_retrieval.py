"""Part 5: the retrieval stage's own parts. No model is called; the keyword test needs Postgres."""

from __future__ import annotations

import psycopg
import pytest

from anfa.chunking import Chunk
from anfa.config import SETTINGS
from anfa.retrieval import ad_numbers, reciprocal_rank_fusion
from anfa.store import TERMS


def chunk(id_: str) -> Chunk:
    return Chunk(id_, "", "", "", {})


def test_ad_numbers_in_both_styles():
    assert ad_numbers("Does AD 2000-04-01 or 98-01-01 apply?") == ["2000-04-01", "98-01-01"]


def test_a_part_number_is_not_an_ad_number():
    # A date like 2008-05-21 has the same shape; its lookup finds no directive and adds nothing.
    assert ad_numbers("Which directive covers part number 2013142-18?") == []


def test_fusion_favours_a_chunk_both_searches_found():
    lexical = [chunk("a"), chunk("b"), chunk("c")]
    dense = [chunk("d"), chunk("e"), chunk("c")]
    assert [c.id for c in reciprocal_rank_fusion(lexical, dense)][0] == "c"


def test_fusion_keeps_each_chunk_once():
    fused = reciprocal_rank_fusion([chunk("a"), chunk("b")], [chunk("b"), chunk("a")])
    assert sorted(c.id for c in fused) == ["a", "b"]


@pytest.fixture
def terms_table():
    try:
        conn = psycopg.connect(SETTINGS.database_url, autocommit=True)
    except psycopg.OperationalError:
        pytest.skip("no database")
    conn.execute("create extension if not exists pg_search")
    conn.execute("drop table if exists terms_test")
    conn.execute("create table terms_test (id int primary key, body text)")
    conn.execute(
        "insert into terms_test values (1, 'AD 2000-04-01 applies to the switch.'),"
        " (2, 'Revised 2001-04-17; see paragraph 01.'), (3, 'Replace P/N 2013142-18.')"
    )
    conn.execute(
        "create index terms_test_bm25 on terms_test using bm25 (id, body) with (text_fields = "
        f"'{{\"body\": {{\"tokenizer\": {{\"type\": \"regex\", \"pattern\": \"{TERMS}\"}}}}}}')"
    )
    yield conn
    conn.execute("drop table terms_test")
    conn.close()


def matches(conn, query: str) -> list[int]:
    return [r[0] for r in conn.execute("select id from terms_test where body ||| %s order by id", (query,))]


def test_a_directive_number_is_matched_whole(terms_table):
    # The default tokenizer splits the number into "2000", "04", "01", and row 2's "01" would match.
    assert matches(terms_table, "What does AD 2000-04-01 require?") == [1]


def test_a_part_number_is_matched_whole(terms_table):
    assert matches(terms_table, "part number 2013142-18") == [3]
