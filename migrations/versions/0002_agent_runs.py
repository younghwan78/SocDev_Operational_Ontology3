"""Create durable agent run queue and event stream."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_agent_runs"
down_revision: str | None = "0001_case_store"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("run_id", sa.String(80), nullable=False),
        sa.Column("case_id", sa.String(80), nullable=False),
        sa.Column("packet_hash", sa.String(64), nullable=False),
        sa.Column("role_id", sa.String(80), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("lease_owner", sa.String(120), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("run_id", name="pk_agent_runs"),
        sa.UniqueConstraint("idempotency_key", name="uq_agent_runs_idempotency_key"),
        schema="observable",
    )
    op.create_index("ix_observable_agent_runs_case_id", "agent_runs", ["case_id"], schema="observable")
    op.create_table(
        "agent_run_events",
        sa.Column("event_id", sa.String(120), nullable=False),
        sa.Column("run_id", sa.String(80), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("event_id", name="pk_agent_run_events"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_agent_run_events_run_sequence"),
        schema="audit",
    )
    op.create_index("ix_audit_agent_run_events_run_id", "agent_run_events", ["run_id"], schema="audit")


def downgrade() -> None:
    op.drop_index("ix_audit_agent_run_events_run_id", table_name="agent_run_events", schema="audit")
    op.drop_table("agent_run_events", schema="audit")
    op.drop_index("ix_observable_agent_runs_case_id", table_name="agent_runs", schema="observable")
    op.drop_table("agent_runs", schema="observable")
