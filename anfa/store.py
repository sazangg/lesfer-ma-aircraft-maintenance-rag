"""The index, in Postgres: each chunk's text, metadata, and embedding (pgvector).

Search runs in SQL. The access filter is part of the same query, so a chunk the user may
not read is never a candidate, and the HNSW index finds the nearest of the rest.
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
create index if not exists chunks_embedding on chunks using hnsw (embedding vector_cosine_ops);
create table if not exists index_state (key text primary key, value text not null);
"""


class PgVectorIndex:
    def __init__(self, dsn: str = SETTINGS.database_url, dimensions: int = SETTINGS.embed_dimensions):
        self.conn = psycopg.connect(dsn, autocommit=True)
        self.conn.execute(SCHEMA.format(dims=dimensions))
        register_vector(self.conn)

    def reset(self, fingerprint: str) -> None:
        self.conn.execute("truncate chunks")
        self.conn.execute("insert into index_state values ('fingerprint', %s) "
                          "on conflict (key) do update set value = excluded.value", (fingerprint,))

    def fingerprint(self) -> str | None:
        row = self.conn.execute("select value from index_state where key = 'fingerprint'").fetchone()
        return row[0] if row else None

    def add(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        import numpy as np

        with self.conn.cursor() as cur:
            cur.executemany(
                "insert into chunks values (%s, %s, %s, %s, %s, %s, %s)",
                [(c.id, c.text, c.source_id, c.section, json.dumps(c.meta), _groups(c.meta), np.array(v))
                 for c, v in zip(chunks, vectors)],
            )

    def search(self, vector: list[float], allowed_groups: set[str], limit: int) -> list[tuple[float, Chunk]]:
        import numpy as np

        rows = self.conn.execute(
            "select id, text, source_id, section, meta, 1 - (embedding <=> %s) as score from chunks "
            "where access && %s order by embedding <=> %s limit %s",
            (np.array(vector), sorted(allowed_groups), np.array(vector), limit),
        ).fetchall()
        return [(score, Chunk(id_, text, source_id, section, meta)) for id_, text, source_id, section, meta, score in rows]

    def __len__(self) -> int:
        return self.conn.execute("select count(*) from chunks").fetchone()[0]


def _groups(meta: dict) -> list[str]:
    return [g.strip() for g in meta.get("access", "").split(",") if g.strip()]
