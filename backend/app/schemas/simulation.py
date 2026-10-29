"""Validated workload simulation request and response schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.limits import (
    MAX_AVERAGE_POWER_W,
    MAX_CARBON_INTENSITY_G_PER_KWH,
    MAX_DATABASE_ID,
)

MAX_SIMULATED_DURATION_SECONDS = 86_400
MAX_RANDOM_SEED = 2**32 - 1


class WorkloadSimulationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    application_id: int = Field(gt=0, le=MAX_DATABASE_ID)
    name: str = Field(min_length=1, max_length=120)
    workload_type: Literal["cpu-bound", "memory-bound", "mixed"]
    duration_seconds: float = Field(
        gt=0,
        le=MAX_SIMULATED_DURATION_SECONDS,
        allow_inf_nan=False,
    )
    average_power_w: float = Field(
        ge=0, le=MAX_AVERAGE_POWER_W, allow_inf_nan=False
    )
    carbon_intensity_g_per_kwh: float = Field(
        ge=0, le=MAX_CARBON_INTENSITY_G_PER_KWH, allow_inf_nan=False
    )
    cpu_utilization_percent: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False
    )
    seed: int | None = Field(default=None, ge=0, le=MAX_RANDOM_SEED)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Workload name must not be blank")
        return value


class WorkloadRunRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    application_id: int
    workload_id: int
    name: str
    workload_type: str
    status: Literal["completed", "failed"]
    parameters: dict[str, Any]
    profile: dict[str, Any]
    simulation_started_at: datetime
    completed_at: datetime
    average_power_w: float
    duration_seconds: float
    carbon_intensity_g_per_kwh: float
    energy_kwh: float
    emissions_kg_co2e: float
    estimation_method: str
    source: Literal["simulated"]
    estimation_source: Literal["estimated"]
