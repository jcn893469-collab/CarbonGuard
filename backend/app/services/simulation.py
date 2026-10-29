"""Bounded, reproducible workload-profile simulation."""

import random
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Workload, WorkloadRun
from app.schemas.estimates import EstimateRequest
from app.schemas.simulation import WorkloadSimulationRequest
from app.services.database import commit_or_conflict
from app.services.estimation import estimate_energy_and_emissions

PROFILE_SAMPLE_COUNT = 60
PROFILE_VARIATION = {
    "cpu-bound": (0.65, 1.35),
    "memory-bound": (0.9, 1.1),
    "mixed": (0.5, 1.5),
}


def _generate_relative_profile(
    workload_type: str,
    seed: int | None,
) -> dict[str, float | int | list[float]]:
    """Generate bounded relative power factors without running host workloads."""
    lower, upper = PROFILE_VARIATION[workload_type]
    generator = random.Random(seed)
    raw_factors = [
        generator.uniform(lower, upper) for _ in range(PROFILE_SAMPLE_COUNT)
    ]
    mean_factor = sum(raw_factors) / PROFILE_SAMPLE_COUNT
    normalized = [factor / mean_factor for factor in raw_factors]
    return {
        "sample_count": PROFILE_SAMPLE_COUNT,
        "relative_power_factors": [round(factor, 10) for factor in normalized],
        "minimum_relative_power": round(min(normalized), 10),
        "maximum_relative_power": round(max(normalized), 10),
        "mean_relative_power": round(sum(normalized) / PROFILE_SAMPLE_COUNT, 10),
        "variation_range": [lower, upper],
    }


def _serialize_run(run: WorkloadRun, workload_name: str) -> dict:
    return {
        "run_id": run.id,
        "application_id": run.application_id,
        "workload_id": run.workload_id,
        "name": workload_name,
        "workload_type": run.workload_type,
        "status": run.status,
        "parameters": run.parameters_json,
        "profile": run.profile_json,
        "simulation_started_at": run.simulation_started_at,
        "completed_at": run.completed_at,
        "average_power_w": run.average_power_w,
        "duration_seconds": run.duration_seconds,
        "carbon_intensity_g_per_kwh": run.carbon_intensity_g_per_kwh,
        "energy_kwh": run.energy_kwh,
        "emissions_kg_co2e": run.emissions_kg_co2e,
        "estimation_method": run.estimation_method,
        "source": "simulated",
        "estimation_source": "estimated",
    }


def _run_with_workload(db: Session, run: WorkloadRun) -> dict:
    workload = db.get(Workload, run.workload_id)
    if workload is None:
        raise HTTPException(status_code=404, detail="Workload definition not found")
    return _serialize_run(run, workload.name)


def simulate_workload(
    db: Session,
    request: WorkloadSimulationRequest,
) -> dict:
    """Create/reuse a workload definition, simulate a profile, and persist its run."""
    application = db.get(Application, request.application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")

    workload = db.scalar(
        select(Workload).where(
            Workload.application_id == request.application_id,
            Workload.name == request.name,
        )
    )
    if workload is not None and workload.workload_type != request.workload_type:
        raise HTTPException(
            status_code=409,
            detail="A workload with this name is already registered with a different type",
        )
    if workload is None:
        workload = Workload(
            application_id=request.application_id,
            name=request.name,
            workload_type=request.workload_type,
            status="registered",
        )
        db.add(workload)
        db.flush()

    started_at = datetime.now(timezone.utc)
    profile = _generate_relative_profile(request.workload_type, request.seed)
    try:
        estimate = estimate_energy_and_emissions(
            EstimateRequest(
                average_power_w=request.average_power_w,
                duration_seconds=request.duration_seconds,
                carbon_intensity_g_per_kwh=request.carbon_intensity_g_per_kwh,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    completed_at = datetime.now(timezone.utc)

    run = WorkloadRun(
        application_id=application.id,
        workload_id=workload.id,
        workload_type=request.workload_type,
        duration_seconds=request.duration_seconds,
        average_power_w=request.average_power_w,
        carbon_intensity_g_per_kwh=request.carbon_intensity_g_per_kwh,
        cpu_utilization_percent=request.cpu_utilization_percent,
        seed=request.seed,
        parameters_json=request.model_dump(mode="json"),
        profile_json=profile,
        energy_kwh=estimate.energy_kwh,
        emissions_kg_co2e=estimate.emissions_kg_co2e,
        estimation_method=estimate.estimation_method,
        source="simulated",
        status="completed",
        simulation_started_at=started_at,
        completed_at=completed_at,
    )
    db.add(run)
    commit_or_conflict(db, "Workload run could not be saved")
    db.refresh(run)
    return _serialize_run(run, workload.name)


def get_workload_run(db: Session, run_id: str) -> dict:
    run = db.get(WorkloadRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Workload run not found")
    return _run_with_workload(db, run)


def list_workload_runs(
    db: Session,
    *,
    application_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[dict]:
    statement = select(WorkloadRun)
    if application_id is not None:
        statement = statement.where(WorkloadRun.application_id == application_id)
    runs = db.scalars(
        statement.order_by(WorkloadRun.simulation_started_at.desc(), WorkloadRun.id)
        .offset(skip)
        .limit(limit)
    )
    return [_run_with_workload(db, run) for run in runs]
