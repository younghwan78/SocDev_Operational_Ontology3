"""Persist simulated Chair commands with idempotency."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_persist_sim_decisions"
down_revision: str | None = "0013_persist_evaluations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulated_decisions",
        sa.Column("command_id", sa.String(120), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("command_fingerprint", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(80), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("review_run_id", sa.String(80), nullable=False),
        sa.Column("actor_id", sa.String(120), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("command_id", name="pk_simulated_decisions"),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_simulated_decisions_idempotency_key"
        ),
        schema="observable",
    )
    op.create_index(
        "ix_observable_simulated_decisions_case_id",
        "simulated_decisions",
        ["case_id"],
        schema="observable",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_observable_simulated_decisions_case_id",
        table_name="simulated_decisions",
        schema="observable",
    )
    op.drop_table("simulated_decisions", schema="observable")
