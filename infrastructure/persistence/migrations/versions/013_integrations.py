"""Phase 14: external services the user connected.

Revision ID: 013
Revises: 012
Create Date: 2026-09-08

One table, and the interesting part is which of its columns the platform trusts.

Three of them are the trust boundary and all three are written on this machine
rather than by the service being described (ADR 0015). `effects` says what each
of its tools does to the world and is the only thing the policy layer reads - a
server does not classify its own actions. `capabilities` is what an employee
granted this integration may thereby be asked to do, in the platform's own
closed vocabulary. `discovered` is what the server last said it offers, cached
here so that listing tools, checking an employee declaration or planning a task
never has to start a subprocess; the server is reached when a call is made and
not before.

**No credential is stored.** `configuration` holds how to reach the service and
`secret_names` holds the names of the secrets it needs; the values are resolved
at the moment of a call, from wherever secrets actually live, and never land in
a row, a log or a prompt (§74).

**Unique on (workspace, name).** The name prefixes every tool the integration
contributes, so two integrations called `gmail` would make `gmail.send_message`
ambiguous - and an employee declaration naming it would silently mean either
one. That has to be impossible rather than discouraged.

**No foreign keys, and removal keeps history.** Disconnecting an integration
deletes this row and nothing else: the `tool_calls` and `audit_log` entries for
what it did stay, for the reason those tables have never had foreign keys - a
record outlives what it describes, and clearing a setup must not erase what was
done to the machine.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="MCP"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DISCONNECTED"),
        # How to reach it. Shape is the transport's business: a command and its
        # arguments for stdio, a URL for anything else that arrives later.
        sa.Column("configuration", sa.JSON(), nullable=False, server_default="{}"),
        # Tool name to Effect. The local classification, and the whole of it.
        sa.Column("effects", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default="[]"),
        # Names only. A value never appears in this table.
        sa.Column("secret_names", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("discovered", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workspace_id", "name", name="uq_integrations_name"),
        sa.CheckConstraint(
            "kind IN ('MCP', 'NATIVE')",
            name="ck_integrations_kind",
        ),
        sa.CheckConstraint(
            "status IN ('DISCONNECTED', 'CONFIGURING', 'CONNECTING', 'CONNECTED', "
            "'DISCOVERING', 'READY', 'CONNECTION_FAILED', 'AUTHENTICATION_REQUIRED', "
            "'CONFIGURATION_INVALID', 'UNAVAILABLE', 'DISABLED')",
            name="ck_integrations_status",
        ),
    )
    # What the runtime asks on start-up: everything switched on here, in the
    # order a person would read it.
    op.create_index(
        "ix_integrations_workspace", "integrations", ["workspace_id", "enabled", "name"]
    )


def downgrade() -> None:
    op.drop_index("ix_integrations_workspace", table_name="integrations")
    op.drop_table("integrations")
