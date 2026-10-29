"""Create initial application-management schema.

Revision ID: 0001_initial_database
Revises:
Create Date: 2026-10-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_database"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "name", sa.String(length=120, collation="NOCASE"), nullable=False
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'inactive')", name="ck_applications_status"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_applications_name"),
    )
    op.create_index("ix_applications_id", "applications", ["id"], unique=False)

    op.create_table(
        "carbon_budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("budget_kg_co2e", sa.Float(), nullable=False),
        sa.Column("warning_threshold_percent", sa.Integer(), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "budget_kg_co2e > 0", name="ck_carbon_budgets_positive"
        ),
        sa.CheckConstraint(
            "warning_threshold_percent BETWEEN 1 AND 100",
            name="ck_carbon_budgets_warning_threshold",
        ),
        sa.CheckConstraint(
            "period IN ('daily', 'weekly', 'monthly')",
            name="ck_carbon_budgets_period",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_carbon_budgets_id", "carbon_budgets", ["id"], unique=False)
    op.create_index(
        "ix_carbon_budgets_application_id",
        "carbon_budgets",
        ["application_id"],
        unique=False,
    )

    op.create_table(
        "workloads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("workload_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('registered', 'pending', 'inactive')",
            name="ck_workloads_status",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workloads_id", "workloads", ["id"], unique=False)
    op.create_index(
        "ix_workloads_application_id", "workloads", ["application_id"], unique=False
    )

    op.create_table(
        "monitoring_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("energy_kwh", sa.Float(), nullable=True),
        sa.Column("emissions_kg_co2e", sa.Float(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "energy_kwh IS NULL OR energy_kwh >= 0",
            name="ck_monitoring_energy_nonnegative",
        ),
        sa.CheckConstraint(
            "emissions_kg_co2e IS NULL OR emissions_kg_co2e >= 0",
            name="ck_monitoring_emissions_nonnegative",
        ),
        sa.CheckConstraint(
            "source_type IN ('simulated', 'estimated', 'measured')",
            name="ck_monitoring_source_type",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monitoring_records_id", "monitoring_records", ["id"], unique=False)
    op.create_index(
        "ix_monitoring_records_application_id",
        "monitoring_records",
        ["application_id"],
        unique=False,
    )

    op.create_table(
        "policy_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('warning', 'throttling', 'suspension', 'recovery', 'other')",
            name="ck_policy_events_type",
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_policy_events_id", "policy_events", ["id"], unique=False)
    op.create_index(
        "ix_policy_events_application_id",
        "policy_events",
        ["application_id"],
        unique=False,
    )

    op.create_table(
        "experiment_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("method", sa.String(length=80), nullable=False),
        sa.Column("results_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_experiment_results_id", "experiment_results", ["id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_experiment_results_id", table_name="experiment_results")
    op.drop_table("experiment_results")
    op.drop_index("ix_policy_events_application_id", table_name="policy_events")
    op.drop_index("ix_policy_events_id", table_name="policy_events")
    op.drop_table("policy_events")
    op.drop_index(
        "ix_monitoring_records_application_id", table_name="monitoring_records"
    )
    op.drop_index("ix_monitoring_records_id", table_name="monitoring_records")
    op.drop_table("monitoring_records")
    op.drop_index("ix_workloads_application_id", table_name="workloads")
    op.drop_index("ix_workloads_id", table_name="workloads")
    op.drop_table("workloads")
    op.drop_index("ix_carbon_budgets_application_id", table_name="carbon_budgets")
    op.drop_index("ix_carbon_budgets_id", table_name="carbon_budgets")
    op.drop_table("carbon_budgets")
    op.drop_index("ix_applications_id", table_name="applications")
    op.drop_table("applications")
