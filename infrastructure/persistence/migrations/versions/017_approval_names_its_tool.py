"""Phase 16: the approval says which tool it is about.

Revision ID: 017
Revises: 016
Create Date: 2026-09-09

`approvals.action` is the tool rendered with its arguments - the one line a
person reads before deciding - and it was the only thing the row said about what
was being asked. Anything that has to decide *by tool* rather than by prose had
to read the name back out of that line, which is parsing our own formatting: the
habit the platform refuses everywhere else, and for the same reason.

`audit_log` has carried `tool` since Phase 10, so the asymmetry was already
visible in the two tables people read together. This closes it.

Existing rows keep an empty name. Backfilling would mean parsing the very string
this column exists to stop anyone parsing, and a blank is honest: those questions
were asked before the row could say.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "approvals",
        sa.Column("tool", sa.String(length=64), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("approvals", "tool")
