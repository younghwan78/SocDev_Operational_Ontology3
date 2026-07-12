"""Distinguish single-role and routed Dossier runs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_dossier_runs"
down_revision: str | None = "0007_run_repro_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column(
            "run_kind",
            sa.String(40),
            nullable=False,
            server_default="role_review",
        ),
        schema="observable",
    )


def downgrade() -> None:
    op.drop_column("agent_runs", "run_kind", schema="observable")
