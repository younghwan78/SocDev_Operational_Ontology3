"""Allow provider attempts to be checkpointed before completion."""

from collections.abc import Sequence

from alembic import op

revision: str = "0015_attempt_start_checkpoint"
down_revision: str | None = "0014_persist_sim_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("agent_attempts", "completed_at", nullable=True, schema="audit")
    op.execute("GRANT UPDATE ON audit.agent_attempts TO soc_ot_runtime")


def downgrade() -> None:
    op.execute("REVOKE UPDATE ON audit.agent_attempts FROM soc_ot_runtime")
    op.execute(
        "UPDATE audit.agent_attempts SET completed_at = started_at "
        "WHERE completed_at IS NULL"
    )
    op.alter_column("agent_attempts", "completed_at", nullable=False, schema="audit")
