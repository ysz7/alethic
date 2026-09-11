"""Phase 17: credentials live in the store, encrypted.

Revision ID: 018
Revises: 017
Create Date: 2026-09-09

Until now a credential was a JSON file with mode 0600 beside the database, and
that was the right size while the only thing the platform stored was a token for
an integration somebody set up by hand on their own laptop.

It stops being the right size the moment the backend is something you deploy.
A container restarts with an empty filesystem and a database that survived, so a
file is the half of the state that quietly disappears; and the operating
system's own keychain, which would be the stronger answer on a laptop, does not
exist on the server the same backend has to run on.

So the row holds AES-GCM ciphertext and the key that opens it is never in the
database: `PROMETHEUS_MASTER_KEY` on a deployment, a 0600 file on a desktop. A
backup, a dump and `storage-migrate` therefore carry something unreadable rather
than a set of live API keys - which is the only thing that makes storing them
here better than storing them beside.

The name is the primary key. There is no `id`: everything in the platform that
needs a credential names it, and two rows answering to one name would make
"which key does this connection use" a question with two answers.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "secrets",
        sa.Column("name", sa.String(length=120), primary_key=True),
        sa.Column(
            "workspace_id", sa.String(length=64), nullable=False, server_default="default"
        ),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("secrets")
