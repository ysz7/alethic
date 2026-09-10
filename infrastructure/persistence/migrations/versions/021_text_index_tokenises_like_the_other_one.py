"""Phase 19: the PostgreSQL text index cuts words where FTS5 cuts them.

Revision ID: 021
Revises: 020
Create Date: 2026-09-10

The second backend was written in Phase 15 and first run against a real server
in Phase 19, which is when the two indexes turned out to be answering different
questions. PostgreSQL's default parser knows a file name when it sees one and
keeps `reports/q2.md` as a single token; FTS5's `unicode61` splits it into
`reports`, `q2`, `md`. A note saying where the report is was therefore found by
searching for `q2` on one backend and not on the other - and which backend a
person is on is meant to be a setting (ADR 0017), not a difference in what the
platform can remember.

So the index is rebuilt over `regexp_replace(content, '\\W+', ' ', 'g')`, which
is `unicode61`'s rule stated in PostgreSQL's terms. The expression lives in
`memory_fts` and `knowledge_fts` beside the SQLite version, and the adapter's
query is built from the same constant: an expression index that does not match
the query exactly is an index the planner will not use, and nothing would say
so.

Nothing to do on SQLite, where the index this is about does not exist.
"""

from __future__ import annotations

from alembic import op

from infrastructure.persistence import knowledge_fts, memory_fts

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def _postgres() -> bool:
    return op.get_context().dialect.name == "postgresql"


def upgrade() -> None:
    if not _postgres():
        return
    for statement in (
        *memory_fts.DROP_POSTGRES,
        *knowledge_fts.DROP_POSTGRES,
        *memory_fts.CREATE_POSTGRES,
        *knowledge_fts.CREATE_POSTGRES,
    ):
        op.execute(statement)


def downgrade() -> None:
    """Back to the parser's own tokens, which is what 007 and 016 created."""
    if not _postgres():
        return
    for statement in (*memory_fts.DROP_POSTGRES, *knowledge_fts.DROP_POSTGRES):
        op.execute(statement)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_memory_items_text ON memory_items "
        "USING GIN (to_tsvector('simple', content))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_text ON chunks "
        "USING GIN (to_tsvector('simple', content))"
    )
