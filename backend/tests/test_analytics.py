import csv
import io
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event, text


def create_application(client, name):
    response = client.post("/api/applications", json={"name": name})
    assert response.status_code == 201
    return response.json()


def create_policy(client, application_id, **overrides):
    payload = {
        "application_id": application_id,
        "budget_kg_co2e": 0.05,
        "period": "daily",
        "action": "recommend_throttle",
    } | overrides
    response = client.post("/api/budget-policies", json=payload)
    assert response.status_code == 201
    return response.json()


def simulate(client, application_id, name, average_power=120):
    response = client.post(
        "/api/workloads/simulate",
        json={
            "application_id": application_id,
            "name": name,
            "workload_type": "cpu-bound",
            "duration_seconds": 1800,
            "average_power_w": average_power,
            "carbon_intensity_g_per_kwh": 400,
            "seed": 12,
        },
    )
    assert response.status_code == 201
    return response.json()


def set_run_times(test_session_factory, run_ids, timestamp):
    from app.models import WorkloadRun

    with test_session_factory() as db:
        for run_id in run_ids:
            db.get(WorkloadRun, run_id).completed_at = timestamp
        db.commit()


def iso(value):
    return value.isoformat().replace("+00:00", "Z")


def test_overview_returns_explicit_empty_all_time_and_current_windows(client):
    response = client.get("/api/analytics/overview")
    assert response.status_code == 200
    result = response.json()
    assert result["registered_application_count"] == 0
    assert result["enabled_policy_count"] == 0
    assert result["all_time_completed_workload_run_count"] == 0
    assert result["all_time_estimated_energy_kwh"] == 0
    assert result["all_time_estimated_emissions_kg_co2e"] == 0
    assert result["run_metrics_window"] == "all_recorded_time"
    assert result["policy_status_window"] == "current_policy_periods"
    assert result["policy_status_counts"] == {
        "within_budget": 0,
        "warning": 0,
        "critical": 0,
        "exceeded": 0,
    }
    assert result["policy_evaluations"] == []
    assert result["applications"] == []


def test_overview_aggregates_multiple_applications_once_and_evaluates_current_policies(
    client,
):
    first = create_application(client, "First analytics app")
    second = create_application(client, "Second analytics app")
    create_policy(client, first["id"], budget_kg_co2e=0.024)
    create_policy(client, second["id"], budget_kg_co2e=0.1)
    simulate(client, first["id"], "first-overview-run")
    simulate(client, first["id"], "second-overview-run")
    simulate(client, second["id"], "third-overview-run", average_power=60)

    result = client.get("/api/analytics/overview").json()
    assert result["registered_application_count"] == 2
    assert result["enabled_policy_count"] == 2
    assert result["all_time_completed_workload_run_count"] == 3
    assert result["all_time_estimated_energy_kwh"] == 0.15
    assert result["all_time_estimated_emissions_kg_co2e"] == 0.06
    assert result["policy_status_counts"] == {
        "within_budget": 1,
        "warning": 0,
        "critical": 0,
        "exceeded": 1,
    }
    assert result["recommended_intervention_count"] == 1
    assert len(result["policy_evaluations"]) == 2


def test_trends_zero_fill_empty_daily_buckets_and_use_half_open_range(
    client, test_session_factory
):
    application = create_application(client, "Trend boundaries")
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=3)
    before = simulate(client, application["id"], "trend-before")
    at_start = simulate(client, application["id"], "trend-start")
    at_end = simulate(client, application["id"], "trend-end")
    set_run_times(
        test_session_factory,
        [before["run_id"], at_start["run_id"], at_end["run_id"]],
        start,
    )
    set_run_times(
        test_session_factory,
        [before["run_id"]],
        start - timedelta(microseconds=1),
    )
    set_run_times(test_session_factory, [at_end["run_id"]], end)

    response = client.get(
        "/api/analytics/trends",
        params={"start": iso(start), "end": iso(end), "interval": "daily"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["time_basis"] == "UTC"
    assert result["range_semantics"] == "half_open"
    assert len(result["buckets"]) == 3
    assert [bucket["period_start"] for bucket in result["buckets"]] == [
        iso(start),
        iso(start + timedelta(days=1)),
        iso(start + timedelta(days=2)),
    ]
    assert result["buckets"][0]["completed_workload_run_count"] == 1
    assert result["buckets"][0]["estimated_energy_kwh"] == 0.06
    assert result["buckets"][0]["estimated_emissions_kg_co2e"] == 0.024
    assert result["buckets"][1]["is_empty"] is True
    assert result["buckets"][1]["estimated_emissions_kg_co2e"] == 0


def test_weekly_and_monthly_trends_are_chronological(client, test_session_factory):
    application = create_application(client, "Trend aggregation")
    first = simulate(client, application["id"], "weekly-trend-one")
    second = simulate(client, application["id"], "monthly-trend-two")
    first_day = datetime(2026, 5, 4, 12, tzinfo=timezone.utc)
    second_day = datetime(2026, 5, 19, 12, tzinfo=timezone.utc)
    set_run_times(test_session_factory, [first["run_id"]], first_day)
    set_run_times(test_session_factory, [second["run_id"]], second_day)
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    end = datetime(2026, 6, 1, tzinfo=timezone.utc)

    weekly = client.get(
        "/api/analytics/trends",
        params={"start": iso(start), "end": iso(end), "interval": "weekly"},
    ).json()
    monthly = client.get(
        "/api/analytics/trends",
        params={"start": iso(start), "end": iso(end), "interval": "monthly"},
    ).json()
    assert [item["period_start"] for item in weekly["buckets"]] == sorted(
        item["period_start"] for item in weekly["buckets"]
    )
    assert weekly["buckets"][0]["period_start"] == "2026-04-27T00:00:00Z"
    assert sum(item["completed_workload_run_count"] for item in weekly["buckets"]) == 2
    assert len(monthly["buckets"]) == 1
    assert monthly["buckets"][0]["period_start"] == "2026-05-01T00:00:00Z"
    assert monthly["buckets"][0]["estimated_emissions_kg_co2e"] == 0.048


def test_trend_validates_ranges_interval_timezone_and_application(client):
    valid = {
        "start": "2026-05-01T00:00:00Z",
        "end": "2026-05-02T00:00:00Z",
    }
    assert client.get("/api/analytics/trends", params=valid).status_code == 200
    assert client.get(
        "/api/analytics/trends",
        params={"start": valid["start"], "interval": "daily"},
    ).status_code == 422
    assert client.get(
        "/api/analytics/trends",
        params={"start": "2026-05-02T00:00:00Z", "end": valid["start"]},
    ).status_code == 422
    assert client.get(
        "/api/analytics/trends",
        params={
            "start": "2026-05-01T00:00:00",
            "end": "2026-05-02T00:00:00",
        },
    ).status_code == 422
    assert client.get(
        "/api/analytics/trends",
        params={
            "start": "2025-01-01T00:00:00Z",
            "end": "2026-06-01T00:00:00Z",
        },
    ).status_code == 422
    assert client.get(
        "/api/analytics/trends",
        params=valid | {"interval": "hourly"},
    ).status_code == 422
    assert client.get(
        "/api/analytics/trends",
        params=valid | {"application_id": 999},
    ).status_code == 404


def test_workload_analytics_filters_utc_range_and_excludes_failed_energy(
    client, test_session_factory
):
    from app.models import WorkloadRun

    first = create_application(client, "Filtered analytics first")
    second = create_application(client, "Filtered analytics second")
    inside = simulate(client, first["id"], "inside-range")
    failed = simulate(client, first["id"], "failed-run")
    outside = simulate(client, second["id"], "outside-range")
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    set_run_times(test_session_factory, [inside["run_id"]], start)
    set_run_times(test_session_factory, [failed["run_id"]], start)
    set_run_times(test_session_factory, [outside["run_id"]], end)
    with test_session_factory() as db:
        db.get(WorkloadRun, failed["run_id"]).status = "failed"
        db.commit()

    response = client.get(
        "/api/analytics/workloads",
        params={
            "start": iso(start),
            "end": iso(end),
            "application_id": first["id"],
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["range_semantics"] == "half_open"
    assert result["status_counts"] == {"completed": 1, "failed": 1}
    assert {run["run_id"] for run in result["runs"]} == {
        inside["run_id"],
        failed["run_id"],
    }
    assert len(result["applications"]) == 1
    assert result["applications"][0]["application_name"] == first["name"]
    assert result["applications"][0]["completed_workload_run_count"] == 1
    assert result["applications"][0]["estimated_energy_kwh"] == 0.06
    assert result["applications"][0]["estimated_emissions_kg_co2e"] == 0.024


def test_workload_analytics_returns_zero_application_totals_for_empty_range(client):
    application = create_application(client, "Empty analytics application")
    response = client.get(
        "/api/analytics/workloads",
        params={
            "start": "2026-05-01T00:00:00Z",
            "end": "2026-05-02T00:00:00Z",
            "application_id": application["id"],
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["runs"] == []
    assert result["status_counts"] == {}
    assert result["applications"] == [{
        "application_id": application["id"],
        "application_name": application["name"],
        "completed_workload_run_count": 0,
        "estimated_energy_kwh": 0,
        "estimated_emissions_kg_co2e": 0,
    }]


def test_application_comparison_includes_zero_run_and_disabled_policy(client):
    first = create_application(client, "Application with history")
    second = create_application(client, "Application without runs")
    create_policy(client, first["id"], budget_kg_co2e=0.024)
    create_policy(client, second["id"], enabled=False)
    simulate(client, first["id"], "application-comparison-run")

    response = client.get("/api/analytics/applications?skip=0&limit=10")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert items[0]["completed_workload_run_count"] == 1
    assert items[0]["estimated_emissions_kg_co2e_all_time"] == 0.024
    assert items[0]["enabled_policy_evaluation"]["status"] == "critical"
    assert items[1]["completed_workload_run_count"] == 0
    assert items[1]["estimated_emissions_kg_co2e_all_time"] == 0
    assert items[1]["enabled_policy_evaluation"] is None


def test_policy_overview_states_are_current_request_evaluations(client):
    app = create_application(client, "Current policy snapshot")
    create_policy(client, app["id"])
    result = client.get("/api/analytics/policies").json()

    assert result["evaluation_semantics"] == "evaluated_on_request"
    assert len(result["items"]) == 1
    policy = result["items"][0]
    assert policy["application_name"] == app["name"]
    assert policy["evaluation"]["status"] == "within_budget"
    assert policy["evaluation"]["recommended_action"] == "monitor"
    assert (
        policy["evaluation"]["period_start"]
        <= result["evaluated_at"]
        < policy["evaluation"]["period_end"]
    )


def test_application_detail_analytics_has_current_period_and_selected_trend(
    client, test_session_factory
):
    application = create_application(client, "Detail analytics")
    create_policy(client, application["id"])
    run = simulate(client, application["id"], "detail-run")
    now = datetime.now(timezone.utc)
    set_run_times(test_session_factory, [run["run_id"]], now)
    start = now - timedelta(days=1)
    end = now + timedelta(days=1)

    response = client.get(
        f"/api/analytics/applications/{application['id']}",
        params={
            "start": iso(start),
            "end": iso(end),
            "interval": "daily",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["application"]["id"] == application["id"]
    assert data["totals"]["completed_workload_run_count"] == 1
    assert data["enabled_policy_evaluation"]["contributing_run_count"] == 1
    assert data["trend"]["application_id"] == application["id"]
    assert client.get("/api/analytics/applications/999").status_code == 404


def test_csv_export_escapes_fields_reports_metadata_and_isolates_applications(
    client, test_session_factory
):
    selected = create_application(client, 'Run "quoted", app\nline')
    unrelated = create_application(client, "Unrelated application")
    create_policy(client, selected["id"])
    create_policy(client, unrelated["id"])
    selected_run = simulate(client, selected["id"], "csv-selected")
    unrelated_run = simulate(client, unrelated["id"], "csv-unrelated")
    now = datetime.now(timezone.utc)
    set_run_times(
        test_session_factory,
        [selected_run["run_id"], unrelated_run["run_id"]],
        now,
    )
    params = {
        "start": iso(now - timedelta(days=1)),
        "end": iso(now + timedelta(days=1)),
        "application_id": selected["id"],
    }

    response = client.get("/api/analytics/export.csv", params=params)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["cache-control"] == "no-store"
    assert f'application-{selected["id"]}-report.csv' in response.headers[
        "content-disposition"
    ]
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows[0]["record_type"] == "report_metadata"
    assert rows[0]["values_are_estimates"] == "true"
    run_rows = [row for row in rows if row["record_type"] == "workload_run"]
    assert len(run_rows) == 1
    assert run_rows[0]["application_name"] == selected["name"]
    assert run_rows[0]["workload_run_id"] == selected_run["run_id"]
    assert run_rows[0]["workload_run_id"] != unrelated_run["run_id"]
    assert run_rows[0]["estimated_energy_kwh"] == "0.06"
    assert run_rows[0]["estimated_emissions_kg_co2e"] == "0.024"
    assert run_rows[0]["current_policy_status"] in {
        "warning",
        "critical",
        "exceeded",
        "within_budget",
    }
    escaped_name = io.StringIO(newline="")
    csv.writer(escaped_name, lineterminator="\r\n").writerow([selected["name"]])
    assert escaped_name.getvalue().strip("\r\n") in response.text


def test_csv_export_rejects_invalid_range_and_unknown_application(client):
    now = datetime.now(timezone.utc)
    params = {
        "start": iso(now),
        "end": iso(now + timedelta(days=1)),
    }
    assert client.get("/api/analytics/export.csv", params=params).status_code == 200
    assert client.get(
        "/api/analytics/export.csv",
        params=params | {"application_id": 999},
    ).status_code == 404
    assert client.get(
        "/api/analytics/export.csv",
        params={"start": iso(now), "end": iso(now)},
    ).status_code == 422


@pytest.mark.parametrize(
    "formula",
    [
        "=HYPERLINK(\"https://example.invalid\")",
        "+1+1",
        "-1+1",
        "@SUM(1,1)",
    ],
)
def test_csv_export_neutralizes_spreadsheet_formula_names(client, formula):
    name = f"\x00\t {formula}"
    application = create_application(client, name)
    run = simulate(client, application["id"], "csv-injection-run")
    response = client.get(
        "/api/analytics/export.csv",
        params={
            "start": iso(datetime.now(timezone.utc) - timedelta(days=1)),
            "end": iso(datetime.now(timezone.utc) + timedelta(days=1)),
            "application_id": application["id"],
        },
    )

    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert rows[0]["record_type"] == "report_metadata"
    assert rows[0]["application_name"] == f"'{name}"
    run_rows = [row for row in rows if row["record_type"] == "workload_run"]
    assert len(run_rows) == 1
    assert run_rows[0]["application_name"] == f"'{name}"
    assert run_rows[0]["workload_run_id"] == run["run_id"]
    assert client.get(f"/api/applications/{application['id']}").json()["name"] == name


def test_analytics_policy_listing_is_paginated_and_validates_bounds(client):
    first = create_application(client, "First paged policy")
    second = create_application(client, "Second paged policy")
    create_policy(client, first["id"])
    create_policy(client, second["id"])

    first_page = client.get("/api/analytics/policies?skip=0&limit=1")
    second_page = client.get("/api/analytics/policies?skip=1&limit=1")
    assert first_page.status_code == second_page.status_code == 200
    assert first_page.json()["items"][0]["application_id"] == first["id"]
    assert second_page.json()["items"][0]["application_id"] == second["id"]
    assert client.get("/api/analytics/policies?limit=101").status_code == 422


def test_analytics_reads_do_not_mutate_recorded_run_history(client):
    application = create_application(client, "Read-only analytics")
    create_policy(client, application["id"])
    run = simulate(client, application["id"], "read-only-run")

    first = client.get("/api/analytics/overview").json()
    second = client.get("/api/analytics/overview").json()
    evaluation = client.post("/api/budget-policies/1/evaluate").json()
    stored = client.get(f"/api/workload-runs/{run['run_id']}").json()

    assert first["all_time_completed_workload_run_count"] == 1
    assert second["all_time_completed_workload_run_count"] == 1
    assert evaluation["contributing_run_count"] == 1
    assert stored["energy_kwh"] == run["energy_kwh"]
    assert stored["emissions_kg_co2e"] == run["emissions_kg_co2e"]


def test_overview_batches_policy_run_queries(client, test_session_factory):
    applications = [
        create_application(client, f"Batch policy app {index}")
        for index in range(3)
    ]
    for index, application in enumerate(applications):
        create_policy(client, application["id"])
        simulate(client, application["id"], f"batch-policy-run-{index}")

    engine = test_session_factory.kw["bind"]
    run_queries = []

    def record_workload_queries(
        _connection,
        _cursor,
        statement,
        _parameters,
        _context,
        _executemany,
    ):
        if "from workload_runs" in statement.lower():
            run_queries.append(statement)

    event.listen(engine, "before_cursor_execute", record_workload_queries)
    try:
        response = client.get("/api/analytics/overview")
    finally:
        event.remove(engine, "before_cursor_execute", record_workload_queries)

    assert response.status_code == 200
    assert len(response.json()["policy_evaluations"]) == 3
    assert len(run_queries) == 3


def test_time_filtered_analytics_queries_use_composite_run_indexes(
    test_session_factory,
):
    with test_session_factory() as db:
        global_plan = db.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM workload_runs "
                "WHERE status = :status AND completed_at >= :start "
                "AND completed_at < :end"
            ),
            {
                "status": "completed",
                "start": "2026-10-01T00:00:00+00:00",
                "end": "2026-10-02T00:00:00+00:00",
            },
        ).all()
        application_plan = db.execute(
            text(
                "EXPLAIN QUERY PLAN SELECT id FROM workload_runs "
                "WHERE application_id = :application_id AND status = :status "
                "AND completed_at >= :start AND completed_at < :end"
            ),
            {
                "application_id": 1,
                "status": "completed",
                "start": "2026-10-01T00:00:00+00:00",
                "end": "2026-10-02T00:00:00+00:00",
            },
        ).all()

    assert any(
        "ix_workload_runs_status_completed_at" in str(row)
        for row in global_plan
    )
    assert any(
        "ix_workload_runs_application_status_completed_at" in str(row)
        for row in application_plan
    )
