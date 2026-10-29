"""Workload, monitoring, policy, and experiment API schemas."""

import math
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WorkloadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    workload_type: str = Field(min_length=1, max_length=80)
    status: Literal["registered", "pending", "inactive"] = "registered"

    @field_validator("name", "workload_type")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value


class WorkloadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    name: str
    workload_type: str
    status: str
    created_at: datetime


class MonitoringRecordCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    energy_kwh: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    emissions_kg_co2e: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_type: Literal["simulated", "estimated", "measured"]


class MonitoringRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    energy_kwh: float | None
    emissions_kg_co2e: float | None
    recorded_at: datetime
    source_type: str


class PolicyEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    event_type: str
    message: str
    created_at: datetime


class ExperimentResultCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    method: Literal["manual", "imported"] = Field(
        description="Phase 2 stores manually entered or imported results only."
    )
    results_json: dict[str, Any]

    @field_validator("results_json")
    @classmethod
    def require_finite_numbers(cls, value: dict[str, Any]) -> dict[str, Any]:
        pending: list[Any] = [value]
        while pending:
            item = pending.pop()
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError("Experiment results must contain finite numbers")
            if isinstance(item, dict):
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
        return value

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Experiment name must not be blank")
        return value


class ExperimentResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    method: str
    results_json: dict[str, Any]
    created_at: datetime
