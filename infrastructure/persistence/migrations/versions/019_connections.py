"""Phase 17: a connection is an account, not a vendor.

Revision ID: 019
Revises: 018
Create Date: 2026-09-09

Until now there was one API key in settings and one base URL, so "which
provider" and "which account" were the same question. They are not the same
question: one person holds two keys to one vendor - work and personal, a
client's and their own - and a configuration keyed by vendor cannot say that.

So the row is a connection. `openai` is a kind, and the platform knows how to
talk to it; `openai-work` is a row somebody added. A catalog entry points at the
row, and the factory gets the address and the credential from it.

No foreign key onto `secrets`: the credential is *named* here, exactly as an
integration names one, and a name that outlives the value it points at is the
condition this platform is built to survive - it says "no credential named X"
rather than failing to load the row that mentions it.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("workspace_id", sa.String(length=64), nullable=False, server_default="default"),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("secret_name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column(
            "needs_credential", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_connections_name"),
    )


def downgrade() -> None:
    op.drop_table("connections")
