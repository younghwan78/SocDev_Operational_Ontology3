"""Persist development-project.v1 runtime aggregates."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_development_projects"
down_revision: str | None = "0019_agent_run_topology"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "development_projects",
        sa.Column("project_id", sa.String(length=80), nullable=False),
        sa.Column("fixture_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_version", sa.Integer(), nullable=False),
        sa.Column("current_step", sa.Integer(), nullable=False),
        sa.Column("lifecycle_stage", sa.String(length=40), nullable=False),
        sa.Column("title_ko", sa.String(length=240), nullable=False),
        sa.Column("fixture_hash", sa.String(length=64), nullable=False),
        sa.Column("contract_version", sa.String(length=80), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.PrimaryKeyConstraint("project_id"),
        schema="observable",
    )


def downgrade() -> None:
    # Back up imported project aggregates before downgrading.
    op.drop_table("development_projects", schema="observable")
