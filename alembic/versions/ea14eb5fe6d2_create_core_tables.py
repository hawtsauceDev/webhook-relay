"""create core tables

Revision ID: ea14eb5fe6d2
Revises: 
Create Date: 2026-09-17 22:24:25.150580

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ea14eb5fe6d2'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("target_url", sa.String, nullable=False),
        # Single-column index for fast subscriber lookup by event type
        sa.Column("event_type", sa.String, nullable=False, index=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True),
        # Single-column index for querying/filtering events by type
        sa.Column("event_type", sa.String, nullable=False, index=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    op.create_table(
        "deliveries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("event_id", sa.Integer, sa.ForeignKey("events.id"), nullable=False, index=True),
        sa.Column("subscription_id", sa.Integer, sa.ForeignKey("subscriptions.id"), nullable=False, index=True),
        sa.Column("status", sa.String, nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False)
    )

    op.create_table(
        "delivery_attempts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("delivery_id", sa.Integer, sa.ForeignKey("deliveries.id"), nullable=False),
        sa.Column("attempted_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("response_status", sa.Integer, nullable=True),
        sa.Column("error", sa.String, nullable=True)
    )


def downgrade() -> None:
    op.drop_table("delivery_attempts")
    op.drop_table("deliveries")
    op.drop_table("events")
    op.drop_table("subscriptions")
