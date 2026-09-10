"""The full-text index over `memory_items`, and the triggers that keep it true.

FTS5 is the one SQLite-specific thing in the schema, which is why it is written
once here and used from both places that build the database: the migration, and
the metadata that the test suite creates tables from. Two hand-copied versions
of a trigger drift, and a search index that drifts is a search that quietly
stops finding things.

The index is a standalone table rather than an external-content one. External
content is smaller, and it makes every write to `memory_items` a write that must
be mirrored exactly or the index corrupts; the content here is short - a
sentence or two per item - and correctness is worth the duplication.
"""

from __future__ import annotations

CREATE_INDEX = (
    "CREATE VIRTUAL TABLE IF NOT EXISTS memory_items_fts "
    "USING fts5(item_id UNINDEXED, content, tokenize='unicode61')"
)

#: Written by trigger rather than by the repository, so an item is searchable
#: because it is stored - not because the code path that stored it remembered.
CREATE_TRIGGERS = (
    """
    CREATE TRIGGER IF NOT EXISTS memory_items_fts_insert
    AFTER INSERT ON memory_items BEGIN
        INSERT INTO memory_items_fts (item_id, content) VALUES (new.id, new.content);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS memory_items_fts_update
    AFTER UPDATE OF content ON memory_items BEGIN
        UPDATE memory_items_fts SET content = new.content WHERE item_id = new.id;
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS memory_items_fts_delete
    AFTER DELETE ON memory_items BEGIN
        DELETE FROM memory_items_fts WHERE item_id = old.id;
    END
    """,
)

DROP = (
    "DROP TRIGGER IF EXISTS memory_items_fts_delete",
    "DROP TRIGGER IF EXISTS memory_items_fts_update",
    "DROP TRIGGER IF EXISTS memory_items_fts_insert",
    "DROP TABLE IF EXISTS memory_items_fts",
)

#: Everything needed to make an existing `memory_items` searchable, in order.
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
    f"CREATE INDEX IF NOT EXISTS ix_memory_items_text ON memory_items "
    f"USING GIN ({POSTGRES_VECTOR.format(column='content')})",
)

DROP_POSTGRES = ("DROP INDEX IF EXISTS ix_memory_items_text",)
