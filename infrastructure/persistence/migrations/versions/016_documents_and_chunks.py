"""Phase 15: knowledge the user brought.

Revision ID: 016
Revises: 015
Create Date: 2026-09-08

Two tables and one index, and the reason they are not three columns on
the memory table is ADR 0016: memory has a half-life and a time to live, and a
specification somebody uploaded does not stop being true because nobody opened
it for a fortnight. Storing it in a table whose maintenance job deletes rows by
age would mean the platform quietly throwing away something a person put there
on purpose.

**`chunks.embedding_model` and `embedding_dimension` are the point of the
schema, not decoration.** A vector is only comparable with a query's vector if
the same model produced both. Without these columns, changing the embedding
model - or moving to another store - leaves nobody able to say whether what is
already written can still be compared, and the answer becomes a guess. With
them, a mismatch means re-indexing, which is work; without them, it means
silently comparing numbers that mean different things.

**The vector is a BLOB of float32.** Read on every query and never read by a
person, so a text encoding would be four times the file for no benefit. A
backend with a vector type of its own uses it instead (ADR 0017); this is the
local one, and at one person's scale a cosine over a few thousand rows held in
memory answers in milliseconds without an extension or a daemon.

**The cascade onto `documents` is the one this schema wants.** Everywhere else a
record outlives what it describes - that is why `tool_calls` and `audit_log`
have no foreign keys at all. A chunk is not a record *about* a document; it is
part of one, and a chunk whose document has been deleted is unreachable text
that still answers queries.

The FTS index over chunks is separate from memory's, because the two stores are
separate. Lexical retrieval is kept alongside the vectors rather than replaced
by them: semantic search is what finds "shipping" by the word "delivery", and
lexical search is what still finds an invoice number or an error code.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from infrastructure.persistence import knowledge_fts

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None

STATUSES = ("PENDING", "EXTRACTED", "INDEXED", "FAILED")


def _sqlite() -> bool:
    """Which backend this migration is running against.

    Asked rather than configured: the schema is the same on both, and what is
    not is the text index - FTS5 with triggers on one, a GIN index over
    `to_tsvector` on the other (ADR 0017).
    """
    return op.get_context().dialect.name == "sqlite"

def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("title", sa.String(500), nullable=False),
        # Where it came from, as written: a path on this machine, a URL, or
        # nothing at all for text that was pasted in.
        sa.Column("source", sa.Text(), nullable=False, server_default=""),
        sa.Column("media_type", sa.String(120), nullable=False, server_default=""),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        # Of the extracted text, not of the file: two exports of one page that
        # read the same are one document.
        sa.Column("checksum", sa.String(64), nullable=False, server_default=""),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=False, server_default=""),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "status IN ('" + "','".join(STATUSES) + "')", name="ck_documents_status"
        ),
    )
    op.create_index("ix_documents_workspace", "documents", ["workspace_id", "created_at"])
    op.create_index("ix_documents_checksum", "documents", ["workspace_id", "checksum"])

    op.create_table(
        "chunks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(36),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.String(64), nullable=False, server_default="default"),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.LargeBinary(), nullable=True),
        sa.Column("embedding_model", sa.String(120), nullable=False, server_default=""),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_chunks_ordinal"),
    )
    op.create_index("ix_chunks_document", "chunks", ["document_id", "ordinal"])
    op.create_index("ix_chunks_workspace", "chunks", ["workspace_id"])
    for statement in (
        knowledge_fts.CREATE if _sqlite() else knowledge_fts.CREATE_POSTGRES
    ):
        op.execute(statement)


def downgrade() -> None:
    for statement in knowledge_fts.DROP if _sqlite() else knowledge_fts.DROP_POSTGRES:
        op.execute(statement)
    op.drop_index("ix_chunks_workspace", table_name="chunks")
    op.drop_index("ix_chunks_document", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_documents_checksum", table_name="documents")
    op.drop_index("ix_documents_workspace", table_name="documents")
    op.drop_table("documents")
