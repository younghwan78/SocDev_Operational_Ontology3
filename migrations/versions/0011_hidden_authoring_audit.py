"""Audit every explicit hidden-fixture authoring access."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_hidden_authoring_audit"
down_revision: str | None = "0010_command_audit_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hidden_authoring_audits",
        sa.Column("audit_id", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(120), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("case_id", sa.String(80), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("audit_id", name="pk_hidden_authoring_audits"),
        schema="audit",
    )


def downgrade() -> None:
    op.drop_table("hidden_authoring_audits", schema="audit")
