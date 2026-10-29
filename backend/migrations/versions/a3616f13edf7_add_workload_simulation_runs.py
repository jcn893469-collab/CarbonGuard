"""add workload simulation runs

Revision ID: a3616f13edf7
Revises: 0001_initial_database
Create Date: 2026-10-20 09:07:00.611517

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a3616f13edf7'
down_revision: Union[str, None] = '0001_initial_database'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workload_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("workload_id", sa.Integer(), nullable=False),
        sa.Column("workload_type", sa.String(length=20), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("average_power_w", sa.Float(), nullable=False),
        sa.Column("carbon_intensity_g_per_kwh", sa.Float(), nullable=False),
        sa.Column("cpu_utilization_percent", sa.Float(), nullable=True),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("parameters_json", sa.JSON(), nullable=False),
        sa.Column("profile_json", sa.JSON(), nullable=False),
        sa.Column("energy_kwh", sa.Float(), nullable=False),
        sa.Column("emissions_kg_co2e", sa.Float(), nullable=False),
        sa.Column("estimation_method", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("simulation_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source IN ('simulated', 'measured')", name="ck_workload_runs_source"
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'failed')", name="ck_workload_runs_status"
        ),
        sa.CheckConstraint("average_power_w >= 0", name="ck_workload_runs_power"),
        sa.CheckConstraint(
            "carbon_intensity_g_per_kwh >= 0",
            name="ck_workload_runs_carbon_intensity",
        ),
        sa.CheckConstraint("duration_seconds > 0", name="ck_workload_runs_duration"),
        sa.CheckConstraint(
            "emissions_kg_co2e >= 0", name="ck_workload_runs_emissions"
        ),
        sa.CheckConstraint("energy_kwh >= 0", name="ck_workload_runs_energy"),
        sa.ForeignKeyConstraint(
            ["application_id"], ["applications.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workload_id"], ["workloads.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table('workload_runs', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_workload_runs_application_id"),
            ["application_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_workload_runs_workload_id"),
            ["workload_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table('workload_runs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_workload_runs_workload_id'))
        batch_op.drop_index(batch_op.f('ix_workload_runs_application_id'))

    op.drop_table('workload_runs')
