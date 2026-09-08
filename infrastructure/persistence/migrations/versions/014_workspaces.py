"""Phase 15: the column from migration 001 gets a table.

Revision ID: 014
Revises: 013
Create Date: 2026-09-08

`workspace_id` has been on every user-owned row since the first migration and
has always held 'default'. It was laid through the manager, the planner, the
supervisor, the scheduler and memory - 73 places - while there was exactly one
workspace, so that the day a second one existed nothing above the schema had to
be rewritten (§71c). This is that day, and it is one table.

**The default row is seeded here, not lazily on first read.** Every existing row
in thirteen tables belongs to a workspace called 'default'; if the record only
appeared when somebody first listed workspaces, an installation that never
listed them would have history belonging to a workspace that does not exist. The
id keeps the literal value 'default' for the same reason - rewriting it would
mean an UPDATE across every table in the database to rename something nobody
asked to rename.

**No foreign keys point at this table.** Deleting a workspace is a decision
about a person's history, and the two things a foreign key could do - cascade
through every table, or refuse - are both decisions the application should make
out loud. It is also what has kept `workspace_id` a plain column that any of the
thirteen tables can carry without knowing this table exists.

**`file_root` is a column and not a key in `settings`.** Switching workspace
moves the root the filesystem tools can see, and isolation that stops at the
moment an employee opens a file is not isolation. NULL means the root this
machine is configured with, which is what every installation has used until now.
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    workspaces = op.create_table(
        "workspaces",
        # The id is the value already written across the database - a slug of
        # the name, not a uuid. A uuid here would have made the first
        # workspace's id something no migration could reproduce.
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("file_root", sa.Text(), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    op.bulk_insert(
        workspaces,
        [
            {
                "id": "default",
                "name": "Default",
                "description": "",
                "file_root": None,
                "settings": {},
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("workspaces")
