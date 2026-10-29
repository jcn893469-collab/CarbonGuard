"""Workload, monitoring, policy-event, and experiment storage endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.parameters import DatabasePathId
from app.models import (
    ExperimentResult,
    MonitoringRecord,
    PolicyEvent,
    Workload,
)
from app.schemas.records import (
    ExperimentResultCreate,
    ExperimentResultRead,
    MonitoringRecordCreate,
    MonitoringRecordRead,
    PolicyEventRead,
    WorkloadCreate,
    WorkloadRead,
)
from app.services.database import (
    commit_or_conflict,
    get_application_or_404,
    get_experiment_or_404,
    get_monitoring_record_or_404,
    get_policy_event_or_404,
    get_workload_or_404,
)

router = APIRouter(tags=["application records"])
Database = Annotated[Session, Depends(get_db)]


@router.post(
    "/applications/{application_id}/workloads",
    response_model=WorkloadRead,
    status_code=status.HTTP_201_CREATED,
)
def register_workload(
    application_id: DatabasePathId,
    payload: WorkloadCreate,
    db: Database,
) -> Workload:
    get_application_or_404(db, application_id)
    workload = Workload(application_id=application_id, **payload.model_dump())
    db.add(workload)
    commit_or_conflict(db, "Workload violates a database constraint")
    db.refresh(workload)
    return workload


@router.get(
    "/applications/{application_id}/workloads",
    response_model=list[WorkloadRead],
)
def list_workloads(
    application_id: DatabasePathId,
    db: Database,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[Workload]:
    get_application_or_404(db, application_id)
    return list(
        db.scalars(
            select(Workload)
            .where(Workload.application_id == application_id)
            .order_by(Workload.id)
            .offset(skip)
            .limit(limit)
        )
    )


@router.get("/workloads/{workload_id}", response_model=WorkloadRead)
def read_workload(workload_id: DatabasePathId, db: Database) -> Workload:
    return get_workload_or_404(db, workload_id)


@router.get(
    "/applications/{application_id}/monitoring-records",
    response_model=list[MonitoringRecordRead],
)
def list_monitoring_records(
    application_id: DatabasePathId,
    db: Database,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[MonitoringRecord]:
    get_application_or_404(db, application_id)
    return list(
        db.scalars(
            select(MonitoringRecord)
            .where(MonitoringRecord.application_id == application_id)
            .order_by(MonitoringRecord.recorded_at.desc(), MonitoringRecord.id.desc())
            .offset(skip)
            .limit(limit)
        )
    )


@router.post(
    "/applications/{application_id}/monitoring-records",
    response_model=MonitoringRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def create_monitoring_record(
    application_id: DatabasePathId,
    payload: MonitoringRecordCreate,
    db: Database,
) -> MonitoringRecord:
    get_application_or_404(db, application_id)
    record = MonitoringRecord(application_id=application_id, **payload.model_dump())
    db.add(record)
    commit_or_conflict(db, "Monitoring record violates a database constraint")
    db.refresh(record)
    return record


@router.get(
    "/monitoring-records/{record_id}",
    response_model=MonitoringRecordRead,
)
def read_monitoring_record(record_id: DatabasePathId, db: Database) -> MonitoringRecord:
    return get_monitoring_record_or_404(db, record_id)


@router.get(
    "/applications/{application_id}/policy-events",
    response_model=list[PolicyEventRead],
)
def list_policy_events(
    application_id: DatabasePathId,
    db: Database,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[PolicyEvent]:
    get_application_or_404(db, application_id)
    return list(
        db.scalars(
            select(PolicyEvent)
            .where(PolicyEvent.application_id == application_id)
            .order_by(PolicyEvent.created_at.desc(), PolicyEvent.id.desc())
            .offset(skip)
            .limit(limit)
        )
    )


@router.get("/policy-events/{event_id}", response_model=PolicyEventRead)
def read_policy_event(event_id: DatabasePathId, db: Database) -> PolicyEvent:
    return get_policy_event_or_404(db, event_id)


@router.get("/experiments", response_model=list[ExperimentResultRead])
def list_experiments(
    db: Database,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[ExperimentResult]:
    return list(
        db.scalars(
            select(ExperimentResult)
            .order_by(ExperimentResult.created_at.desc(), ExperimentResult.id.desc())
            .offset(skip)
            .limit(limit)
        )
    )


@router.post(
    "/experiments",
    response_model=ExperimentResultRead,
    status_code=status.HTTP_201_CREATED,
)
def create_experiment(
    payload: ExperimentResultCreate,
    db: Database,
) -> ExperimentResult:
    experiment = ExperimentResult(**payload.model_dump())
    db.add(experiment)
    commit_or_conflict(db, "Experiment result violates a database constraint")
    db.refresh(experiment)
    return experiment


@router.get("/experiments/{experiment_id}", response_model=ExperimentResultRead)
def read_experiment(experiment_id: DatabasePathId, db: Database) -> ExperimentResult:
    return get_experiment_or_404(db, experiment_id)
