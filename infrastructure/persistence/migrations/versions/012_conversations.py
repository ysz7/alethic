"""Phase 13: the thread a request was asked in.

Revision ID: 012
Revises: 011
Create Date: 2026-09-08

One table and one column, and the column is the interesting half.

**A conversation stores no messages.** The obvious schema here is
`conversations` + `messages`, with a row per user turn and a row per answer.
That would be a second history of work the platform already records in full:
`objectives` holds the user's verbatim sentence, what Prometheus read out of it, the
acceptance criteria, the plans, the tasks and the answer. Two histories of one
run disagree the first time a process is killed between writing them - and the
one an interface reads would be the one that is wrong.

So a message *is* an objective, and this migration only gives objectives a
thread: `objectives.conversation_id`, nullable, with no foreign key. Nullable
because the CLI, a schedule and an event all state a goal with no conversation
around it, and that is not a degraded case. No foreign key for the reason
`audit_log` and `validation_runs` have none: deleting a thread must not take
the record of what was actually done to the machine with it.

**`updated_at` rather than ordering threads by creation.** A thread picked up
after a week belongs at the top of the list; `created_at` would bury it under
threads nobody has touched since.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False, server_default="default"),
        # Named after the first thing asked in it unless the user says
        # otherwise. Empty is legal: a thread with nothing in it yet.
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_conversations_workspace_updated", "conversations", ["workspace_id", "updated_at"]
    )
    op.add_column("objectives", sa.Column("conversation_id", sa.String(36), nullable=True))
    # Reading one thread in the order it was said. The whole query, and the
    # only one this column exists for.
    op.create_index(
        "ix_objectives_conversation", "objectives", ["conversation_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_objectives_conversation", table_name="objectives")
    op.drop_column("objectives", "conversation_id")
    op.drop_index("ix_conversations_workspace_updated", table_name="conversations")
    op.drop_table("conversations")
