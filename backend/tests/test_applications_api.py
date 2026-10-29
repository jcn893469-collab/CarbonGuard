import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models import Application, PolicyEvent, Workload


def create_application(client, name="Payments API"):
    response = client.post(
        "/api/applications",
        json={"name": name, "description": "Payment processing", "owner": "Platform"},
    )
    assert response.status_code == 201
    return response.json()


def test_create_list_read_and_update_application(client):
    created = create_application(client)
    assert created["created_at"].endswith(("Z", "+00:00"))
    assert created["updated_at"].endswith(("Z", "+00:00"))

    listed = client.get("/api/applications")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [created["id"]]

    retrieved = client.get(f"/api/applications/{created['id']}")
    assert retrieved.status_code == 200
    assert retrieved.json()["name"] == "Payments API"

    updated = client.put(
        f"/api/applications/{created['id']}",
        json={
            "name": "Payments Platform",
            "description": "Updated description",
            "owner": "Core",
            "status": "inactive",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Payments Platform"
    assert updated.json()["status"] == "inactive"


def test_application_name_is_trimmed_and_case_insensitive_unique(client):
    response = client.post("/api/applications", json={"name": "  Billing  "})
    assert response.status_code == 201
    assert response.json()["name"] == "Billing"

    duplicate = client.post("/api/applications", json={"name": "billing"})
    assert duplicate.status_code == 409


def test_application_collection_pagination(client):
    create_application(client, "First")
    create_application(client, "Second")

    response = client.get("/api/applications?skip=1&limit=1")
    assert response.status_code == 200
    assert [application["name"] for application in response.json()] == ["Second"]
    assert client.get("/api/applications?limit=101").status_code == 422


def test_blank_application_name_is_rejected(client):
    response = client.post("/api/applications", json={"name": "   "})
    assert response.status_code == 422


def test_application_create_rejects_server_managed_fields(client):
    response = client.post(
        "/api/applications",
        json={
            "name": "Overposting attempt",
            "created_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
        },
    )

    assert response.status_code == 422
    assert client.get("/api/applications").json() == []


def test_missing_application_returns_404(client):
    missing = client.get("/api/applications/100")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Application not found"}
    assert "Traceback" not in missing.text
    assert client.put(
        "/api/applications/100",
        json={"name": "Missing", "description": None, "owner": None, "status": "active"},
    ).status_code == 404
    assert client.delete("/api/applications/100").status_code == 404


def test_application_delete_is_restricted_while_records_exist(client):
    application = create_application(client)
    created = client.post(
        f"/api/applications/{application['id']}/workloads",
        json={"name": "worker", "workload_type": "batch"},
    )
    assert created.status_code == 201

    response = client.delete(f"/api/applications/{application['id']}")
    assert response.status_code == 409
    assert client.get(f"/api/applications/{application['id']}").status_code == 200


def test_application_can_be_deleted_when_empty(client):
    application = create_application(client)
    response = client.delete(f"/api/applications/{application['id']}")
    assert response.status_code == 204
    assert client.get(f"/api/applications/{application['id']}").status_code == 404


def test_database_foreign_key_rejects_orphan_workload(
    test_session_factory: sessionmaker,
):
    with test_session_factory() as db:
        db.add(
            Workload(
                application_id=999,
                name="orphan",
                workload_type="batch",
                status="registered",
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_budget_crud_and_input_validation(client):
    application = create_application(client)
    path = f"/api/applications/{application['id']}/budgets"
    response = client.post(
        path,
        json={
            "budget_kg_co2e": 125.5,
            "warning_threshold_percent": 75,
            "period": "monthly",
        },
    )
    assert response.status_code == 201
    budget = response.json()
    assert budget["application_id"] == application["id"]
    assert budget["budget_kg_co2e"] == 125.5
    assert client.get(path).json()[0]["id"] == budget["id"]
    assert client.get(f"/api/budgets/{budget['id']}").status_code == 200

    updated = client.put(
        f"/api/budgets/{budget['id']}",
        json={
            "budget_kg_co2e": 90,
            "warning_threshold_percent": 80,
            "period": "weekly",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["period"] == "weekly"
    assert client.delete(f"/api/budgets/{budget['id']}").status_code == 204

    assert client.post(
        path,
        json={
            "budget_kg_co2e": 0,
            "warning_threshold_percent": 101,
            "period": "yearly",
        },
    ).status_code == 422
    assert client.post(
        path,
        json={
            "budget_kg_co2e": 1_000_000_000_001,
            "warning_threshold_percent": 80,
            "period": "monthly",
        },
    ).status_code == 422


def test_budget_requires_existing_application(client):
    response = client.post(
        "/api/applications/999/budgets",
        json={"budget_kg_co2e": 1, "period": "daily"},
    )
    assert response.status_code == 404


def test_workload_registration_and_lookup(client):
    application = create_application(client)
    path = f"/api/applications/{application['id']}/workloads"
    created = client.post(
        path,
        json={"name": "nightly batch", "workload_type": "batch"},
    )
    assert created.status_code == 201
    workload = created.json()
    assert workload["status"] == "registered"
    assert client.get(path).json()[0]["id"] == workload["id"]
    assert client.get(f"/api/workloads/{workload['id']}").status_code == 200


def test_monitoring_record_is_stored_without_calculation(client):
    application = create_application(client)
    path = f"/api/applications/{application['id']}/monitoring-records"
    created = client.post(
        path,
        json={
            "energy_kwh": 2.5,
            "emissions_kg_co2e": 1.2,
            "source_type": "measured",
        },
    )
    assert created.status_code == 201
    record = created.json()
    assert record["energy_kwh"] == 2.5
    assert record["emissions_kg_co2e"] == 1.2
    assert record["source_type"] == "measured"
    assert client.get(path).json()[0]["id"] == record["id"]
    assert client.get(f"/api/monitoring-records/{record['id']}").status_code == 200

    invalid = client.post(
        path,
        json={"energy_kwh": -1, "source_type": "computed"},
    )
    assert invalid.status_code == 422


def test_policy_events_can_be_listed(client, test_session_factory: sessionmaker):
    application = create_application(client)
    with test_session_factory() as db:
        db.add(
            PolicyEvent(
                application_id=application["id"],
                event_type="warning",
                message="Stored test event",
            )
        )
        db.commit()

    response = client.get(f"/api/applications/{application['id']}/policy-events")
    assert response.status_code == 200
    assert response.json()[0]["message"] == "Stored test event"
    assert client.get("/api/applications/999/policy-events").status_code == 404


def test_experiment_result_is_stored_as_json(client):
    created = client.post(
        "/api/experiments",
        json={
            "name": "Imported evaluation",
            "method": "imported",
            "results_json": {"sample_count": 3, "label": "baseline"},
        },
    )
    assert created.status_code == 201
    result = created.json()
    assert result["results_json"] == {"sample_count": 3, "label": "baseline"}
    assert client.get("/api/experiments").json()[0]["id"] == result["id"]
    assert client.get(f"/api/experiments/{result['id']}").status_code == 200
    assert client.post(
        "/api/experiments",
        json={"name": "Not phase 2", "method": "simulation", "results_json": {}},
    ).status_code == 422


def test_experiment_result_rejects_non_finite_nested_numbers(client):
    response = client.post(
        "/api/experiments",
        content=(
            b'{"name":"Invalid numeric result","method":"manual",'
            b'"results_json":{"nested":[{"measurement":NaN}]}}'
        ),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == [
        "body",
        "results_json",
    ]
    assert "input" not in response.json()["detail"][0]
    assert "nan" not in response.text.lower()


def test_health_remains_available(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
