"""Read-only aggregates and exports over stored workload-run estimates."""

import csv
import io
import math
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application, BudgetPolicy, Workload, WorkloadRun
from app.schemas.analytics import (
    AnalyticsApplicationsRead,
    AnalyticsExportRow,
    AnalyticsOverviewRead,
    AnalyticsPoliciesRead,
    AnalyticsPolicyCounts,
    AnalyticsPolicySnapshot,
    AnalyticsTotals,
    AnalyticsTrendRead,
    AnalyticsWorkloadApplicationRead,
    AnalyticsWorkloadRunRead,
    AnalyticsWorkloadsRead,
    ApplicationAnalyticsDetailRead,
    ApplicationAnalyticsRead,
    TrendBucket,
)
from app.schemas.policies import BudgetEvaluationRead
from app.services.database import get_application_or_404
from app.services.policies import evaluate_policies, evaluate_policy

TrendInterval = Literal["daily", "weekly", "monthly"]
MAX_TREND_RANGE = timedelta(days=366)
MAX_EXPORT_ROWS = 10_000
MAX_ANALYTICS_RUNS = 5_000
MAX_POLICY_PAGE_SIZE = 100

_CSV_COLUMNS = [
    "record_type",
    "report_period_start_utc",
    "report_period_end_utc",
    "values_are_estimates",
    "policy_snapshot_at_utc",
    "application_id",
    "application_name",
    "workload_run_id",
    "completed_at_utc",
    "estimated_energy_kwh",
    "estimated_emissions_kg_co2e",
    "run_source",
    "estimation_method",
    "budget_policy_id",
    "budget_period",
    "configured_budget_kg_co2e",
    "current_policy_status",
    "current_recommended_action",
]


def resolve_time_range(
    start: datetime | None,
    end: datetime | None,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Resolve a complete timezone-aware UTC range, defaulting to the last 30 days."""
    if start is None and end is None:
        current = now or datetime.now(timezone.utc)
        current = _as_utc(current)
        return current - timedelta(days=30), current
    if start is None or end is None:
        raise HTTPException(
            status_code=422,
            detail="Both start and end must be supplied together",
        )
    if start.tzinfo is None or end.tzinfo is None:
        raise HTTPException(
            status_code=422,
            detail="start and end must include a UTC offset",
        )
    start_utc = _as_utc(start)
    end_utc = _as_utc(end)
    if start_utc >= end_utc:
        raise HTTPException(
            status_code=422,
            detail="start must be earlier than end",
        )
    if end_utc - start_utc > MAX_TREND_RANGE:
        raise HTTPException(
            status_code=422,
            detail="The requested time range must not exceed 366 days",
        )
    return start_utc, end_utc


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _bucket_start(value: datetime, interval: TrendInterval) -> datetime:
    current = _as_utc(value)
    day = datetime(current.year, current.month, current.day, tzinfo=timezone.utc)
    if interval == "daily":
        return day
    if interval == "weekly":
        return day - timedelta(days=day.weekday())
    return datetime(current.year, current.month, 1, tzinfo=timezone.utc)


def _next_bucket(value: datetime, interval: TrendInterval) -> datetime:
    if interval == "daily":
        return value + timedelta(days=1)
    if interval == "weekly":
        return value + timedelta(days=7)
    if value.month == 12:
        return datetime(value.year + 1, 1, 1, tzinfo=timezone.utc)
    return datetime(value.year, value.month + 1, 1, tzinfo=timezone.utc)


def _assert_finite(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise HTTPException(
            status_code=500,
            detail=f"Stored workload data produced a non-finite {label}",
        )
    return value


def _safe_csv_text(value: str | None) -> str | None:
    """Prefix spreadsheet formula-leading text while preserving its contents."""
    if value is None:
        return None
    for character in value:
        category = unicodedata.category(character)
        if character.isspace() or category.startswith("C") or category.startswith("Z"):
            continue
        if character in "=+-@":
            return f"'{value}"
        break
    return value


def _completed_run_aggregate(db: Session, application_ids: list[int] | None = None):
    statement = (
        select(
            WorkloadRun.application_id,
            func.count(WorkloadRun.id),
            func.coalesce(func.sum(WorkloadRun.energy_kwh), 0.0),
            func.coalesce(func.sum(WorkloadRun.emissions_kg_co2e), 0.0),
        )
        .where(WorkloadRun.status == "completed")
        .group_by(WorkloadRun.application_id)
    )
    if application_ids is not None:
        if not application_ids:
            return {}
        statement = statement.where(WorkloadRun.application_id.in_(application_ids))
    return {
        row[0]: {
            "count": int(row[1]),
            "energy": _assert_finite(float(row[2]), "energy total"),
            "emissions": _assert_finite(float(row[3]), "emissions total"),
        }
        for row in db.execute(statement)
    }


def get_trend(
    db: Session,
    *,
    start: datetime,
    end: datetime,
    interval: TrendInterval,
    application_id: int | None = None,
) -> AnalyticsTrendRead:
    """Return deterministic UTC buckets, including explicitly empty buckets."""
    start_utc, end_utc = resolve_time_range(start, end)
    selected_application = (
        get_application_or_404(db, application_id)
        if application_id is not None
        else None
    )

    utc_day = func.strftime("%Y-%m-%d", WorkloadRun.completed_at)
    statement = (
        select(
            utc_day,
            func.count(WorkloadRun.id),
            func.coalesce(func.sum(WorkloadRun.energy_kwh), 0.0),
            func.coalesce(func.sum(WorkloadRun.emissions_kg_co2e), 0.0),
        )
        .where(
            WorkloadRun.status == "completed",
            WorkloadRun.completed_at >= start_utc,
            WorkloadRun.completed_at < end_utc,
        )
        .group_by(utc_day)
        .order_by(utc_day)
    )
    if application_id is not None:
        statement = statement.where(WorkloadRun.application_id == application_id)

    daily_totals: dict[datetime, dict[str, float | int]] = {}
    for day_string, count, energy, emissions in db.execute(statement):
        day = datetime.strptime(day_string, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        daily_totals[day] = {
            "count": int(count),
            "energy": _assert_finite(float(energy), "energy bucket"),
            "emissions": _assert_finite(float(emissions), "emissions bucket"),
        }

    bucket_totals: dict[datetime, dict[str, float | int]] = defaultdict(
        lambda: {"count": 0, "energy": 0.0, "emissions": 0.0}
    )
    for day, totals in daily_totals.items():
        bucket = _bucket_start(day, interval)
        bucket_totals[bucket]["count"] += totals["count"]
        bucket_totals[bucket]["energy"] += totals["energy"]
        bucket_totals[bucket]["emissions"] += totals["emissions"]

    buckets = []
    bucket_start = _bucket_start(start_utc, interval)
    while bucket_start < end_utc:
        bucket_end = _next_bucket(bucket_start, interval)
        totals = bucket_totals[bucket_start]
        buckets.append(
            TrendBucket(
                period_start=bucket_start,
                period_end=bucket_end,
                estimated_energy_kwh=_assert_finite(
                    float(totals["energy"]), "energy bucket"
                ),
                estimated_emissions_kg_co2e=_assert_finite(
                    float(totals["emissions"]), "emissions bucket"
                ),
                completed_workload_run_count=int(totals["count"]),
                is_empty=int(totals["count"]) == 0,
            )
        )
        bucket_start = bucket_end

    return AnalyticsTrendRead(
        range_start=start_utc,
        range_end=end_utc,
        interval=interval,
        time_basis="UTC",
        range_semantics="half_open",
        data_source="recorded_completed_workload_runs",
        application_id=application_id,
        buckets=buckets,
    )


def get_workload_analytics(
    db: Session,
    *,
    start: datetime | None,
    end: datetime | None,
    application_id: int | None = None,
) -> AnalyticsWorkloadsRead:
    start_utc, end_utc = resolve_time_range(start, end)
    if application_id is not None:
        get_application_or_404(db, application_id)

    filters = [
        WorkloadRun.completed_at >= start_utc,
        WorkloadRun.completed_at < end_utc,
    ]
    if application_id is not None:
        filters.append(WorkloadRun.application_id == application_id)

    run_count = db.scalar(
        select(func.count(WorkloadRun.id)).where(*filters)
    ) or 0
    if run_count > MAX_ANALYTICS_RUNS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"The selected range contains more than {MAX_ANALYTICS_RUNS} runs. "
                "Choose a shorter date range."
            ),
        )

    status_counts = {
        row[0]: int(row[1])
        for row in db.execute(
            select(WorkloadRun.status, func.count(WorkloadRun.id))
            .where(*filters)
            .group_by(WorkloadRun.status)
        )
    }

    applications_query = select(Application).order_by(Application.name)
    if application_id is not None:
        applications_query = applications_query.where(Application.id == application_id)
    applications = list(db.scalars(applications_query))
    app_totals = {
        application.id: {"count": 0, "energy": 0.0, "emissions": 0.0}
        for application in applications
    }
    aggregate_rows = db.execute(
        select(
            WorkloadRun.application_id,
            func.count(WorkloadRun.id),
            func.coalesce(func.sum(WorkloadRun.energy_kwh), 0.0),
            func.coalesce(func.sum(WorkloadRun.emissions_kg_co2e), 0.0),
        )
        .where(*filters, WorkloadRun.status == "completed")
        .group_by(WorkloadRun.application_id)
    )
    for app_id, count, energy, emissions in aggregate_rows:
        app_totals[app_id] = {
            "count": int(count),
            "energy": _assert_finite(float(energy), "energy total"),
            "emissions": _assert_finite(float(emissions), "emissions total"),
        }

    run_statement = (
        select(WorkloadRun, Workload.name, Application.name)
        .join(Workload, Workload.id == WorkloadRun.workload_id)
        .join(Application, Application.id == WorkloadRun.application_id)
        .where(*filters)
        .order_by(WorkloadRun.completed_at, WorkloadRun.id)
    )
    runs = [
        AnalyticsWorkloadRunRead(
            run_id=run.id,
            application_id=run.application_id,
            application_name=app_name,
            name=workload_name,
            workload_type=run.workload_type,
            status=run.status,
            completed_at=run.completed_at,
            duration_seconds=run.duration_seconds,
            energy_kwh=run.energy_kwh,
            emissions_kg_co2e=run.emissions_kg_co2e,
        )
        for run, workload_name, app_name in db.execute(run_statement)
    ]

    return AnalyticsWorkloadsRead(
        range_start=start_utc,
        range_end=end_utc,
        time_basis="UTC",
        range_semantics="half_open",
        data_source="recorded_workload_runs",
        application_id=application_id,
        status_counts=status_counts,
        applications=[
            AnalyticsWorkloadApplicationRead(
                application_id=application.id,
                application_name=application.name,
                completed_workload_run_count=app_totals[application.id]["count"],
                estimated_energy_kwh=app_totals[application.id]["energy"],
                estimated_emissions_kg_co2e=app_totals[application.id]["emissions"],
            )
            for application in applications
        ],
        runs=runs,
    )


def _enabled_policy_evaluations(
    db: Session,
    reference_time: datetime,
    application_ids: list[int] | None = None,
) -> dict[int, BudgetEvaluationRead]:
    statement = select(BudgetPolicy).where(BudgetPolicy.enabled.is_(True))
    if application_ids is not None:
        if not application_ids:
            return {}
        statement = statement.where(BudgetPolicy.application_id.in_(application_ids))
    policies = list(db.scalars(statement.order_by(BudgetPolicy.id)))
    return {
        evaluation.application_id: evaluation
        for evaluation in evaluate_policies(db, policies, reference_time)
    }


def get_overview(db: Session) -> AnalyticsOverviewRead:
    evaluated_at = datetime.now(timezone.utc)
    run_totals = db.execute(
        select(
            func.count(WorkloadRun.id),
            func.coalesce(func.sum(WorkloadRun.energy_kwh), 0.0),
            func.coalesce(func.sum(WorkloadRun.emissions_kg_co2e), 0.0),
        ).where(WorkloadRun.status == "completed")
    ).one()
    evaluations_by_application = _enabled_policy_evaluations(db, evaluated_at)
    policy_evaluations = list(evaluations_by_application.values())
    applications = list(db.scalars(select(Application).order_by(Application.id)))
    aggregates = _completed_run_aggregate(db)
    application_items = []
    for application in applications:
        application_totals = aggregates.get(
            application.id, {"count": 0, "energy": 0.0, "emissions": 0.0}
        )
        application_items.append(
            ApplicationAnalyticsRead(
                application_id=application.id,
                application_name=application.name,
                application_description=application.description,
                owner=application.owner,
                application_status=application.status,
                totals_window="all_recorded_time",
                completed_workload_run_count=application_totals["count"],
                estimated_energy_kwh_all_time=application_totals["energy"],
                estimated_emissions_kg_co2e_all_time=application_totals["emissions"],
                enabled_policy_evaluation=evaluations_by_application.get(
                    application.id
                ),
            )
        )
    statuses = {status: 0 for status in ("within_budget", "warning", "critical", "exceeded")}
    for evaluation in policy_evaluations:
        statuses[evaluation.status] += 1
    registered_applications = db.scalar(
        select(func.count(Application.id))
    ) or 0
    enabled_policies = db.scalar(
        select(func.count(BudgetPolicy.id)).where(BudgetPolicy.enabled.is_(True))
    ) or 0
    return AnalyticsOverviewRead(
        evaluated_at=evaluated_at,
        registered_application_count=int(registered_applications),
        enabled_policy_count=int(enabled_policies),
        all_time_completed_workload_run_count=int(run_totals[0]),
        all_time_estimated_energy_kwh=_assert_finite(
            float(run_totals[1]), "energy total"
        ),
        all_time_estimated_emissions_kg_co2e=_assert_finite(
            float(run_totals[2]), "emissions total"
        ),
        run_metrics_window="all_recorded_time",
        policy_status_window="current_policy_periods",
        policy_status_counts=AnalyticsPolicyCounts(**statuses),
        recommended_intervention_count=sum(
            evaluation.recommended_action != "monitor"
            for evaluation in policy_evaluations
        ),
        policy_evaluations=policy_evaluations,
        applications=application_items,
    )


def get_application_comparison(
    db: Session,
    *,
    skip: int = 0,
    limit: int = 100,
) -> AnalyticsApplicationsRead:
    evaluated_at = datetime.now(timezone.utc)
    applications = list(
        db.scalars(
            select(Application)
            .order_by(Application.id)
            .offset(skip)
            .limit(limit)
        )
    )
    application_ids = [application.id for application in applications]
    aggregates = _completed_run_aggregate(db, application_ids)
    evaluations = _enabled_policy_evaluations(db, evaluated_at, application_ids)
    items = []
    for application in applications:
        totals = aggregates.get(
            application.id, {"count": 0, "energy": 0.0, "emissions": 0.0}
        )
        items.append(
            ApplicationAnalyticsRead(
                application_id=application.id,
                application_name=application.name,
                application_description=application.description,
                owner=application.owner,
                application_status=application.status,
                totals_window="all_recorded_time",
                completed_workload_run_count=totals["count"],
                estimated_energy_kwh_all_time=totals["energy"],
                estimated_emissions_kg_co2e_all_time=totals["emissions"],
                enabled_policy_evaluation=evaluations.get(application.id),
            )
        )
    return AnalyticsApplicationsRead(evaluated_at=evaluated_at, items=items)


def get_policy_snapshots(
    db: Session,
    *,
    skip: int = 0,
    limit: int = MAX_POLICY_PAGE_SIZE,
) -> AnalyticsPoliciesRead:
    evaluated_at = datetime.now(timezone.utc)
    policies = list(
        db.scalars(
            select(BudgetPolicy)
            .order_by(BudgetPolicy.id)
            .offset(skip)
            .limit(limit)
        )
    )
    application_ids = [policy.application_id for policy in policies]
    applications = {
        application.id: application
        for application in db.scalars(
            select(Application).where(Application.id.in_(application_ids))
        )
    } if application_ids else {}
    evaluations = _enabled_policy_evaluations(db, evaluated_at, application_ids)
    items = [
        AnalyticsPolicySnapshot(
            policy_id=policy.id,
            application_id=policy.application_id,
            application_name=applications[policy.application_id].name,
            enabled=policy.enabled,
            budget_kg_co2e=policy.budget_kg_co2e,
            period=policy.period,
            configured_action=policy.action,
            evaluation=evaluations.get(policy.application_id),
        )
        for policy in policies
    ]
    return AnalyticsPoliciesRead(
        evaluated_at=evaluated_at,
        evaluation_semantics="evaluated_on_request",
        items=items,
    )


def get_application_analytics(
    db: Session,
    *,
    application_id: int,
    start: datetime | None,
    end: datetime | None,
    interval: TrendInterval,
) -> ApplicationAnalyticsDetailRead:
    application = get_application_or_404(db, application_id)
    start_utc, end_utc = resolve_time_range(start, end)
    totals = _completed_run_aggregate(db, [application_id]).get(
        application_id, {"count": 0, "energy": 0.0, "emissions": 0.0}
    )
    policy = db.scalar(
        select(BudgetPolicy).where(
            BudgetPolicy.application_id == application_id,
            BudgetPolicy.enabled.is_(True),
        )
    )
    evaluated_at = datetime.now(timezone.utc)
    evaluation = (
        evaluate_policy(db, policy, evaluated_at) if policy is not None else None
    )
    trend = get_trend(
        db,
        start=start_utc,
        end=end_utc,
        interval=interval,
        application_id=application_id,
    )
    return ApplicationAnalyticsDetailRead(
        evaluated_at=evaluated_at,
        application=application,
        totals=AnalyticsTotals(
            completed_workload_run_count=totals["count"],
            estimated_energy_kwh=totals["energy"],
            estimated_emissions_kg_co2e=totals["emissions"],
        ),
        trend=trend,
        enabled_policy_evaluation=evaluation,
    )


def export_csv(
    db: Session,
    *,
    start: datetime,
    end: datetime,
    application_id: int | None = None,
) -> str:
    start_utc, end_utc = resolve_time_range(start, end)
    selected_application = (
        get_application_or_404(db, application_id)
        if application_id is not None
        else None
    )

    statement = (
        select(WorkloadRun, Application, BudgetPolicy)
        .join(Application, Application.id == WorkloadRun.application_id)
        .outerjoin(
            BudgetPolicy,
            BudgetPolicy.application_id == WorkloadRun.application_id,
        )
        .where(
            WorkloadRun.status == "completed",
            WorkloadRun.completed_at >= start_utc,
            WorkloadRun.completed_at < end_utc,
        )
        .order_by(WorkloadRun.completed_at, WorkloadRun.id)
        .limit(MAX_EXPORT_ROWS + 1)
    )
    if application_id is not None:
        statement = statement.where(WorkloadRun.application_id == application_id)
    rows = list(db.execute(statement))
    if len(rows) > MAX_EXPORT_ROWS:
        raise HTTPException(
            status_code=413,
            detail=f"Export is limited to {MAX_EXPORT_ROWS} workload runs",
        )

    evaluated_at = datetime.now(timezone.utc)
    evaluations = _enabled_policy_evaluations(
        db,
        evaluated_at,
        [application_id] if application_id is not None else None,
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=_CSV_COLUMNS,
        extrasaction="ignore",
        lineterminator="\r\n",
    )
    writer.writeheader()
    writer.writerow(
        {
            "record_type": "report_metadata",
            "report_period_start_utc": start_utc.isoformat(),
            "report_period_end_utc": end_utc.isoformat(),
            "values_are_estimates": "true",
            "policy_snapshot_at_utc": evaluated_at.isoformat(),
            "application_id": (
                selected_application.id if selected_application is not None else None
            ),
            "application_name": (
                _safe_csv_text(selected_application.name)
                if selected_application is not None
                else None
            ),
        }
    )
    for run, application, policy in rows:
        evaluation = evaluations.get(application.id)
        writer.writerow(
            {
                "record_type": "workload_run",
                "report_period_start_utc": start_utc.isoformat(),
                "report_period_end_utc": end_utc.isoformat(),
                "values_are_estimates": "true",
                "policy_snapshot_at_utc": evaluated_at.isoformat(),
                "application_id": application.id,
                "application_name": _safe_csv_text(application.name),
                "workload_run_id": run.id,
                "completed_at_utc": _as_utc(run.completed_at).isoformat(),
                "estimated_energy_kwh": run.energy_kwh,
                "estimated_emissions_kg_co2e": run.emissions_kg_co2e,
                "run_source": run.source,
                "estimation_method": run.estimation_method,
                "budget_policy_id": policy.id if policy else None,
                "budget_period": policy.period if policy else None,
                "configured_budget_kg_co2e": (
                    policy.budget_kg_co2e if policy else None
                ),
                "current_policy_status": evaluation.status if evaluation else None,
                "current_recommended_action": (
                    evaluation.recommended_action if evaluation else None
                ),
            }
        )
    return output.getvalue()
