"""Workload simulation and run-history endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.parameters import DatabasePathId
from app.schemas.simulation import WorkloadRunRead, WorkloadSimulationRequest
from app.services.database import get_application_or_404
from app.services.simulation import (
    get_workload_run,
    list_workload_runs,
    simulate_workload,
)

router = APIRouter(tags=["workload simulation"])
Database = Annotated[Session, Depends(get_db)]


@router.post(
    "/workloads/simulate",
    response_model=WorkloadRunRead,
    status_code=status.HTTP_201_CREATED,
)
def simulate_workload_endpoint(
    request: WorkloadSimulationRequest,
    db: Database,
) -> dict:
    return simulate_workload(db, request)


@router.get("/workload-runs", response_model=list[WorkloadRunRead])
def read_workload_runs(
    db: Database,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict]:
    return list_workload_runs(db, skip=skip, limit=limit)


@router.get(
    "/applications/{application_id}/workload-runs",
    response_model=list[WorkloadRunRead],
)
def read_application_workload_runs(
    application_id: DatabasePathId,
    db: Database,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict]:
    get_application_or_404(db, application_id)
    return list_workload_runs(
        db,
        application_id=application_id,
        skip=skip,
        limit=limit,
    )


@router.get("/workload-runs/{run_id}", response_model=WorkloadRunRead)
def read_workload_run(run_id: str, db: Database) -> dict:
    if len(run_id) != 36:
        raise HTTPException(status_code=404, detail="Workload run not found")
    return get_workload_run(db, run_id)
