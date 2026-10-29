"""Transparent power-and-duration energy and emissions estimation."""

import math

from app.schemas.estimates import EstimateRequest, EstimateResponse

POWER_DURATION_METHOD = "power_duration"
ASSUMPTIONS = [
    "Average power is supplied by the caller and treated as constant for the duration.",
    "Carbon intensity is supplied explicitly by the caller; it is not fetched or verified against a regional grid.",
    "The output is an estimate, not measured telemetry.",
]
UNITS = {
    "average_power_w": "W",
    "duration_seconds": "s",
    "carbon_intensity_g_per_kwh": "g CO2e/kWh",
    "energy_kwh": "kWh",
    "emissions_kg_co2e": "kg CO2e",
}


def estimate_energy_and_emissions(request: EstimateRequest) -> EstimateResponse:
    """Calculate energy and emissions from explicit average power and duration."""
    power_w = request.average_power_w
    duration_seconds = request.duration_seconds
    carbon_intensity = request.carbon_intensity_g_per_kwh

    if not all(math.isfinite(value) for value in (power_w, duration_seconds, carbon_intensity)):
        raise ValueError("Power, duration, and carbon intensity must be finite numbers")
    if power_w < 0:
        raise ValueError("Average power must be nonnegative")
    if duration_seconds <= 0:
        raise ValueError("Duration must be greater than zero")
    if carbon_intensity < 0:
        raise ValueError("Carbon intensity must be nonnegative")

    energy_kwh = power_w * duration_seconds / 3_600_000
    emissions_kg_co2e = energy_kwh * carbon_intensity / 1000
    if not math.isfinite(energy_kwh) or not math.isfinite(emissions_kg_co2e):
        raise ValueError("The supplied values exceed the supported calculation range")

    return EstimateResponse(
        energy_kwh=round(energy_kwh, 12),
        emissions_kg_co2e=round(emissions_kg_co2e, 12),
        average_power_w=power_w,
        duration_seconds=duration_seconds,
        carbon_intensity_g_per_kwh=carbon_intensity,
        estimation_method=POWER_DURATION_METHOD,
        source="estimated",
        assumptions=ASSUMPTIONS.copy(),
        units=UNITS.copy(),
    )
