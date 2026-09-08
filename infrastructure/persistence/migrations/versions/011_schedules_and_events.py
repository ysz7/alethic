"""Phase 12: work that starts without anybody asking for it.

Revision ID: 011
Revises: 010
Create Date: 2026-09-08

Two tables, and they are a pair: `schedules` says what should happen and when,
`events` says what happened and whether anything acted on it.

**Why `events` is a table and not a callback.** An event that arrives while
nothing is listening has to survive until something is. A row survives a
process being killed, a machine being asleep, and the scheduler being started
five minutes later; an in-process signal survives none of those, and the
failure is silent in every case.

**`consumed_at` is on the event, not on the schedule.** Two schedules waiting on
one kind of event is a legitimate configuration; each firing twice for a single
event is not. Recording the claim on the thing being claimed is what makes the
second impossible rather than merely unlikely.

**No foreign key from `schedules` to `objectives`.** `last_objective_id` is a
pointer for a person following what a schedule actually did, and the schedule
has to outlive the history: clearing old objectives must not delete the standing
instructions that produced them. Same rule as `audit_log` and `validation_runs`.

**`next_due_at` is a stored column, not a computed one.** It is what makes "what
is due" a query rather than a scan that reconstructs a recurrence per row, and
it is the one piece of scheduler state that has to survive a restart - a timer
in a process that died is a schedule that silently stopped.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("name", sa.String(120), nullable=False, server_default=""),
        # The request in the user's own words. Not a plan and not an employee:
        # a schedule outlives the workforce it was written against.
        sa.Column("request", sa.Text(), nullable=False),
        sa.Column("every_seconds", sa.Integer(), nullable=True),
        sa.Column("daily_at", sa.String(8), nullable=True),
        sa.Column("on_event", sa.String(64), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("next_due_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_objective_id", sa.String(36), nullable=True),
        sa.Column("runs", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_schedules_due", "schedules", ["workspace_id", "enabled", "next_due_at"]
    )

    op.create_table(
        "events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("source", sa.String(120), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
    )
    # The scheduler's only hot query: unconsumed events of one kind, oldest
    # first. `consumed_at` leads the tail of the index because "not yet acted
    # on" is what almost every read is filtering for.
    op.create_index(
        "ix_events_pending", "events", ["workspace_id", "kind", "consumed_at", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_events_pending", table_name="events")
    op.drop_table("events")
    op.drop_index("ix_schedules_due", table_name="schedules")
    op.drop_table("schedules")
