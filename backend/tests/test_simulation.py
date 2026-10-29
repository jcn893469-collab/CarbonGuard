import pytest


def register_application(client, name="Simulation test app"):
    response = client.post("/api/applications", json={"name": name})
    assert response.status_code == 201
    return response.json()


def simulation_payload(application_id: int, **overrides) -> dict:
    payload = {
        "application_id": application_id,
        "name": "demo-cpu-workload",
        "workload_type": "cpu-bound",
        "duration_seconds": 1800,
        "average_power_w": 120,
        "carbon_intensity_g_per_kwh": 400,
        "cpu_utilization_percent": 75,
        "seed": 42,
    }
    return payload | overrides


def test_simulation_uses_estimator_and_persists_run(client):
    application = register_application(client)
    response = client.post(
        "/api/workloads/simulate",
        json=simulation_payload(application["id"]),
    )

    assert response.status_code == 201
    result = response.json()
    assert result["application_id"] == application["id"]
    assert result["name"] == "demo-cpu-workload"
    assert result["workload_type"] == "cpu-bound"
    assert result["status"] == "completed"
    assert result["energy_kwh"] == pytest.approx(0.06)
    assert result["emissions_kg_co2e"] == pytest.approx(0.024)
    assert result["source"] == "simulated"
    assert result["estimation_source"] == "estimated"
    assert result["estimation_method"] == "power_duration"
    assert result["profile"]["sample_count"] == 60
    assert result["parameters"]["seed"] == 42

    stored = client.get(f"/api/workload-runs/{result['run_id']}")
    assert stored.status_code == 200
    assert stored.json() == result


def test_seed_reproduces_profile_but_not_run_identity_or_time(client):
    application = register_application(client)
    payload = simulation_payload(application["id"], seed=314)
    first = client.post("/api/workloads/simulate", json=payload).json()
    second = client.post("/api/workloads/simulate", json=payload).json()

    assert first["profile"] == second["profile"]
    assert first["run_id"] != second["run_id"]
    assert first["simulation_started_at"] != second["simulation_started_at"]


def test_different_seeds_produce_different_profiles(client):
    application = register_application(client)
    first = client.post(
        "/api/workloads/simulate",
        json=simulation_payload(application["id"], seed=1),
    ).json()
    second = client.post(
        "/api/workloads/simulate",
        json=simulation_payload(application["id"], seed=2),
    ).json()

    assert first["profile"] != second["profile"]


def test_workload_type_profiles_have_documented_variation(client):
    application = register_application(client)
    profiles = {}
    for workload_type in ("cpu-bound", "memory-bound", "mixed"):
        response = client.post(
            "/api/workloads/simulate",
            json=simulation_payload(
                application["id"],
                name=f"work-{workload_type}",
                workload_type=workload_type,
            ),
        )
        assert response.status_code == 201
        profiles[workload_type] = response.json()["profile"]

    assert profiles["memory-bound"]["variation_range"] == [0.9, 1.1]
    assert profiles["cpu-bound"]["variation_range"] == [0.65, 1.35]
    assert profiles["mixed"]["variation_range"] == [0.5, 1.5]


def test_simulation_requires_existing_application(client):
    response = client.post(
        "/api/workloads/simulate",
        json=simulation_payload(999),
    )
    assert response.status_code == 404


@pytest.mark.parametrize(
    "override",
    [
        {"workload_type": "gpu-bound"},
        {"average_power_w": -1},
        {"average_power_w": "NaN"},
        {"average_power_w": "Infinity"},
        {"average_power_w": 1_000_000_001},
        {"duration_seconds": 0},
        {"duration_seconds": 86401},
        {"duration_seconds": "Infinity"},
        {"carbon_intensity_g_per_kwh": -1},
        {"carbon_intensity_g_per_kwh": "NaN"},
        {"carbon_intensity_g_per_kwh": "Infinity"},
        {"carbon_intensity_g_per_kwh": 100_001},
        {"cpu_utilization_percent": -0.1},
        {"cpu_utilization_percent": 100.1},
        {"cpu_utilization_percent": "Infinity"},
        {"seed": -1},
    ],
)
def test_invalid_simulation_parameters_are_rejected(client, override):
    application = register_application(client)
    response = client.post(
        "/api/workloads/simulate",
        json=simulation_payload(application["id"], **override),
    )
    assert response.status_code == 422


def test_cpu_utilization_is_descriptive_and_does_not_derive_power(client):
    application = register_application(client)
    result = client.post(
        "/api/workloads/simulate",
        json=simulation_payload(application["id"], average_power_w=120),
    ).json()
    assert result["average_power_w"] == 120
    assert result["parameters"]["cpu_utilization_percent"] == 75
    assert result["energy_kwh"] == pytest.approx(0.06)


def test_run_collections_support_pagination_and_application_filter(client):
    first_app = register_application(client, "First sim app")
    second_app = register_application(client, "Second sim app")
    first_run = client.post(
        "/api/workloads/simulate",
        json=simulation_payload(first_app["id"], name="first-run"),
    ).json()
    client.post(
        "/api/workloads/simulate",
        json=simulation_payload(first_app["id"], name="second-run"),
    )
    client.post(
        "/api/workloads/simulate",
        json=simulation_payload(second_app["id"], name="third-run"),
    )

    all_runs = client.get("/api/workload-runs?skip=1&limit=1")
    assert all_runs.status_code == 200
    assert len(all_runs.json()) == 1
    assert len(client.get(f"/api/applications/{first_app['id']}/workload-runs").json()) == 2
    assert client.get(
        f"/api/applications/{second_app['id']}/workload-runs"
    ).json()[0]["name"] == "third-run"
    assert client.get("/api/workload-runs?limit=101").status_code == 422

    missing = client.get(f"/api/workload-runs/{first_run['run_id'][:-1]}x")
    assert missing.status_code == 404
    assert client.get("/api/applications/999/workload-runs").status_code == 404


def test_registered_workload_type_conflict_is_clear(client):
    application = register_application(client)
    created = client.post(
        f"/api/applications/{application['id']}/workloads",
        json={"name": "existing", "workload_type": "batch"},
    )
    assert created.status_code == 201

    conflict = client.post(
        "/api/workloads/simulate",
        json=simulation_payload(
            application["id"],
            name="existing",
            workload_type="cpu-bound",
        ),
    )
    assert conflict.status_code == 409


def test_application_deletion_remains_restricted_after_simulation(client):
    application = register_application(client)
    simulated = client.post(
        "/api/workloads/simulate",
        json=simulation_payload(application["id"]),
    )
    assert simulated.status_code == 201

    response = client.delete(f"/api/applications/{application['id']}")
    assert response.status_code == 409
    assert client.get(
        f"/api/workload-runs/{simulated.json()['run_id']}"
    ).status_code == 200


def test_simulation_rejects_values_above_supported_calculation_limits(client):
    application = register_application(client)
    response = client.post(
        "/api/workloads/simulate",
        json=simulation_payload(
            application["id"],
            average_power_w=1e308,
            carbon_intensity_g_per_kwh=1e308,
        ),
    )
    assert response.status_code == 422
    error_fields = {
        tuple(error["loc"])
        for error in response.json()["detail"]
    }
    assert ("body", "average_power_w") in error_fields
    assert ("body", "carbon_intensity_g_per_kwh") in error_fields
