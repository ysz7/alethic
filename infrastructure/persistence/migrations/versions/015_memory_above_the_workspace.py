"""Phase 15: two memory scopes that are not inside a workspace.

Revision ID: 015
Revises: 014
Create Date: 2026-09-08

`USER` is the person and `SYSTEM` is this installation. A stated preference -
"always answer in Markdown" - was not said about the sales folder, and having to
re-state it in every workspace would be a chore the platform invented for
itself. The workspace it was stated in stays on the row as provenance, so a
later "only here" narrows an existing record rather than needing a migration.

The whole of the change is one CHECK constraint, and on SQLite widening one
means rebuilding the table. Three things make that safe and are the reason this
file is longer than the sentence above.

**The index is dropped and rebuilt around the copy.** The FTS5 triggers name
`memory_items`; a rebuild under them leaves triggers pointing at a table that
was renamed away. So the index goes first and is rebuilt from the rows
afterwards - which is also the honest thing to do with a search index, and is
what a move to another backend will have to do (ADR 0017).

**Nothing is reclassified.** Every existing row keeps the scope it has. This
migration widens what is allowed and changes no data: what gets written at
`USER` is what is written after it, by the recorder.

**The downgrade narrows the constraint back and would refuse rows it cannot
hold**, so it deletes the two new scopes first and says so. A downgrade that
left the rows would fail the constraint at rebuild time and roll back with a
message about a check, which is a worse way to learn the same thing.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from infrastructure.persistence import memory_fts

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None

BEFORE = ("WORKSPACE", "PLAN", "EMPLOYEE_PRIVATE")
AFTER = (*BEFORE, "USER", "SYSTEM")


def _rebuild(scopes: tuple[str, ...]) -> None:
    """Widen or narrow the scope constraint, whichever backend this is.

    PostgreSQL alters a constraint in place and its text index is a GIN index
    the database maintains, so there is nothing to rebuild there. All of the
    ceremony below is SQLite's, and it is SQLite's for a reason worth keeping
    visible: changing a CHECK means recreating the table, and recreating the
    table under triggers that name it leaves them pointing at something that
    has been renamed away.
    """
    allowed = "scope IN ('" + "','".join(scopes) + "')"
    if op.get_context().dialect.name != "sqlite":
        op.drop_constraint("ck_memory_items_scope", "memory_items", type_="check")
        op.create_check_constraint("ck_memory_items_scope", "memory_items", allowed)
        return
    for statement in memory_fts.DROP:
        op.execute(statement)
    with op.batch_alter_table("memory_items", recreate="always") as batch:
        batch.drop_constraint("ck_memory_items_scope", type_="check")
        batch.create_check_constraint("ck_memory_items_scope", allowed)
    for statement in memory_fts.CREATE:
        op.execute(statement)
    # The rebuilt table's rows were copied, not inserted through the trigger,
    # so the index knows nothing about them until it is filled from here.
    op.execute(
        sa.text(
            "INSERT INTO memory_items_fts (item_id, content) "
            "SELECT id, content FROM memory_items"
        )
    )


def upgrade() -> None:
    _rebuild(AFTER)


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM memory_items WHERE scope IN ('USER', 'SYSTEM')"))
    _rebuild(BEFORE)
