"""Make outcome evaluation commands durable and idempotent."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_persist_evaluations"
down_revision: str | None = "0012_agent_attempt_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outcome_evaluations",
        sa.Column("idempotency_key", sa.String(120), nullable=True),
        schema="hidden",
    )
    op.add_column(
        "outcome_evaluations",
        sa.Column("command_fingerprint", sa.String(64), nullable=True),
        schema="hidden",
    )
    op.add_column(
        "outcome_evaluations",
        sa.Column("aggregate_version", sa.Integer(), nullable=True),
        schema="hidden",
    )
    op.add_column(
        "outcome_evaluations",
        sa.Column("actor_id", sa.String(120), nullable=True),
        schema="hidden",
    )
    op.execute(
        "UPDATE hidden.outcome_evaluations SET "
        "idempotency_key = evaluation_id, "
        "command_fingerprint = repeat('0', 64), "
        "aggregate_version = 0, actor_id = 'migration' "
        "WHERE idempotency_key IS NULL"
    )
    for column in (
        "idempotency_key",
        "command_fingerprint",
        "aggregate_version",
        "actor_id",
    ):
        op.alter_column(
            "outcome_evaluations", column, nullable=False, schema="hidden"
        )
    op.create_unique_constraint(
        "uq_outcome_evaluations_idempotency_key",
        "outcome_evaluations",
        ["idempotency_key"],
        schema="hidden",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_outcome_evaluations_idempotency_key",
        "outcome_evaluations",
        type_="unique",
        schema="hidden",
    )
    for column in (
        "actor_id",
        "aggregate_version",
        "command_fingerprint",
        "idempotency_key",
    ):
        op.drop_column("outcome_evaluations", column, schema="hidden")
