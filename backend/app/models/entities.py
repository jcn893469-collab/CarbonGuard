"""Persistent application-management and audit entities."""

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'inactive')", name="ck_applications_status"),
        UniqueConstraint("name", name="uq_applications_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120, collation="NOCASE"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now, nullable=False
    )

    budgets: Mapped[list["CarbonBudget"]] = relationship(
        back_populates="application", passive_deletes="all"
    )
    budget_policy: Mapped["BudgetPolicy | None"] = relationship(
        back_populates="application", passive_deletes="all", uselist=False
    )
    workloads: Mapped[list["Workload"]] = relationship(
        back_populates="application", passive_deletes="all"
    )
    monitoring_records: Mapped[list["MonitoringRecord"]] = relationship(
        back_populates="application", passive_deletes="all"
    )
    policy_events: Mapped[list["PolicyEvent"]] = relationship(
        back_populates="application", passive_deletes="all"
    )
    workload_runs: Mapped[list["WorkloadRun"]] = relationship(
        back_populates="application", passive_deletes="all"
    )


class CarbonBudget(Base):
    __tablename__ = "carbon_budgets"
    __table_args__ = (
        CheckConstraint("budget_kg_co2e > 0", name="ck_carbon_budgets_positive"),
        CheckConstraint(
            "warning_threshold_percent BETWEEN 1 AND 100",
            name="ck_carbon_budgets_warning_threshold",
        ),
        CheckConstraint(
            "period IN ('daily', 'weekly', 'monthly')",
            name="ck_carbon_budgets_period",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    budget_kg_co2e: Mapped[float] = mapped_column(Float, nullable=False)
    warning_threshold_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now, nullable=False
    )

    application: Mapped[Application] = relationship(back_populates="budgets")


class BudgetPolicy(Base):
    __tablename__ = "budget_policies"
    __table_args__ = (
        CheckConstraint("budget_kg_co2e > 0", name="ck_budget_policies_positive"),
        CheckConstraint(
            "warning_threshold_percent > 0",
            name="ck_budget_policies_warning_positive",
        ),
        CheckConstraint(
            "critical_threshold_percent > warning_threshold_percent",
            name="ck_budget_policies_threshold_order",
        ),
        CheckConstraint(
            "period IN ('daily', 'weekly', 'monthly')",
            name="ck_budget_policies_period",
        ),
        CheckConstraint(
            "action IN ('monitor', 'warn', 'recommend_throttle')",
            name="ck_budget_policies_action",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    budget_kg_co2e: Mapped[float] = mapped_column(Float, nullable=False)
    period: Mapped[str] = mapped_column(String(16), nullable=False)
    warning_threshold_percent: Mapped[float] = mapped_column(
        Float, nullable=False, default=80
    )
    critical_threshold_percent: Mapped[float] = mapped_column(
        Float, nullable=False, default=95
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    action: Mapped[str] = mapped_column(String(24), nullable=False, default="warn")
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now, nullable=False
    )

    application: Mapped[Application] = relationship(back_populates="budget_policy")


class Workload(Base):
    __tablename__ = "workloads"
    __table_args__ = (
        CheckConstraint(
            "status IN ('registered', 'pending', 'inactive')",
            name="ck_workloads_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    workload_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="registered")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    application: Mapped[Application] = relationship(back_populates="workloads")
    runs: Mapped[list["WorkloadRun"]] = relationship(
        back_populates="workload", passive_deletes="all"
    )


class WorkloadRun(Base):
    __tablename__ = "workload_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'failed')",
            name="ck_workload_runs_status",
        ),
        CheckConstraint(
            "source IN ('simulated', 'measured')",
            name="ck_workload_runs_source",
        ),
        CheckConstraint("duration_seconds > 0", name="ck_workload_runs_duration"),
        CheckConstraint("average_power_w >= 0", name="ck_workload_runs_power"),
        CheckConstraint(
            "carbon_intensity_g_per_kwh >= 0",
            name="ck_workload_runs_carbon_intensity",
        ),
        CheckConstraint("energy_kwh >= 0", name="ck_workload_runs_energy"),
        CheckConstraint(
            "emissions_kg_co2e >= 0",
            name="ck_workload_runs_emissions",
        ),
        Index(
            "ix_workload_runs_status_completed_at",
            "status",
            "completed_at",
        ),
        Index(
            "ix_workload_runs_application_status_completed_at",
            "application_id",
            "status",
            "completed_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    workload_id: Mapped[int] = mapped_column(
        ForeignKey("workloads.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    workload_type: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    average_power_w: Mapped[float] = mapped_column(Float, nullable=False)
    carbon_intensity_g_per_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    cpu_utilization_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    profile_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    energy_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    emissions_kg_co2e: Mapped[float] = mapped_column(Float, nullable=False)
    estimation_method: Mapped[str] = mapped_column(String(40), nullable=False)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="simulated")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    simulation_started_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, nullable=False
    )

    application: Mapped[Application] = relationship(back_populates="workload_runs")
    workload: Mapped[Workload] = relationship(back_populates="runs")


class MonitoringRecord(Base):
    __tablename__ = "monitoring_records"
    __table_args__ = (
        CheckConstraint("energy_kwh IS NULL OR energy_kwh >= 0", name="ck_monitoring_energy_nonnegative"),
        CheckConstraint(
            "emissions_kg_co2e IS NULL OR emissions_kg_co2e >= 0",
            name="ck_monitoring_emissions_nonnegative",
        ),
        CheckConstraint(
            "source_type IN ('simulated', 'estimated', 'measured')",
            name="ck_monitoring_source_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    energy_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    emissions_kg_co2e: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)

    application: Mapped[Application] = relationship(back_populates="monitoring_records")


class PolicyEvent(Base):
    __tablename__ = "policy_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('warning', 'throttling', 'suspension', 'recovery', 'other')",
            name="ck_policy_events_type",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)

    application: Mapped[Application] = relationship(back_populates="policy_events")


class ExperimentResult(Base):
    __tablename__ = "experiment_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    method: Mapped[str] = mapped_column(String(80), nullable=False)
    results_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now, nullable=False)
