"""Store at most one accepted output for each logical Agent step."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_agent_logical_steps"
down_revision: str | None = "0004_worker_lease_contract"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_run_steps",
        sa.Column("step_id", sa.String(160), nullable=False),
        sa.Column("run_id", sa.String(80), nullable=False),
        sa.Column("step_kind", sa.String(40), nullable=False),
        sa.Column("role_id", sa.String(80), nullable=False),
        sa.Column("review_round", sa.Integer(), nullable=False),
        sa.Column("normalized_output", postgresql.JSONB(), nullable=False),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("step_id", name="pk_agent_run_steps"),
        sa.UniqueConstraint(
            "run_id",
            "step_kind",
            "role_id",
            "review_round",
            name="uq_agent_run_steps_logical_step",
        ),
        schema="observable",
    )
    op.create_index(
        "ix_observable_agent_run_steps_run_id",
        "agent_run_steps",
        ["run_id"],
        schema="observable",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_observable_agent_run_steps_run_id",
        table_name="agent_run_steps",
        schema="observable",
    )
    op.drop_table("agent_run_steps", schema="observable")
