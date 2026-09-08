"""The full-text index over document chunks, and the triggers that keep it true.

The same shape as `memory_fts`, and separate from it for the reason the two
stores are separate: a document is not a memory (ADR 0016), and one index over
both would have to be told which rows are which on every query.

It exists alongside the vectors rather than instead of them. Semantic search is
what this phase is for - "shipping" found by "delivery" - and lexical search is
what still finds an invoice number, a surname or an error code, where meaning is
not the question. `domain/knowledge/ranking.py` is where the two are reconciled.
"""

from __future__ import annotations

CREATE_INDEX = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts "
    "USING fts5(chunk_id UNINDEXED, content, tokenize='unicode61')"
)

#: By trigger, so a passage is searchable because it is stored - not because
#: the code path that stored it remembered to say so.
CREATE_TRIGGERS = (
    """
    CREATE TRIGGER IF NOT EXISTS chunks_fts_insert
    AFTER INSERT ON chunks BEGIN
        INSERT INTO chunks_fts (chunk_id, content) VALUES (new.id, new.content);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS chunks_fts_update
    AFTER UPDATE OF content ON chunks BEGIN
        UPDATE chunks_fts SET content = new.content WHERE chunk_id = new.id;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS chunks_fts_delete
    AFTER DELETE ON chunks BEGIN
        DELETE FROM chunks_fts WHERE chunk_id = old.id;
    END
    """,
)

DROP = (
    "DROP TRIGGER IF EXISTS chunks_fts_delete",
    "DROP TRIGGER IF EXISTS chunks_fts_update",
    "DROP TRIGGER IF EXISTS chunks_fts_insert",
    "DROP TABLE IF EXISTS chunks_fts",
)

CREATE = (CREATE_INDEX, *CREATE_TRIGGERS)


#: The same capability on PostgreSQL, which has no FTS5 and needs none: a GIN
#: index over `to_tsvector` answers the same question, is kept current by the
#: database rather than by triggers, and is queried by the adapter's other
#: branch. Written here beside the SQLite version so the two cannot drift into
#: being about different columns (ADR 0017).
CREATE_POSTGRES = (
    "CREATE INDEX IF NOT EXISTS ix_chunks_text ON chunks "
    "USING GIN (to_tsvector('simple', content))",
)

DROP_POSTGRES = ("DROP INDEX IF EXISTS ix_chunks_text",)
