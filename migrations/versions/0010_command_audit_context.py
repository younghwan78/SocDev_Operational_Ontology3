"""Persist application-resolved actor context for commands."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_command_audit_context"
down_revision: str | None = "0009_runtime_readiness_grant"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    actor = sa.Column(
        "actor_id",
        sa.String(120),
        nullable=False,
        server_default="local-home-reviewer",
    )
    op.add_column("agent_runs", actor, schema="observable")
    op.add_column(
        "domain_events",
        sa.Column(
            "actor_id",
            sa.String(120),
            nullable=False,
            server_default="local-system",
        ),
        schema="audit",
    )
    op.add_column(
        "outcome_advances",
        sa.Column(
            "actor_id",
            sa.String(120),
            nullable=False,
            server_default="local-home-reviewer",
        ),
        schema="hidden",
    )


def downgrade() -> None:
    op.drop_column("outcome_advances", "actor_id", schema="hidden")
    op.drop_column("domain_events", "actor_id", schema="audit")
    op.drop_column("agent_runs", "actor_id", schema="observable")
