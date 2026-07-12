"""Complete worker lease, retry, and cancellation timestamps."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_worker_lease_contract"
down_revision: str | None = "0003_hidden_outcomes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("agent_runs", "attempt", new_column_name="attempt_no", schema="observable")
    op.add_column(
        "agent_runs",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        schema="observable",
    )
    op.add_column(
        "agent_runs",
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        schema="observable",
    )
    op.add_column(
        "agent_runs",
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        schema="observable",
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "cancel_requested_at", schema="observable")
    op.drop_column("agent_runs", "next_retry_at", schema="observable")
    op.drop_column("agent_runs", "heartbeat_at", schema="observable")
    op.alter_column("agent_runs", "attempt_no", new_column_name="attempt", schema="observable")
