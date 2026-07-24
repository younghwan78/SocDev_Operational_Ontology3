"""Persist evaluation-only pre-advice and post-advice responses."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0021_decision_responses"
down_revision: str | None = "0020_development_projects"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_evaluation_responses",
        sa.Column("response_id", sa.String(length=120), nullable=False),
        sa.Column("case_id", sa.String(length=80), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=False),
        sa.Column("participant_kind", sa.String(length=40), nullable=False),
        sa.Column("interpretation", sa.String(length=80), nullable=False),
        sa.Column(
            "initial_response",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "advice_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "final_response",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("initial_key", sa.String(length=120), nullable=False),
        sa.Column("initial_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("reveal_key", sa.String(length=120), nullable=True),
        sa.Column("reveal_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("final_key", sa.String(length=120), nullable=True),
        sa.Column("final_fingerprint", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("response_id"),
        sa.UniqueConstraint(
            "case_id",
            "actor_id",
            name="uq_decision_evaluation_response_actor",
        ),
        sa.UniqueConstraint(
            "initial_key", name="uq_decision_response_initial_key"
        ),
        sa.UniqueConstraint("reveal_key", name="uq_decision_response_reveal_key"),
        sa.UniqueConstraint("final_key", name="uq_decision_response_final_key"),
        schema="observable",
    )
    op.create_index(
        op.f("ix_observable_decision_evaluation_responses_case_id"),
        "decision_evaluation_responses",
        ["case_id"],
        unique=False,
        schema="observable",
    )


def downgrade() -> None:
    # Back up evaluation-only response records before downgrading.
    op.drop_index(
        op.f("ix_observable_decision_evaluation_responses_case_id"),
        table_name="decision_evaluation_responses",
        schema="observable",
    )
    op.drop_table("decision_evaluation_responses", schema="observable")
