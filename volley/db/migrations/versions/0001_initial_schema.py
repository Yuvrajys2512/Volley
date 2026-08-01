"""initial schema — users, gmail_accounts, processed_messages, corpus_entries
(pgvector), draft_log, jobs

Revision ID: 0001
Revises:
Create Date: 2026-08-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql as pg

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column(
            "id",
            pg.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("confidence_threshold", sa.Float(), nullable=True),
    )

    op.create_table(
        "gmail_accounts",
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            primary_key=True,
        ),
        sa.Column("refresh_token_enc", sa.LargeBinary(), nullable=False),
        sa.Column("granted_scopes", pg.ARRAY(sa.String()), nullable=False),
        sa.Column("last_history_id", sa.BigInteger(), nullable=True),
        sa.Column("watch_status", sa.String(), nullable=False, server_default="ok"),
        sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "processed_messages",
        sa.Column("user_id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", sa.String(), primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "corpus_entries",
        sa.Column("user_id", pg.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", sa.String(), primary_key=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False, server_default=""),
        sa.Column("sent_to", sa.Text(), nullable=False, server_default=""),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
    )
    # autogenerate doesn't know pgvector index syntax — hand-written HNSW index.
    op.execute(
        "CREATE INDEX corpus_entries_embedding_hnsw_idx "
        "ON corpus_entries USING hnsw (embedding vector_cosine_ops)"
    )
    op.create_index("corpus_entries_user_id_idx", "corpus_entries", ["user_id"])

    op.create_table(
        "draft_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("gmail_draft_id", sa.String(), nullable=False),
        sa.Column("intent", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("draft_log_user_id_idx", "draft_log", ["user_id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", pg.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_after", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("jobs_kind_status_idx", "jobs", ["kind", "status"])


def downgrade() -> None:
    op.drop_table("jobs")
    op.drop_index("draft_log_user_id_idx", table_name="draft_log")
    op.drop_table("draft_log")
    op.drop_index("corpus_entries_user_id_idx", table_name="corpus_entries")
    op.execute("DROP INDEX IF EXISTS corpus_entries_embedding_hnsw_idx")
    op.drop_table("corpus_entries")
    op.drop_table("processed_messages")
    op.drop_table("gmail_accounts")
    op.drop_table("users")
