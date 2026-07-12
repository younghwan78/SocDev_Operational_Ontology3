"""Create outcome-only hidden world tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_hidden_outcomes"
down_revision: str | None = "0002_agent_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hidden_cases",
        sa.Column("case_id", sa.String(80), nullable=False),
        sa.Column("fixture_version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("case_id", name="pk_hidden_cases"),
        schema="hidden",
    )
    op.create_table(
        "outcome_evaluations",
        sa.Column("evaluation_id", sa.String(120), nullable=False),
        sa.Column("case_id", sa.String(80), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("evaluation_id", name="pk_outcome_evaluations"),
        schema="hidden",
    )
    op.create_index(
        "ix_hidden_outcome_evaluations_case_id",
        "outcome_evaluations",
        ["case_id"],
        schema="hidden",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hidden_outcome_evaluations_case_id",
        table_name="outcome_evaluations",
        schema="hidden",
    )
    op.drop_table("outcome_evaluations", schema="hidden")
    op.drop_table("hidden_cases", schema="hidden")
