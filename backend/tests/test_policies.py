from datetime import datetime, timedelta, timezone

import pytest

from app.models import BudgetPolicy, WorkloadRun
from app.services.policies import evaluate_policy, period_bounds


def register_application(client, name="Policy test application"):
    response = client.post("/api/applications", json={"name": name})
    assert response.status_code == 201
    return response.json()


def create_policy(client, application_id, **overrides):
    payload = {
        "application_id": application_id,
        "budget_kg_co2e": 0.05,
        "period": "daily",
    } | overrides
    return client.post("/api/budget-policies", json=payload)


def simulate_run(client, application_id, name):
    response = client.post(
        "/api/workloads/simulate",
        json={
            "application_id": application_id,
            "name": name,
            "workload_type": "cpu-bound",
            "duration_seconds": 1800,
            "average_power_w": 120,
            "carbon_intensity_g_per_kwh": 400,
            "seed": 42,
        },
    )
    assert response.status_code == 201
    return response.json()


def set_run_times(session_factory, run_ids, completed_at):
    with session_factory() as db:
        for run_id in run_ids:
            run = db.get(WorkloadRun, run_id)
            run.completed_at = completed_at
        db.commit()


def evaluate_at(session_factory, policy_id, reference_time):
    with session_factory() as db:
        policy = db.get(BudgetPolicy, policy_id)
        return evaluate_policy(db, policy, reference_time)


def test_create_read_and_enforce_one_policy_per_application(client):
    application = register_application(client)
    created = create_policy(client, application["id"])

    assert created.status_code == 201
    policy = created.json()
    assert policy["application_id"] == application["id"]
    assert policy["budget_kg_co2e"] == 0.05
    assert policy["warning_threshold_percent"] == 80
    assert policy["critical_threshold_percent"] == 95
    assert policy["enabled"] is True
    assert policy["action"] == "warn"
    assert client.get(f"/api/budget-policies/{policy['id']}").json() == policy
    assert create_policy(client, application["id"]).status_code == 409


@pytest.mark.parametrize(
    "overrides",
    [
        {"budget_kg_co2e": 0},
        {"budget_kg_co2e": -1},
        {"budget_kg_co2e": "Infinity"},
        {"budget_kg_co2e": 1_000_000_000_001},
        {"warning_threshold_percent": 0},
        {"warning_threshold_percent": "NaN"},
        {"warning_threshold_percent": 1_000_001},
        {"critical_threshold_percent": 1_000_001},
        {"critical_threshold_percent": 80, "warning_threshold_percent": 80},
        {"critical_threshold_percent": 79, "warning_threshold_percent": 80},
        {"period": "yearly"},
        {"action": "terminate"},
    ],
)
def test_invalid_policy_configuration_is_rejected(client, overrides):
    application = register_application(client)
    assert create_policy(client, application["id"], **overrides).status_code == 422


def test_policy_requires_existing_application_and_rejects_malformed_payload(client):
    assert create_policy(client, 999).status_code == 404
    assert create_policy(client, 2_147_483_648).status_code == 422
    assert client.post("/api/budget-policies", json={"application_id": 1}).status_code == 422
    application = register_application(client)
    payload = {
        "application_id": application["id"],
        "budget_kg_co2e": 1,
        "period": "daily",
        "unexpected": True,
    }
    assert client.post("/api/budget-policies", json=payload).status_code == 422


def test_update_thresholds_and_enable_disable_behavior(client):
    application = register_application(client)
    policy = create_policy(client, application["id"]).json()

    updated = client.patch(
        f"/api/budget-policies/{policy['id']}",
        json={"critical_threshold_percent": 110, "enabled": False},
    )
    assert updated.status_code == 200
    assert updated.json()["critical_threshold_percent"] == 110
    assert updated.json()["enabled"] is False
    assert client.patch(
        f"/api/budget-policies/{policy['id']}",
        json={"warning_threshold_percent": 110},
    ).status_code == 422
    assert client.patch(
        f"/api/budget-policies/{policy['id']}", json={"enabled": None}
    ).status_code == 422
    assert client.patch(f"/api/budget-policies/{policy['id']}", json={}).status_code == 422
    assert client.post("/api/budget-policies/evaluate").json() == []
    assert client.get(f"/api/applications/{application['id']}/budget-status").status_code == 404

    enabled = client.patch(
        f"/api/budget-policies/{policy['id']}", json={"enabled": True}
    )
    assert enabled.status_code == 200
    assert len(client.post("/api/budget-policies/evaluate").json()) == 1


def test_policy_listing_filters_by_application(client):
    first = register_application(client, "Policy first app")
    second = register_application(client, "Policy second app")
    first_policy = create_policy(client, first["id"]).json()
    create_policy(client, second["id"])

    assert len(client.get("/api/budget-policies").json()) == 2
    filtered = client.get(f"/api/budget-policies?application_id={first['id']}")
    assert [item["id"] for item in filtered.json()] == [first_policy["id"]]
    assert client.get("/api/budget-policies?application_id=0").status_code == 422
    assert client.get("/api/budget-policies?limit=101").status_code == 422
    first_page = client.post("/api/budget-policies/evaluate?limit=1")
    second_page = client.post("/api/budget-policies/evaluate?skip=1&limit=1")
    assert first_page.status_code == second_page.status_code == 200
    assert len(first_page.json()) == len(second_page.json()) == 1
    assert first_page.json()[0]["policy_id"] != second_page.json()[0]["policy_id"]
    assert client.post("/api/budget-policies/evaluate?limit=101").status_code == 422


def test_policy_can_be_deleted_without_deleting_application_or_workload_history(client):
    application = register_application(client)
    policy = create_policy(client, application["id"]).json()
    run = simulate_run(client, application["id"], "retain-after-policy-delete")

    deleted = client.delete(f"/api/budget-policies/{policy['id']}")

    assert deleted.status_code == 204
    assert client.get(f"/api/budget-policies/{policy['id']}").status_code == 404
    assert client.get(f"/api/workload-runs/{run['run_id']}").status_code == 200
    assert client.get(f"/api/applications/{application['id']}").status_code == 200
    assert client.delete(f"/api/budget-policies/{policy['id']}").status_code == 404


def test_no_run_evaluation_reports_zero_consumption(client):
    application = register_application(client)
    policy = create_policy(client, application["id"]).json()

    result = client.post(f"/api/budget-policies/{policy['id']}/evaluate")
    assert result.status_code == 200
    assert result.json()["consumed_kg_co2e"] == 0
    assert result.json()["utilization_percent"] == 0
    assert result.json()["remaining_kg_co2e"] == 0.05
    assert result.json()["contributing_run_count"] == 0
    assert result.json()["status"] == "within_budget"
    assert result.json()["recommended_action"] == "monitor"


def test_aggregates_recorded_emissions_and_repeated_evaluation_does_not_double_count(
    client, test_session_factory
):
    application = register_application(client)
    policy = create_policy(client, application["id"], budget_kg_co2e=0.05).json()
    first = simulate_run(client, application["id"], "aggregation-one")
    second = simulate_run(client, application["id"], "aggregation-two")
    now = datetime(2026, 3, 18, 12, tzinfo=timezone.utc)
    set_run_times(test_session_factory, [first["run_id"], second["run_id"]], now)

    evaluated = evaluate_at(test_session_factory, policy["id"], now)
    evaluated_again = evaluate_at(test_session_factory, policy["id"], now)
    assert evaluated.consumed_kg_co2e == pytest.approx(0.048)
    assert evaluated.utilization_percent == pytest.approx(96)
    assert evaluated.status == "critical"
    assert evaluated.contributing_run_count == 2
    assert len(evaluated.contributing_runs) == 2
    assert evaluated_again == evaluated


def test_half_open_period_excludes_runs_before_start_and_at_end(
    client, test_session_factory
):
    application = register_application(client)
    policy = create_policy(client, application["id"], budget_kg_co2e=0.05).json()
    before = simulate_run(client, application["id"], "outside-before")
    at_start = simulate_run(client, application["id"], "inside-start")
    at_end = simulate_run(client, application["id"], "outside-end")
    start = datetime(2026, 3, 18, tzinfo=timezone.utc)
    set_run_times(
        test_session_factory,
        [before["run_id"], at_start["run_id"], at_end["run_id"]],
        start,
    )
    with test_session_factory() as db:
        db.get(WorkloadRun, before["run_id"]).completed_at = start - timedelta(microseconds=1)
        db.get(WorkloadRun, at_end["run_id"]).completed_at = start + timedelta(days=1)
        db.commit()

    result = evaluate_at(
        test_session_factory,
        policy["id"],
        start + timedelta(hours=12),
    )
    assert result.period_start == start
    assert result.period_end == start + timedelta(days=1)
    assert [run.run_id for run in result.contributing_runs] == [at_start["run_id"]]


@pytest.mark.parametrize(
    ("period", "reference", "expected_start", "expected_end"),
    [
        (
            "daily",
            datetime(2024, 2, 29, 13, 0, tzinfo=timezone.utc),
            datetime(2024, 2, 29, tzinfo=timezone.utc),
            datetime(2024, 3, 1, tzinfo=timezone.utc),
        ),
        (
            "weekly",
            datetime(2026, 3, 18, 13, 0, tzinfo=timezone.utc),
            datetime(2026, 3, 16, tzinfo=timezone.utc),
            datetime(2026, 3, 23, tzinfo=timezone.utc),
        ),
        (
            "monthly",
            datetime(2024, 2, 29, 13, 0, tzinfo=timezone.utc),
            datetime(2024, 2, 1, tzinfo=timezone.utc),
            datetime(2024, 3, 1, tzinfo=timezone.utc),
        ),
    ],
)
def test_period_boundaries(period, reference, expected_start, expected_end):
    assert period_bounds(period, reference) == (expected_start, expected_end)


def test_timezone_is_normalized_to_utc_for_period_selection():
    reference = datetime.fromisoformat("2026-03-01T00:30:00+02:00")
    assert period_bounds("monthly", reference) == (
        datetime(2026, 2, 1, tzinfo=timezone.utc),
        datetime(2026, 3, 1, tzinfo=timezone.utc),
    )


def test_warning_critical_exceeded_precedence_and_recommended_actions(
    client, test_session_factory
):
    application = register_application(client)
    now = datetime(2026, 3, 18, 12, tzinfo=timezone.utc)
    warning_policy = create_policy(
        client,
        application["id"],
        budget_kg_co2e=0.03,
        critical_threshold_percent=95,
        action="warn",
    ).json()
    run = simulate_run(client, application["id"], "warning-boundary")
    set_run_times(test_session_factory, [run["run_id"]], now)
    warning = evaluate_at(test_session_factory, warning_policy["id"], now)
    assert warning.utilization_percent == pytest.approx(80)
    assert warning.status == "warning"
    assert warning.recommended_action == "warn"

    throttle_policy = client.patch(
        f"/api/budget-policies/{warning_policy['id']}",
        json={
            "budget_kg_co2e": 0.048,
            "warning_threshold_percent": 40,
            "critical_threshold_percent": 50,
            "action": "recommend_throttle",
        },
    ).json()
    critical = evaluate_at(test_session_factory, throttle_policy["id"], now)
    assert critical.utilization_percent == pytest.approx(50)
    assert critical.status == "critical"
    assert critical.recommended_action == "recommend_throttle"

    above_100 = client.patch(
        f"/api/budget-policies/{warning_policy['id']}",
        json={"critical_threshold_percent": 150},
    ).json()
    exceeded = evaluate_at(test_session_factory, above_100["id"], now)
    assert exceeded.utilization_percent == pytest.approx(50)
    assert exceeded.status == "warning"
    assert exceeded.recommended_action == "warn"


def test_exceeded_takes_precedence_when_critical_threshold_is_over_100(
    client, test_session_factory
):
    application = register_application(client)
    policy = create_policy(
        client,
        application["id"],
        budget_kg_co2e=0.02,
        warning_threshold_percent=80,
        critical_threshold_percent=150,
        action="recommend_throttle",
    ).json()
    run = simulate_run(client, application["id"], "over-budget")
    now = datetime(2026, 3, 18, 12, tzinfo=timezone.utc)
    set_run_times(test_session_factory, [run["run_id"]], now)
    result = evaluate_at(test_session_factory, policy["id"], now)
    assert result.utilization_percent == pytest.approx(120)
    assert result.status == "exceeded"
    assert result.recommended_action == "recommend_throttle"


def test_monitor_action_never_recommends_intervention(client, test_session_factory):
    application = register_application(client)
    policy = create_policy(
        client, application["id"], budget_kg_co2e=0.01, action="monitor"
    ).json()
    run = simulate_run(client, application["id"], "monitor-over")
    now = datetime(2026, 3, 18, 12, tzinfo=timezone.utc)
    set_run_times(test_session_factory, [run["run_id"]], now)
    result = evaluate_at(test_session_factory, policy["id"], now)
    assert result.status == "exceeded"
    assert result.recommended_action == "monitor"


def test_application_status_and_evaluate_all_are_isolated(client):
    first = register_application(client, "Independent budget first")
    second = register_application(client, "Independent budget second")
    first_policy = create_policy(client, first["id"], budget_kg_co2e=1).json()
    second_policy = create_policy(client, second["id"], budget_kg_co2e=2).json()
    simulate_run(client, first["id"], "first-app-run")

    first_status = client.get(f"/api/applications/{first['id']}/budget-status")
    second_status = client.get(f"/api/applications/{second['id']}/budget-status")
    assert first_status.status_code == second_status.status_code == 200
    assert first_status.json()["policy_id"] == first_policy["id"]
    assert second_status.json()["policy_id"] == second_policy["id"]
    assert first_status.json()["contributing_run_count"] == 1
    assert second_status.json()["contributing_run_count"] == 0
    assert len(client.post("/api/budget-policies/evaluate").json()) == 2
    assert client.get("/api/applications/999/budget-status").status_code == 404


def test_application_deletion_is_restricted_while_budget_policy_exists(client):
    application = register_application(client)
    assert create_policy(client, application["id"]).status_code == 201
    assert client.delete(f"/api/applications/{application['id']}").status_code == 409


def test_api_evaluation_discloses_recommendation_only_and_recorded_sources(client):
    application = register_application(client)
    policy = create_policy(client, application["id"]).json()
    simulate_run(client, application["id"], "api-status-run")

    response = client.post(f"/api/budget-policies/{policy['id']}/evaluate")
    assert response.status_code == 200
    result = response.json()
    assert result["time_basis"] == "UTC"
    assert result["run_timestamp_field"] == "completed_at"
    assert result["enforcement_mode"] == "recommendation_only"
    assert result["consumption_source"] == "recorded_workload_run_estimates"
    assert result["contributing_runs"][0]["source"] == "simulated"
    assert result["contributing_runs"][0]["estimation_method"] == "power_duration"
