"""UTC-period carbon-budget evaluation over recorded workload runs."""

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import BudgetPolicy, WorkloadRun
from app.schemas.policies import BudgetEvaluationRead

ROUNDING_DIGITS = 12
MAX_POLICY_EVALUATION_BATCH_SIZE = 100


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def period_bounds(period: str, reference_time: datetime) -> tuple[datetime, datetime]:
    """Return the UTC calendar period containing reference_time as [start, end)."""
    current = _as_utc(reference_time)
    start_of_day = datetime(
        current.year, current.month, current.day, tzinfo=timezone.utc
    )
    if period == "daily":
        start = start_of_day
        end = start + timedelta(days=1)
    elif period == "weekly":
        start = start_of_day - timedelta(days=current.weekday())
        end = start + timedelta(days=7)
    elif period == "monthly":
        start = datetime(current.year, current.month, 1, tzinfo=timezone.utc)
        if current.month == 12:
            end = datetime(current.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            end = datetime(current.year, current.month + 1, 1, tzinfo=timezone.utc)
    else:
        raise ValueError(f"Unsupported budget period: {period}")
    return start, end


def _recommended_action(policy: BudgetPolicy, status: str) -> str:
    if not policy.enabled or policy.action == "monitor":
        return "monitor"
    if policy.action == "warn":
        return "warn" if status != "within_budget" else "monitor"
    if status in {"critical", "exceeded"}:
        return "recommend_throttle"
    if status == "warning":
        return "warn"
    return "monitor"


def _finite_float(value: Decimal, field_name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise HTTPException(
            status_code=500,
            detail=f"Cannot evaluate policy: {field_name} is outside the supported numeric range",
        )
    return result


def _evaluate_policy_runs(
    policy: BudgetPolicy,
    period_start: datetime,
    period_end: datetime,
    runs: list[WorkloadRun],
) -> BudgetEvaluationRead:
    """Build one policy evaluation from its already-filtered run records."""
    with localcontext() as context:
        context.prec = 700
        consumed = Decimal(0)
        contributions = []
        for run in runs:
            emissions = Decimal(str(run.emissions_kg_co2e))
            if not emissions.is_finite() or emissions < 0:
                raise HTTPException(
                    status_code=500,
                    detail="Cannot evaluate policy: a recorded run has invalid emissions",
                )
            consumed += emissions
            contributions.append(
                {
                    "run_id": run.id,
                    "completed_at": _as_utc(run.completed_at),
                    "emissions_kg_co2e": float(emissions),
                    "source": run.source,
                    "estimation_method": run.estimation_method,
                }
            )

        budget = Decimal(str(policy.budget_kg_co2e))
        if not budget.is_finite() or budget <= 0:
            raise HTTPException(
                status_code=500,
                detail="Cannot evaluate policy: the stored budget is invalid",
            )
        utilization = consumed / budget * Decimal(100)
        remaining = budget - consumed
        warning = Decimal(str(policy.warning_threshold_percent))
        critical = Decimal(str(policy.critical_threshold_percent))
        if not utilization.is_finite():
            raise HTTPException(
                status_code=500,
                detail="Cannot evaluate policy: utilization is outside the supported numeric range",
            )
        if consumed > budget:
            policy_status = "exceeded"
        elif utilization >= critical:
            policy_status = "critical"
        elif utilization >= warning:
            policy_status = "warning"
        else:
            policy_status = "within_budget"

        consumed_result = consumed.quantize(Decimal("0.000000000001"))
        remaining_result = remaining.quantize(Decimal("0.000000000001"))
        utilization_result = utilization.quantize(Decimal("0.000001"))

    return BudgetEvaluationRead(
        policy_id=policy.id,
        application_id=policy.application_id,
        enabled=policy.enabled,
        period=policy.period,
        period_start=period_start,
        period_end=period_end,
        time_basis="UTC",
        run_timestamp_field="completed_at",
        budget_kg_co2e=float(budget),
        consumed_kg_co2e=_finite_float(consumed_result, "consumption"),
        remaining_kg_co2e=_finite_float(remaining_result, "remaining budget"),
        utilization_percent=_finite_float(utilization_result, "utilization"),
        status=policy_status,
        contributing_run_count=len(contributions),
        contributing_runs=contributions,
        configured_action=policy.action,
        recommended_action=_recommended_action(policy, policy_status),
        enforcement_mode="recommendation_only",
        consumption_source="recorded_workload_run_estimates",
    )


def evaluate_policy(
    db: Session,
    policy: BudgetPolicy,
    reference_time: datetime,
) -> BudgetEvaluationRead:
    """Evaluate one policy using completed runs in a single UTC calendar period."""
    now = _as_utc(reference_time)
    period_start, period_end = period_bounds(policy.period, now)
    runs = list(
        db.scalars(
            select(WorkloadRun)
            .where(
                WorkloadRun.application_id == policy.application_id,
                WorkloadRun.status == "completed",
                WorkloadRun.completed_at >= period_start,
                WorkloadRun.completed_at < period_end,
            )
            .order_by(WorkloadRun.completed_at, WorkloadRun.id)
        )
    )
    return _evaluate_policy_runs(policy, period_start, period_end, runs)


def evaluate_policies(
    db: Session,
    policies: list[BudgetPolicy],
    reference_time: datetime,
) -> list[BudgetEvaluationRead]:
    """Evaluate policies in bounded batches, loading runs once per batch."""
    now = _as_utc(reference_time)
    evaluations = []
    for offset in range(0, len(policies), MAX_POLICY_EVALUATION_BATCH_SIZE):
        batch = policies[offset : offset + MAX_POLICY_EVALUATION_BATCH_SIZE]
        period_by_application = {
            policy.application_id: period_bounds(policy.period, now)
            for policy in batch
        }
        run_windows = [
            and_(
                WorkloadRun.application_id == policy.application_id,
                WorkloadRun.completed_at >= period_by_application[
                    policy.application_id
                ][0],
                WorkloadRun.completed_at
                < period_by_application[policy.application_id][1],
            )
            for policy in batch
        ]
        statement = (
            select(WorkloadRun)
            .where(
                WorkloadRun.status == "completed",
                or_(*run_windows),
            )
            .order_by(WorkloadRun.completed_at, WorkloadRun.id)
        )
        runs_by_application: dict[int, list[WorkloadRun]] = {}
        for run in db.scalars(statement):
            runs_by_application.setdefault(run.application_id, []).append(run)

        for policy in batch:
            period_start, period_end = period_by_application[policy.application_id]
            evaluations.append(
                _evaluate_policy_runs(
                    policy,
                    period_start,
                    period_end,
                    runs_by_application.get(policy.application_id, []),
                )
            )
    return evaluations
