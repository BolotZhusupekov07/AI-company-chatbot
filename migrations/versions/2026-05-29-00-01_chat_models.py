"""chat models

Revision ID: 202605290001
Revises: None
Create Date: 2026-05-29 00:01:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202605290001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "chats",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("user_email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("chats_pkey")),
    )
    op.create_index(op.f("chats_user_email_idx"), "chats", ["user_email"], unique=False)
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=True),
        sa.Column("chat_id", sa.UUID(), nullable=False),
        sa.Column("role", postgresql.ENUM("USER", "AGENT", name="chat_message_role"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", postgresql.ENUM("EN", "RU", "UK", name="chat_message_lang"), nullable=False),
        sa.Column("processing_time_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], name=op.f("chat_messages_chat_id_fkey")),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["chat_messages.id"],
            name=op.f("chat_messages_message_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("chat_messages_pkey")),
    )
    op.create_index(op.f("chat_messages_chat_id_idx"), "chat_messages", ["chat_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("chat_messages_chat_id_idx"), table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_index(op.f("chats_user_email_idx"), table_name="chats")
    op.drop_table("chats")
    op.execute("DROP TYPE IF EXISTS chat_message_role")
    op.execute("DROP TYPE IF EXISTS chat_message_lang")
