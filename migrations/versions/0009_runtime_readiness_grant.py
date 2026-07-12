"""Allow runtime health checks to verify the applied schema revision."""

from collections.abc import Sequence

from alembic import op

revision: str = "0009_runtime_readiness_grant"
down_revision: str | None = "0008_dossier_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "GRANT SELECT ON TABLE public.alembic_version "
        "TO soc_ot_runtime, soc_ot_outcome"
    )


def downgrade() -> None:
    op.execute(
        "REVOKE SELECT ON TABLE public.alembic_version "
        "FROM soc_ot_runtime, soc_ot_outcome"
    )
