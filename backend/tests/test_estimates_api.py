import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_estimate_endpoint_returns_expected_values_and_provenance() -> None:
    response = client.post(
        "/api/estimates",
        json={
            "average_power_w": 120,
            "duration_seconds": 1800,
            "carbon_intensity_g_per_kwh": 400,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["energy_kwh"] == pytest.approx(0.06)
    assert body["emissions_kg_co2e"] == pytest.approx(0.024)
    assert body["carbon_intensity_g_per_kwh"] == 400
    assert body["estimation_method"] == "power_duration"
    assert body["source"] == "estimated"
    assert body["units"]["energy_kwh"] == "kWh"
    assert body["units"]["emissions_kg_co2e"] == "kg CO2e"
    assert body["assumptions"]


@pytest.mark.parametrize(
    "payload",
    [
        {"average_power_w": -1, "duration_seconds": 1, "carbon_intensity_g_per_kwh": 1},
        {"average_power_w": 1, "duration_seconds": 0, "carbon_intensity_g_per_kwh": 1},
        {"average_power_w": 1, "duration_seconds": 1, "carbon_intensity_g_per_kwh": -1},
        {"average_power_w": "NaN", "duration_seconds": 1, "carbon_intensity_g_per_kwh": 1},
        {"average_power_w": 1, "duration_seconds": "Infinity", "carbon_intensity_g_per_kwh": 1},
        {"average_power_w": 1_000_000_001, "duration_seconds": 1, "carbon_intensity_g_per_kwh": 1},
        {"average_power_w": 1, "duration_seconds": 31_536_001, "carbon_intensity_g_per_kwh": 1},
        {"average_power_w": 1, "duration_seconds": 1, "carbon_intensity_g_per_kwh": 100_001},
        {"average_power_w": 1, "duration_seconds": 1, "carbon_intensity_g_per_kwh": 1, "created_at": "2026-10-20T00:00:00Z"},
    ],
)
def test_estimate_endpoint_rejects_invalid_inputs(payload: dict) -> None:
    response = client.post("/api/estimates", json=payload)
    assert response.status_code == 422


def test_estimate_endpoint_handles_zero_values() -> None:
    response = client.post(
        "/api/estimates",
        json={
            "average_power_w": 0,
            "duration_seconds": 10,
            "carbon_intensity_g_per_kwh": 0,
        },
    )
    assert response.status_code == 200
    assert response.json()["energy_kwh"] == 0
    assert response.json()["emissions_kg_co2e"] == 0


def test_existing_root_health_and_application_apis_remain_available(client) -> None:
    assert client.get("/").status_code == 200
    assert client.get("/api/health").status_code == 200
    created = client.post("/api/applications", json={"name": "Estimate API test"})
    assert created.status_code == 201
    assert client.get(f"/api/applications/{created.json()['id']}").status_code == 200
