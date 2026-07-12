"""Record requested/returned model and versioned prompt policy metadata."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_run_repro_metadata"
down_revision: str | None = "0006_outcome_advances"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("agent_runs", "model", new_column_name="requested_model", schema="observable")
    op.add_column(
        "agent_runs", sa.Column("returned_model", sa.String(100)), schema="observable"
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "contract_version",
            sa.String(80),
            nullable=False,
            server_default="role-review.v1",
        ),
        schema="observable",
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "prompt_bundle_version",
            sa.String(80),
            nullable=False,
            server_default="prompts.v1",
        ),
        schema="observable",
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "prompt_bundle_hash",
            sa.String(64),
            nullable=False,
            server_default="legacy-unavailable",
        ),
        schema="observable",
    )
    op.add_column(
        "agent_runs",
        sa.Column(
            "policy_version",
            sa.String(80),
            nullable=False,
            server_default="decision-policy.v1",
        ),
        schema="observable",
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "policy_version", schema="observable")
    op.drop_column("agent_runs", "prompt_bundle_hash", schema="observable")
    op.drop_column("agent_runs", "prompt_bundle_version", schema="observable")
    op.drop_column("agent_runs", "contract_version", schema="observable")
    op.drop_column("agent_runs", "returned_model", schema="observable")
    op.alter_column("agent_runs", "requested_model", new_column_name="model", schema="observable")
