"""The index, in Postgres: each chunk's text, metadata, and embedding (pgvector).

From Part 4, a chunk is a searched piece, and `blocks` holds what is supplied to the model in
its place (`parent_id`).

Search runs in SQL. The access filter is part of the same query, so a chunk the user may not
read is never a candidate, and the nearest of the rest are found by comparing the question with
every chunk. That is exact, and at a few thousand chunks it takes milliseconds. Parts 1 to 3 used
an approximate (HNSW) index; Part 4 dropped it, see CHECKPOINTS.md.
"""

from __future__ import annotations

import json

import psycopg
from pgvector.psycopg import register_vector

from anfa.chunking import Chunk
from anfa.config import SETTINGS

SCHEMA = """
create extension if not exists vector;
create table if not exists chunks (
    id text primary key,
    text text not null,
    source_id text not null,
    section text not null,
    meta jsonb not null,
    access text[] not null,
    embedding vector({dims}) not null
);
alter table chunks add column if not exists parent_id text;
drop index if exists chunks_embedding;
create table if not exists blocks (
    id text primary key,
    text text not null,
    source_id text not null,
    section text not null,
    meta jsonb not null,
    access text[] not null
);
create table if not exists index_state (key text primary key, value text not null);
"""


class PgVectorIndex:
    def __init__(self, dsn: str = SETTINGS.database_url, dimensions: int = SETTINGS.embed_dimensions):
        self.conn = psycopg.connect(dsn, autocommit=True)
        self.conn.execute(SCHEMA.format(dims=dimensions))
        register_vector(self.conn)

    def reset(self, fingerprint: str) -> None:
        self.conn.execute("truncate chunks, blocks")
        self.conn.execute("insert into index_state values ('fingerprint', %s) "
                          "on conflict (key) do update set value = excluded.value", (fingerprint,))

    def fingerprint(self) -> str | None:
        row = self.conn.execute("select value from index_state where key = 'fingerprint'").fetchone()
        return row[0] if row else None

    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        import numpy as np

        with self.conn.cursor() as cur:
            cur.executemany(
                "insert into chunks (id, text, source_id, section, meta, access, embedding, parent_id) "
                "values (%s, %s, %s, %s, %s, %s, %s, %s)",
                [(c.id, c.text, c.source_id, c.section, json.dumps(c.meta), _groups(c.meta), np.array(v), c.parent_id)
                 for c, v in zip(chunks, vectors)],
            )

    def add_blocks(self, blocks: list[Chunk]) -> None:
        with self.conn.cursor() as cur:
            cur.executemany(
                "insert into blocks values (%s, %s, %s, %s, %s, %s)",
                [(b.id, b.text, b.source_id, b.section, json.dumps(b.meta), _groups(b.meta)) for b in blocks],
            )

    def blocks(self, ids: list[str], allowed_groups: set[str]) -> dict[str, Chunk]:
        rows = self.conn.execute(
            "select id, text, source_id, section, meta from blocks where id = any(%s) and access && %s",
            (ids, sorted(allowed_groups)),
        ).fetchall()
        return {r[0]: Chunk(*r) for r in rows}

    def search(self, vector: list[float], allowed_groups: set[str], limit: int) -> list[tuple[float, Chunk]]:
        import numpy as np

        rows = self.conn.execute(
            "select id, text, source_id, section, meta, parent_id, 1 - (embedding <=> %s) as score from chunks "
            "where access && %s order by embedding <=> %s limit %s",
            (np.array(vector), sorted(allowed_groups), np.array(vector), limit),
        ).fetchall()
        return [(score, Chunk(id_, text, source_id, section, meta, parent_id))
                for id_, text, source_id, section, meta, parent_id, score in rows]

    def __len__(self) -> int:
        return self.conn.execute("select count(*) from chunks").fetchone()[0]


def _groups(meta: dict) -> list[str]:
    return [g.strip() for g in meta.get("access", "").split(",") if g.strip()]
