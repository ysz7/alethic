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


#: The same capability on PostgreSQL, which has no FTS5 and needs none: a GIN
#: index over `to_tsvector` answers the same question, is kept current by the
#: database rather than by triggers, and is queried by the adapter's other
#: branch. Written here beside the SQLite version so the two cannot drift into
#: being about different columns (ADR 0017).
CREATE_POSTGRES = (
    "CREATE INDEX IF NOT EXISTS ix_memory_items_text ON memory_items "
    "USING GIN (to_tsvector('simple', content))",
)

DROP_POSTGRES = ("DROP INDEX IF EXISTS ix_memory_items_text",)
