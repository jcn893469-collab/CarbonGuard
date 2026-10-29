"""Response models for historical workload analytics and reports."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.applications import ApplicationRead
from app.schemas.policies import BudgetEvaluationRead, PolicyStatus

AggregationInterval = Literal["daily", "weekly", "monthly"]


class AnalyticsTotals(BaseModel):
    completed_workload_run_count: int
    estimated_energy_kwh: float
    estimated_emissions_kg_co2e: float


class AnalyticsPolicyCounts(BaseModel):
    within_budget: int
    warning: int
    critical: int
    exceeded: int


class ApplicationAnalyticsRead(BaseModel):
    application_id: int
    application_name: str
    application_description: str | None
    owner: str | None
    application_status: Literal["active", "inactive"]
    totals_window: Literal["all_recorded_time"]
    completed_workload_run_count: int
    estimated_energy_kwh_all_time: float
    estimated_emissions_kg_co2e_all_time: float
    enabled_policy_evaluation: BudgetEvaluationRead | None


class AnalyticsOverviewRead(BaseModel):
    evaluated_at: datetime
    registered_application_count: int
    enabled_policy_count: int
    all_time_completed_workload_run_count: int
    all_time_estimated_energy_kwh: float
    all_time_estimated_emissions_kg_co2e: float
    run_metrics_window: Literal["all_recorded_time"]
    policy_status_window: Literal["current_policy_periods"]
    policy_status_counts: AnalyticsPolicyCounts
    recommended_intervention_count: int
    policy_evaluations: list[BudgetEvaluationRead]
    applications: list[ApplicationAnalyticsRead]


class TrendBucket(BaseModel):
    period_start: datetime
    period_end: datetime
    estimated_energy_kwh: float
    estimated_emissions_kg_co2e: float
    completed_workload_run_count: int
    is_empty: bool


class AnalyticsTrendRead(BaseModel):
    range_start: datetime
    range_end: datetime
    interval: AggregationInterval
    time_basis: Literal["UTC"]
    range_semantics: Literal["half_open"]
    data_source: Literal["recorded_completed_workload_runs"]
    application_id: int | None
    buckets: list[TrendBucket]


class AnalyticsWorkloadRunRead(BaseModel):
    run_id: str
    application_id: int
    application_name: str
    name: str
    workload_type: str
    status: Literal["completed", "failed"]
    completed_at: datetime
    duration_seconds: float
    energy_kwh: float
    emissions_kg_co2e: float


class AnalyticsWorkloadApplicationRead(BaseModel):
    application_id: int
    application_name: str
    completed_workload_run_count: int
    estimated_energy_kwh: float
    estimated_emissions_kg_co2e: float


class AnalyticsWorkloadsRead(BaseModel):
    range_start: datetime
    range_end: datetime
    time_basis: Literal["UTC"]
    range_semantics: Literal["half_open"]
    data_source: Literal["recorded_workload_runs"]
    application_id: int | None
    status_counts: dict[str, int]
    applications: list[AnalyticsWorkloadApplicationRead]
    runs: list[AnalyticsWorkloadRunRead]


class AnalyticsApplicationsRead(BaseModel):
    evaluated_at: datetime
    items: list[ApplicationAnalyticsRead]


class AnalyticsPolicySnapshot(BaseModel):
    policy_id: int
    application_id: int
    application_name: str
    enabled: bool
    budget_kg_co2e: float
    period: Literal["daily", "weekly", "monthly"]
    configured_action: Literal["monitor", "warn", "recommend_throttle"]
    evaluation: BudgetEvaluationRead | None


class AnalyticsPoliciesRead(BaseModel):
    evaluated_at: datetime
    evaluation_semantics: Literal["evaluated_on_request"]
    items: list[AnalyticsPolicySnapshot]


class ApplicationAnalyticsDetailRead(BaseModel):
    evaluated_at: datetime
    application: ApplicationRead
    totals: AnalyticsTotals
    trend: AnalyticsTrendRead
    enabled_policy_evaluation: BudgetEvaluationRead | None


class AnalyticsExportRequest(BaseModel):
    start: datetime
    end: datetime
    application_id: int | None = None


class AnalyticsExportRow(BaseModel):
    application_id: int
    application_name: str
    run_id: str
    completed_at: datetime
    energy_kwh: float
    emissions_kg_co2e: float
    run_source: str
    estimation_method: str
    budget_policy_id: int | None
    budget_period: str | None
    budget_kg_co2e: float | None
    current_policy_status: PolicyStatus | None
    current_recommended_action: str | None
