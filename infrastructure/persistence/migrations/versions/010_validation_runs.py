"""Phase 11: what happened when the platform was given real work.

Revision ID: 010
Revises: 009
Create Date: 2026-09-08

One table, and the argument for it is that the phase's Definition of Done is a
claim about a *series*: what works reliably, what works sometimes, what does not
work at all. Every one of those words is about repetition, and repetition cannot
be read off a terminal that has scrolled.

**Why not derive it from `tasks`.** A task row says a task completed. It does
not say what the request was supposed to produce, whether it produced it, or
which of the platform's capabilities was being asked for - those come from the
scenario the run was measured against, and nothing in `tasks` knows a scenario
exists. Reconstructing a verdict from task rows would mean re-deciding, months
later, a judgement that was made once with the evidence in front of it.

**No foreign keys and no task ids.** Same rule as `audit_log`, for a reason that
gets stronger with time: this record is read when somebody asks whether a
capability has regressed, which is long after the tasks behind it are of any
interest and possibly after they have been cleared.

**`failure` has no CHECK constraint.** The classification is a hypothesis about
how this platform fails, and the first genuinely new failure should be recorded
under a new name that afternoon, not after a migration.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None

STATUSES = ("PASSED", "FAILED", "SKIPPED")


def upgrade() -> None:
    op.create_table(
        "validation_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("scenario", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("failure", sa.String(32), nullable=False, server_default="NONE"),
        sa.Column("result", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('" + "','".join(STATUSES) + "')", name="ck_validation_runs_status"
        ),
    )
    op.create_index(
        "ix_validation_runs_scenario",
        "validation_runs",
        ["workspace_id", "scenario", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_validation_runs_scenario", table_name="validation_runs")
    op.drop_table("validation_runs")
