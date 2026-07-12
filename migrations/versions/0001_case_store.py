"""Create observable case and append-only audit tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_case_store"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_cases",
        sa.Column("case_id", sa.String(length=80), nullable=False),
        sa.Column("fixture_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("title_ko", sa.String(length=240), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("case_id", name="pk_decision_cases"),
        schema="observable",
    )
    op.create_table(
        "domain_events",
        sa.Column("event_id", sa.String(length=120), nullable=False),
        sa.Column("case_id", sa.String(length=80), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("event_id", name="pk_domain_events"),
        sa.UniqueConstraint("case_id", "aggregate_version", name="uq_event_case_version"),
        schema="audit",
    )
    op.create_index("ix_audit_domain_events_case_id", "domain_events", ["case_id"], schema="audit")
    op.create_table(
        "fixture_import_runs",
        sa.Column("import_id", sa.String(length=120), nullable=False),
        sa.Column("case_id", sa.String(length=80), nullable=False),
        sa.Column("fixture_version", sa.Integer(), nullable=False),
        sa.Column("fixture_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("import_id", name="pk_fixture_import_runs"),
        schema="audit",
    )


def downgrade() -> None:
    op.drop_table("fixture_import_runs", schema="audit")
    op.drop_index("ix_audit_domain_events_case_id", table_name="domain_events", schema="audit")
    op.drop_table("domain_events", schema="audit")
    op.drop_table("decision_cases", schema="observable")
