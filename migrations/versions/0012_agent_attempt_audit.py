"""Persist one redacted audit row for every provider attempt."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_agent_attempt_audit"
down_revision: str | None = "0011_hidden_authoring_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_attempts",
        sa.Column("attempt_id", sa.String(120), nullable=False),
        sa.Column("run_id", sa.String(80), nullable=False),
        sa.Column("case_id", sa.String(80), nullable=False),
        sa.Column("role_id", sa.String(80), nullable=False),
        sa.Column("review_round", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("requested_model", sa.String(100), nullable=False),
        sa.Column("returned_model", sa.String(100), nullable=True),
        sa.Column("prompt_bundle_version", sa.String(80), nullable=False),
        sa.Column("policy_version", sa.String(80), nullable=False),
        sa.Column("contract_version", sa.String(80), nullable=False),
        sa.Column("observable_packet_hash", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("estimated_cost_usd", sa.Float(), server_default="0", nullable=False),
        sa.Column("retry_reason", sa.String(100), nullable=True),
        sa.Column("validation_result", sa.String(240), nullable=False),
        sa.Column("final_status", sa.String(40), nullable=False),
        sa.PrimaryKeyConstraint("attempt_id", name="pk_agent_attempts"),
        schema="audit",
    )
    op.create_index(
        "ix_audit_agent_attempts_run_id",
        "agent_attempts",
        ["run_id"],
        schema="audit",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_audit_agent_attempts_run_id",
        table_name="agent_attempts",
        schema="audit",
    )
    op.drop_table("agent_attempts", schema="audit")
