"""Add indexes for time-bounded workload-run analytics.

Revision ID: d47e1b9c2a63
Revises: c9f21e6a7b34
Create Date: 2026-10-20
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d47e1b9c2a63"
down_revision: Union[str, None] = "c9f21e6a7b34"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_workload_runs_status_completed_at",
        "workload_runs",
        ["status", "completed_at"],
    )
    op.create_index(
        "ix_workload_runs_application_status_completed_at",
        "workload_runs",
        ["application_id", "status", "completed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workload_runs_application_status_completed_at",
        table_name="workload_runs",
    )
    op.drop_index(
        "ix_workload_runs_status_completed_at",
        table_name="workload_runs",
    )
