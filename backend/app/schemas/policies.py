"""Validated budget-policy request and response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.limits import (
    MAX_BUDGET_KG_CO2E,
    MAX_DATABASE_ID,
    MAX_POLICY_THRESHOLD_PERCENT,
)

BudgetPeriod = Literal["daily", "weekly", "monthly"]
PolicyAction = Literal["monitor", "warn", "recommend_throttle"]
PolicyStatus = Literal["within_budget", "warning", "critical", "exceeded"]
RecommendedAction = Literal["monitor", "warn", "recommend_throttle"]


class BudgetPolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: int = Field(gt=0, le=MAX_DATABASE_ID)
    budget_kg_co2e: float = Field(
        gt=0, le=MAX_BUDGET_KG_CO2E, allow_inf_nan=False
    )
    period: BudgetPeriod
    warning_threshold_percent: float = Field(
        default=80,
        gt=0,
        le=MAX_POLICY_THRESHOLD_PERCENT,
        allow_inf_nan=False,
    )
    critical_threshold_percent: float = Field(
        default=95,
        gt=0,
        le=MAX_POLICY_THRESHOLD_PERCENT,
        allow_inf_nan=False,
    )
    enabled: bool = True
    action: PolicyAction = "warn"

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "BudgetPolicyCreate":
        if self.warning_threshold_percent >= self.critical_threshold_percent:
            raise ValueError(
                "warning_threshold_percent must be lower than critical_threshold_percent"
            )
        return self


class BudgetPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    budget_kg_co2e: float | None = Field(
        default=None,
        gt=0,
        le=MAX_BUDGET_KG_CO2E,
        allow_inf_nan=False,
    )
    period: BudgetPeriod | None = None
    warning_threshold_percent: float | None = Field(
        default=None,
        gt=0,
        le=MAX_POLICY_THRESHOLD_PERCENT,
        allow_inf_nan=False,
    )
    critical_threshold_percent: float | None = Field(
        default=None,
        gt=0,
        le=MAX_POLICY_THRESHOLD_PERCENT,
        allow_inf_nan=False,
    )
    enabled: bool | None = None
    action: PolicyAction | None = None

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "BudgetPolicyUpdate":
        warning = self.warning_threshold_percent
        critical = self.critical_threshold_percent
        if (
            warning is not None
            and critical is not None
            and warning >= critical
        ):
            raise ValueError(
                "warning_threshold_percent must be lower than critical_threshold_percent"
            )
        return self


class BudgetPolicyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    budget_kg_co2e: float
    period: BudgetPeriod
    warning_threshold_percent: float
    critical_threshold_percent: float
    enabled: bool
    action: PolicyAction
    created_at: datetime
    updated_at: datetime


class RunContribution(BaseModel):
    run_id: str
    completed_at: datetime
    emissions_kg_co2e: float
    source: Literal["simulated", "measured"]
    estimation_method: str


class BudgetEvaluationRead(BaseModel):
    policy_id: int
    application_id: int
    enabled: bool
    period: BudgetPeriod
    period_start: datetime
    period_end: datetime
    time_basis: Literal["UTC"]
    run_timestamp_field: Literal["completed_at"]
    budget_kg_co2e: float
    consumed_kg_co2e: float
    remaining_kg_co2e: float
    utilization_percent: float
    status: PolicyStatus
    contributing_run_count: int
    contributing_runs: list[RunContribution]
    configured_action: PolicyAction
    recommended_action: RecommendedAction
    enforcement_mode: Literal["recommendation_only"]
    consumption_source: Literal["recorded_workload_run_estimates"]
