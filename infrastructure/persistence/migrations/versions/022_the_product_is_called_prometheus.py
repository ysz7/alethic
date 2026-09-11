"""The manager's stored name: Alethic becomes Prometheus.

Revision ID: 022
Revises: 021
Create Date: 2026-09-11

The second time, for the reason 008 gave the first time: `ActorKind` and
`TaskCreatedBy` are StrEnums whose *values* are written into rows, so a database
made before the rename carries `ALETHIC` and `alethic`, and reading one of those
rows back would fail in `ActorKind(row.actor_kind)` rather than degrade. The rows
are rewritten here instead of the enums keeping a legacy alias forever.

One thing 008 did not have to do: since 009, `audit_log` has a CHECK constraint
that lists the actor kinds by value. Left alone it would go on accepting the old
name and refusing the new one - so the first audit line the manager wrote after
the rename would fail, and it would fail inside the approval gate, which records
a refusal before anything else happens. The constraint is dropped, the rows are
rewritten, and the constraint is put back with the new list; in that order,
because on SQLite putting it back rebuilds the table, and a row still carrying
the old value would stop the rebuild.

Only the manager's own values are touched: `user`, `schedule`, `workflow`,
`EMPLOYEE` and `SYSTEM` never named the product. History that is prose - an
answer, a memory, a log line - keeps whatever name it was written under.
"""

from __future__ import annotations

from alembic import op

revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None

CONSTRAINT = "ck_audit_log_actor_kind"
BEFORE = ("USER", "ALETHIC", "EMPLOYEE", "SYSTEM")
AFTER = ("USER", "PROMETHEUS", "EMPLOYEE", "SYSTEM")


def _allowed(kinds: tuple[str, ...]) -> str:
    return "actor_kind IN ('" + "','".join(kinds) + "')"


def _rename(old: str, new: str, kinds: tuple[str, ...]) -> None:
    with op.batch_alter_table("audit_log") as batch:
        batch.drop_constraint(CONSTRAINT, type_="check")
    op.execute(
        f"UPDATE audit_log SET actor_kind = '{new.upper()}' WHERE actor_kind = '{old.upper()}'"
    )
    op.execute(f"UPDATE audit_log SET actor_id = '{new}' WHERE actor_id = '{old}'")
    with op.batch_alter_table("audit_log") as batch:
        batch.create_check_constraint(CONSTRAINT, _allowed(kinds))

    op.execute(f"UPDATE tasks SET created_by = '{new}' WHERE created_by = '{old}'")
    op.execute(
        f"UPDATE task_assignments SET assigned_by = '{new.upper()}' "
        f"WHERE assigned_by = '{old.upper()}'"
    )
    op.execute(
        f"UPDATE task_assignments SET assigned_by_id = '{new}' WHERE assigned_by_id = '{old}'"
    )


def upgrade() -> None:
    _rename("alethic", "prometheus", AFTER)


def downgrade() -> None:
    _rename("prometheus", "alethic", BEFORE)
