"""Phase 9: memory - what the platform keeps between runs.

Revision ID: 007
Revises: 006
Create Date: 2026-09-07

Two things here are not the default choice.

**FTS5.** The search index is a virtual table with three triggers rather than a
`LIKE` over `content`, and it is the only SQLite-specific part of the schema.
That is affordable exactly because nothing above `infrastructure/` knows it
exists: every search goes through `Memory.recall`, so replacing this with
pgvector is replacing one adapter (§9.9).

**No foreign keys on `employee_id` and `task_id`.** Memory is written about a
task and outlives it. Keying it to `tasks` would mean that clearing history
erases what was learned, and keying it to `employees` would mean that renaming
an employee's directory throws away its private memory - both of which delete
the valuable half in order to protect the referential integrity of the cheap
half. The scope columns are what the access rule reads, and it reads them
without joining.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from infrastructure.persistence import memory_fts

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

SCOPES = ("WORKSPACE", "PLAN", "EMPLOYEE_PRIVATE")
KINDS = ("WORKING", "EPISODIC", "SEMANTIC", "PROCEDURAL")


def _sqlite() -> bool:
    """Which backend this migration is running against.

    Asked rather than configured: the schema is the same on both, and what is
    not is the text index - FTS5 with triggers on one, a GIN index over
    `to_tsvector` on the other (ADR 0017).
    """
    return op.get_context().dialect.name == "sqlite"

def upgrade() -> None:
    op.create_table(
        "memory_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("employee_id", sa.String(36), nullable=True),
        sa.Column("plan_id", sa.String(36), nullable=True),
        sa.Column("task_id", sa.String(36), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("importance", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "scope IN ('" + "','".join(SCOPES) + "')", name="ck_memory_items_scope"
        ),
        sa.CheckConstraint("kind IN ('" + "','".join(KINDS) + "')", name="ck_memory_items_kind"),
    )
    op.create_index(
        "ix_memory_items_scope", "memory_items", ["workspace_id", "scope", "kind", "created_at"]
    )
    op.create_index(
        "ix_memory_items_employee", "memory_items", ["employee_id", "kind", "created_at"]
    )
    for statement in memory_fts.CREATE if _sqlite() else memory_fts.CREATE_POSTGRES:
        op.execute(statement)


def downgrade() -> None:
    for statement in memory_fts.DROP if _sqlite() else memory_fts.DROP_POSTGRES:
        op.execute(statement)
    op.drop_index("ix_memory_items_employee", table_name="memory_items")
    op.drop_index("ix_memory_items_scope", table_name="memory_items")
    op.drop_table("memory_items")
