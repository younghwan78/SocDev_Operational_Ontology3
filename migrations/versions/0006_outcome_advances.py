"""Persist logical simulation state and idempotent outcome advances."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_outcome_advances"
down_revision: str | None = "0005_agent_logical_steps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulation_states",
        sa.Column("case_id", sa.String(80), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("case_id", name="pk_simulation_states"),
        schema="observable",
    )
    op.create_table(
        "outcome_advances",
        sa.Column("advance_id", sa.String(120), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("command_fingerprint", sa.String(64), nullable=False),
        sa.Column("case_id", sa.String(80), nullable=False),
        sa.Column("decision_id", sa.String(80), nullable=False),
        sa.Column("from_step", sa.Integer(), nullable=False),
        sa.Column("to_step", sa.Integer(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("advance_id", name="pk_outcome_advances"),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_outcome_advances_idempotency_key"
        ),
        schema="hidden",
    )
    op.create_index(
        "ix_hidden_outcome_advances_case_id",
        "outcome_advances",
        ["case_id"],
        schema="hidden",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hidden_outcome_advances_case_id",
        table_name="outcome_advances",
        schema="hidden",
    )
    op.drop_table("outcome_advances", schema="hidden")
    op.drop_table("simulation_states", schema="observable")
