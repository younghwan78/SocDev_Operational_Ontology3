"""Persist the pre-execution Agent budget plan."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_agent_run_budget_plan"
down_revision: str | None = "0015_attempt_start_checkpoint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column(
            "budget_plan",
            postgresql.JSONB(),
            nullable=True,
        ),
        schema="observable",
    )
    op.execute(
        "UPDATE observable.agent_runs SET budget_plan = jsonb_build_object("
        "'max_logical_calls', 9, 'reserved_logical_calls', 1, "
        "'remaining_logical_calls', 8, 'max_provider_attempts', 12, "
        "'reserved_provider_attempts', 3, 'remaining_provider_attempts', 9, "
        "'max_output_tokens', 20000, 'reserved_output_tokens', 1500, "
        "'remaining_output_tokens', 18500, 'timeout_envelope_seconds', 120, "
        "'maximum_cost_usd', 2.0) WHERE budget_plan IS NULL"
    )
    op.alter_column("agent_runs", "budget_plan", nullable=False, schema="observable")


def downgrade() -> None:
    op.drop_column("agent_runs", "budget_plan", schema="observable")
