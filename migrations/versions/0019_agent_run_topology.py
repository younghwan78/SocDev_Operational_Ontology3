"""Persist the selected topology for every dossier run."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_agent_run_topology"
down_revision: str | None = "0018_development_event_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent_runs",
        sa.Column("topology", sa.String(length=2), nullable=True),
        schema="observable",
    )
    # Runs created before Step 5 always executed the hard-coded B3 path.
    op.execute(
        "UPDATE observable.agent_runs SET topology = 'B3' "
        "WHERE run_kind = 'dossier' AND topology IS NULL"
    )
    op.create_check_constraint(
        "ck_agent_runs_topology_by_kind",
        "agent_runs",
        "(run_kind = 'role_review' AND topology IS NULL) OR "
        "(run_kind = 'dossier' AND topology IN ('B1', 'B2', 'B3'))",
        schema="observable",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_agent_runs_topology_by_kind",
        "agent_runs",
        schema="observable",
        type_="check",
    )
    op.drop_column("agent_runs", "topology", schema="observable")
