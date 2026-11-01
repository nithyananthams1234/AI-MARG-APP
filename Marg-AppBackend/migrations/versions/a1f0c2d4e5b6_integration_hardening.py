"""integration hardening: whatsapp table, ownership columns, refresh tokens,
missing mentor_task constraints

Additive and backward compatible. No existing data is removed.

* whatsapp_messages: revision 6889a3a6e20d was generated empty (``pass``), so
  the table was never created. It is created here instead of editing the
  already-applied revision.
* school_visits.mentor_id / mentor_tasks.mentor_id: nullable owner columns,
  backfilled from created_by.
* mentor_tasks: status/priority CHECK constraints that exist on the model but
  were missing from 5d20ae385e19.
* refresh_tokens: server-side refresh-token rotation and revocation.

Revision ID: a1f0c2d4e5b6
Revises: 6889a3a6e20d
Create Date: 2026-10-31 21:30:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1f0c2d4e5b6"
down_revision: Union[str, Sequence[str], None] = "6889a3a6e20d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- whatsapp_messages -------------------------------------------------
    op.create_table(
        "whatsapp_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("recipient", sa.String(length=30), nullable=False),
        sa.Column("message_type", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("template_name", sa.String(length=255), nullable=True),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
        sa.UniqueConstraint("provider_message_id"),
    )
    op.create_index("ix_whatsapp_messages_status", "whatsapp_messages", ["status"])
    op.create_index("ix_whatsapp_messages_recipient", "whatsapp_messages", ["recipient"])
    op.create_index(op.f("ix_whatsapp_messages_created_by"), "whatsapp_messages", ["created_by"])

    # --- ownership columns -------------------------------------------------
    for table in ("school_visits", "mentor_tasks"):
        op.add_column(table, sa.Column("mentor_id", postgresql.UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_mentor_id_users", table, "users", ["mentor_id"], ["id"], ondelete="SET NULL"
        )
        op.create_index(op.f(f"ix_{table}_mentor_id"), table, ["mentor_id"])
        op.execute(f"UPDATE {table} SET mentor_id = created_by WHERE mentor_id IS NULL")

    # --- mentor_tasks constraints missing from 5d20ae385e19 -----------------
    op.create_check_constraint(
        "ck_mentor_tasks_status",
        "mentor_tasks",
        "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_mentor_tasks_priority",
        "mentor_tasks",
        "priority IN ('low', 'medium', 'high', 'critical')",
    )

    # --- refresh_tokens ----------------------------------------------------
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("device_label", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"])
    op.create_index(op.f("ix_refresh_tokens_family_id"), "refresh_tokens", ["family_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_tokens_family_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_constraint("ck_mentor_tasks_priority", "mentor_tasks", type_="check")
    op.drop_constraint("ck_mentor_tasks_status", "mentor_tasks", type_="check")
    for table in ("mentor_tasks", "school_visits"):
        op.drop_index(op.f(f"ix_{table}_mentor_id"), table_name=table)
        op.drop_constraint(f"fk_{table}_mentor_id_users", table, type_="foreignkey")
        op.drop_column(table, "mentor_id")
    op.drop_index(op.f("ix_whatsapp_messages_created_by"), table_name="whatsapp_messages")
    op.drop_index("ix_whatsapp_messages_recipient", table_name="whatsapp_messages")
    op.drop_index("ix_whatsapp_messages_status", table_name="whatsapp_messages")
    op.drop_table("whatsapp_messages")
