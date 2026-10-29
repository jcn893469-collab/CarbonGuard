"""Request and response schemas for transparent carbon estimates."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.limits import (
    MAX_AVERAGE_POWER_W,
    MAX_CARBON_INTENSITY_G_PER_KWH,
    MAX_ESTIMATION_DURATION_SECONDS,
)


class EstimateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    average_power_w: float = Field(
        ge=0,
        le=MAX_AVERAGE_POWER_W,
        allow_inf_nan=False,
        description="User-provided average power in watts.",
    )
    duration_seconds: float = Field(
        gt=0,
        le=MAX_ESTIMATION_DURATION_SECONDS,
        allow_inf_nan=False,
        description="Workload duration in seconds, limited to 365 days.",
    )
    carbon_intensity_g_per_kwh: float = Field(
        ge=0,
        le=MAX_CARBON_INTENSITY_G_PER_KWH,
        allow_inf_nan=False,
        description="Explicit carbon intensity in grams CO2e per kWh.",
    )


class EstimateResponse(BaseModel):
    """A calculation result with explicit units, provenance, and assumptions."""

    energy_kwh: float
    emissions_kg_co2e: float
    average_power_w: float
    duration_seconds: float
    carbon_intensity_g_per_kwh: float
    estimation_method: Literal["power_duration"]
    source: Literal["estimated"]
    assumptions: list[str]
    units: dict[str, str]
