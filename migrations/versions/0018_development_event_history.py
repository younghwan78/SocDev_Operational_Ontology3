"""Add development event history collections to persisted observable cases."""

from collections.abc import Sequence

from alembic import op

revision: str = "0018_development_event_history"
down_revision: str | None = "0017_decision_action_plan_v2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE observable.decision_cases "
        "SET payload = payload || jsonb_build_object("
        "'development_actions', COALESCE(payload -> 'development_actions', '[]'::jsonb), "
        "'development_events', COALESCE(payload -> 'development_events', '[]'::jsonb)) "
        "WHERE NOT (payload ? 'development_actions') "
        "OR NOT (payload ? 'development_events')"
    )


def downgrade() -> None:
    # This intentionally removes Step 2 collections. Back up non-empty histories first.
    op.execute(
        "UPDATE observable.decision_cases "
        "SET payload = payload - 'development_actions' - 'development_events' "
        "WHERE payload ? 'development_actions' OR payload ? 'development_events'"
    )
