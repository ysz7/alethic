"""The manager's stored name: KAI becomes Alethic.

Revision ID: 008
Revises: 007
Create Date: 2026-09-07

The rename is a rename of the product, and `ActorKind` and `TaskCreatedBy` are
StrEnums whose *values* are written into rows. A database made before the rename
therefore carries `KAI` and `kai`, and reading one of those rows back would fail
in `ActorKind(row.assigned_by)` rather than degrade - so the rows are rewritten
here instead of the enum keeping a legacy alias forever.

Only the manager's own values are touched: `user`, `schedule`, `workflow`,
`EMPLOYEE` and `SYSTEM` never named the product.
"""

from __future__ import annotations

from alembic import op

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE tasks SET created_by = 'alethic' WHERE created_by = 'kai'")
    op.execute(
        "UPDATE task_assignments SET assigned_by = 'ALETHIC' WHERE assigned_by = 'KAI'"
    )
    op.execute(
        "UPDATE task_assignments SET assigned_by_id = 'alethic' WHERE assigned_by_id = 'kai'"
    )


def downgrade() -> None:
    op.execute("UPDATE tasks SET created_by = 'kai' WHERE created_by = 'alethic'")
    op.execute(
        "UPDATE task_assignments SET assigned_by = 'KAI' WHERE assigned_by = 'ALETHIC'"
    )
    op.execute(
        "UPDATE task_assignments SET assigned_by_id = 'kai' WHERE assigned_by_id = 'alethic'"
    )
