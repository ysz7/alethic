"""Phase 17: the model catalog can also be a thing a person edits.

Revision ID: 020
Revises: 019
Create Date: 2026-09-09

`models.toml` is the file you edit to change models, and that was the right
shape while the person editing it was the developer. It is the wrong shape
inside an installed application: nobody opens a TOML file in a window, and
`clone && run` is not how most people will get this.

So the catalog gains a second source, and the file becomes the seed. A fresh
installation copies the shipped entries in and then belongs to the user;
`PROMETHEUS_MODEL_CATALOG_PATH` still overrides everything, because validation and
CI need a catalog they can state in one environment variable and not a database
they would have to populate first.

`task_defaults` is "give this key to this task", which was the whole request.
One row per kind of work and deliberately not per employee: a declaration may
not name a model (ADR 0003), and a table keyed by employee would be that rule
broken where the rule cannot see it.

Neither table has a foreign key onto `connections`. An entry names a connection
the way everything here names things - a catalog that fails to load because a
connection was deleted is worse than one that says which entry is now unreachable.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_entries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("connection", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("context_tokens", sa.Integer(), nullable=False, server_default="8192"),
        sa.Column("input_cost_per_1k_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("output_cost_per_1k_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("quality", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("dimensions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_model_entries_name"),
    )
    op.create_table(
        "task_defaults",
        sa.Column("task_kind", sa.String(length=32), primary_key=True),
        sa.Column("workspace_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("entry_name", sa.String(length=120), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("task_defaults")
    op.drop_table("model_entries")
