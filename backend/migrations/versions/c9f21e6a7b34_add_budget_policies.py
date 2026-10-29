"""Add carbon-budget policy configuration.

Revision ID: c9f21e6a7b34
Revises: a3616f13edf7
Create Date: 2026-10-20
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c9f21e6a7b34"
down_revision: Union[str, None] = "a3616f13edf7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "budget_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("budget_kg_co2e", sa.Float(), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("warning_threshold_percent", sa.Float(), nullable=False),
        sa.Column("critical_threshold_percent", sa.Float(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "budget_kg_co2e > 0", name="ck_budget_policies_positive"
        ),
        sa.CheckConstraint(
            "warning_threshold_percent > 0",
            name="ck_budget_policies_warning_positive",
        ),
        sa.CheckConstraint(
            "critical_threshold_percent > warning_threshold_percent",
            name="ck_budget_policies_threshold_order",
        ),
        sa.CheckConstraint(
            "period IN ('daily', 'weekly', 'monthly')",
            name="ck_budget_policies_period",
        ),
        sa.CheckConstraint(
            "action IN ('monitor', 'warn', 'recommend_throttle')",
            name="ck_budget_policies_action",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_budget_policies_id", "budget_policies", ["id"])
    op.create_index(
        "ix_budget_policies_application_id",
        "budget_policies",
        ["application_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_budget_policies_application_id", table_name="budget_policies"
    )
    op.drop_index("ix_budget_policies_id", table_name="budget_policies")
    op.drop_table("budget_policies")
