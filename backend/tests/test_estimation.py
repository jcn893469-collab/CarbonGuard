import pytest
from pydantic import ValidationError

from app.schemas.estimates import EstimateRequest
from app.services.estimation import estimate_energy_and_emissions


def test_example_calculation() -> None:
    result = estimate_energy_and_emissions(
        EstimateRequest(
            average_power_w=120,
            duration_seconds=1800,
            carbon_intensity_g_per_kwh=400,
        )
    )

    assert result.energy_kwh == pytest.approx(0.06)
    assert result.emissions_kg_co2e == pytest.approx(0.024)
    assert result.source == "estimated"
    assert result.estimation_method == "power_duration"


def test_zero_power_produces_zero_energy_and_emissions() -> None:
    result = estimate_energy_and_emissions(
        EstimateRequest(
            average_power_w=0,
            duration_seconds=10,
            carbon_intensity_g_per_kwh=400,
        )
    )
    assert result.energy_kwh == 0
    assert result.emissions_kg_co2e == 0


def test_zero_carbon_intensity_produces_zero_emissions() -> None:
    result = estimate_energy_and_emissions(
        EstimateRequest(
            average_power_w=100,
            duration_seconds=3600,
            carbon_intensity_g_per_kwh=0,
        )
    )
    assert result.energy_kwh == 0.1
    assert result.emissions_kg_co2e == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"average_power_w": -1, "duration_seconds": 1, "carbon_intensity_g_per_kwh": 1},
        {"average_power_w": 1, "duration_seconds": 0, "carbon_intensity_g_per_kwh": 1},
        {"average_power_w": 1, "duration_seconds": -1, "carbon_intensity_g_per_kwh": 1},
        {"average_power_w": 1, "duration_seconds": 1, "carbon_intensity_g_per_kwh": -1},
        {"average_power_w": "NaN", "duration_seconds": 1, "carbon_intensity_g_per_kwh": 1},
        {"average_power_w": "Infinity", "duration_seconds": 1, "carbon_intensity_g_per_kwh": 1},
        {"average_power_w": 1, "duration_seconds": "Infinity", "carbon_intensity_g_per_kwh": 1},
    ],
)
def test_invalid_or_nonfinite_inputs_are_rejected(payload: dict) -> None:
    with pytest.raises(ValidationError):
        EstimateRequest(**payload)


def test_overflowing_finite_inputs_are_rejected_by_service() -> None:
    oversized_values = {
        "average_power_w": 1e308,
        "duration_seconds": 1e308,
        "carbon_intensity_g_per_kwh": 0,
    }
    with pytest.raises(ValidationError):
        EstimateRequest(**oversized_values)

    request = EstimateRequest.model_construct(**oversized_values)
    with pytest.raises(ValueError, match="calculation range"):
        estimate_energy_and_emissions(request)


def test_response_includes_units_inputs_and_explanatory_assumptions() -> None:
    result = estimate_energy_and_emissions(
        EstimateRequest(
            average_power_w=120,
            duration_seconds=1800,
            carbon_intensity_g_per_kwh=400,
        )
    )
    data = result.model_dump()

    assert data["average_power_w"] == 120
    assert data["duration_seconds"] == 1800
    assert data["carbon_intensity_g_per_kwh"] == 400
    assert data["units"] == {
        "average_power_w": "W",
        "duration_seconds": "s",
        "carbon_intensity_g_per_kwh": "g CO2e/kWh",
        "energy_kwh": "kWh",
        "emissions_kg_co2e": "kg CO2e",
    }
    assert any("constant" in assumption for assumption in data["assumptions"])
    assert any("not fetched" in assumption for assumption in data["assumptions"])
