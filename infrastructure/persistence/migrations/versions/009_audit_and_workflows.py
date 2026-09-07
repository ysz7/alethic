"""Phase 10: the audit log, workflow runs, and a deadline on a question.

Revision ID: 009
Revises: 008
Create Date: 2026-09-07

**Why an audit log when `tool_calls` already exists.** They answer different
questions and diverge exactly where it matters. `tool_calls` is accounting: what
ran, how long it took, what came back. `audit_log` is accountability: who asked
for what, and what was decided. A denied action has an audit line and no tool
call - the tool never ran - and a denied action is the single most important
thing an audit can show. Merging the two tables would mean either inventing a
tool call that never happened, or losing the denial.

**No foreign keys on `task_id` and `assignment_id`.** An audit record outlives
what it describes. Keying it to `tasks` would mean that clearing history erases
the record of what was done to the machine, which is the one thing that has to
survive housekeeping. Same reasoning as what 007 says about memory, for a
stronger reason.

**`approvals.expires_at`.** A question can now be given a deadline, and the
column is what makes the deadline survivable: the process that asked is usually
gone by the time it passes, so nothing is left in memory to time out. The row is
the question, and closing it is an UPDATE rather than a callback nobody is
holding. NULL means wait forever, which stays the behaviour for a terminal
prompt where somebody is definitely there.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

ACTOR_KINDS = ("USER", "ALETHIC", "EMPLOYEE", "SYSTEM")
RESULTS = ("SUCCESS", "FAILURE", "DENIED")
TRIGGERS = ("MANUAL", "SCHEDULED", "EVENT", "CONDITIONAL")
RUN_STATUSES = ("RUNNING", "COMPLETED", "FAILED", "CANCELLED")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ('" + "','".join(values) + "')"


def upgrade() -> None:
    op.add_column("approvals", sa.Column("expires_at", sa.DateTime(), nullable=True))

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("actor_kind", sa.String(16), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("task_id", sa.String(36), nullable=True),
        sa.Column("assignment_id", sa.String(36), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("tool", sa.String(64), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.CheckConstraint(_in("actor_kind", ACTOR_KINDS), name="ck_audit_log_actor_kind"),
        sa.CheckConstraint(_in("result", RESULTS), name="ck_audit_log_result"),
    )
    op.create_index("ix_audit_log_ts", "audit_log", ["ts"])
    op.create_index("ix_audit_log_task", "audit_log", ["task_id", "ts"])
    op.create_index("ix_audit_log_actor", "audit_log", ["actor_kind", "actor_id", "ts"])

    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("workflow", sa.String(64), nullable=False),
        sa.Column("trigger", sa.String(16), nullable=False),
        sa.Column("input", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(_in("trigger", TRIGGERS), name="ck_workflow_runs_trigger"),
        sa.CheckConstraint(_in("status", RUN_STATUSES), name="ck_workflow_runs_status"),
    )
    op.create_index("ix_workflow_runs_started", "workflow_runs", ["workspace_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_runs_started", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_index("ix_audit_log_actor", table_name="audit_log")
    op.drop_index("ix_audit_log_task", table_name="audit_log")
    op.drop_index("ix_audit_log_ts", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_column("approvals", "expires_at")
