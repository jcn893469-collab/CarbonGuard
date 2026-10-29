"""Application and carbon-budget API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.limits import MAX_BUDGET_KG_CO2E


class ApplicationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    owner: str | None = Field(default=None, max_length=120)
    status: Literal["active", "inactive"] = "active"

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Application name must not be blank")
        return value


class ApplicationUpdate(ApplicationCreate):
    pass


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    owner: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class CarbonBudgetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    budget_kg_co2e: float = Field(
        gt=0, le=MAX_BUDGET_KG_CO2E, allow_inf_nan=False
    )
    warning_threshold_percent: int = Field(default=80, ge=1, le=100)
    period: Literal["daily", "weekly", "monthly"]


class CarbonBudgetUpdate(CarbonBudgetCreate):
    pass


class CarbonBudgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    budget_kg_co2e: float
    warning_threshold_percent: int
    period: str
    created_at: datetime
    updated_at: datetime
