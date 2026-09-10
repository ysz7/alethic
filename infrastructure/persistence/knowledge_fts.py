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


#: How the words of `content` are found on PostgreSQL, written once because the
#: index and the query have to agree exactly or the index is not used at all.
#:
#: The `regexp_replace` is what makes the two backends answer the same question.
#: PostgreSQL's default parser keeps `reports/q2.md` as one token - it knows a
#: file name when it sees one - while FTS5's `unicode61` splits it into
#: `reports`, `q2`, `md`. So a search for `q2` found the note on SQLite and not
#: on PostgreSQL, which Phase 19 found by running the memory tests on the second
#: dialect. Cutting on non-word characters first is `unicode61`'s rule stated in
#: the other dialect's terms; `\W` rather than a character class because
#: SQLAlchemy's `text()` would read `[:alnum:]` as a bind parameter named
#: `alnum`.
POSTGRES_VECTOR = "to_tsvector('simple', regexp_replace({column}, '\\W+', ' ', 'g'))"


#: The same capability on PostgreSQL, which has no FTS5 and needs none: a GIN
#: index over `to_tsvector` answers the same question, is kept current by the
#: database rather than by triggers, and is queried by the adapter's other
#: branch. Written here beside the SQLite version so the two cannot drift into
#: being about different columns (ADR 0017).
CREATE_POSTGRES = (
    f"CREATE INDEX IF NOT EXISTS ix_chunks_text ON chunks "
    f"USING GIN ({POSTGRES_VECTOR.format(column='content')})",
)

DROP_POSTGRES = ("DROP INDEX IF EXISTS ix_chunks_text",)
