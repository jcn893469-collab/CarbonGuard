"""Shared database operations used by API route modules."""

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Application,
    BudgetPolicy,
    CarbonBudget,
    ExperimentResult,
    MonitoringRecord,
    PolicyEvent,
    Workload,
    WorkloadRun,
)


def commit_or_conflict(db: Session, detail: str) -> None:
    """Commit a write and translate integrity violations to a clear conflict."""
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=detail) from exc


def get_application_or_404(db: Session, application_id: int) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


def get_budget_or_404(db: Session, budget_id: int) -> CarbonBudget:
    budget = db.get(CarbonBudget, budget_id)
    if budget is None:
        raise HTTPException(status_code=404, detail="Carbon budget not found")
    return budget


def get_workload_or_404(db: Session, workload_id: int) -> Workload:
    workload = db.get(Workload, workload_id)
    if workload is None:
        raise HTTPException(status_code=404, detail="Workload not found")
    return workload


def get_monitoring_record_or_404(db: Session, record_id: int) -> MonitoringRecord:
    record = db.get(MonitoringRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Monitoring record not found")
    return record


def get_policy_event_or_404(db: Session, event_id: int) -> PolicyEvent:
    event = db.get(PolicyEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Policy event not found")
    return event


def get_experiment_or_404(db: Session, experiment_id: int) -> ExperimentResult:
    experiment = db.get(ExperimentResult, experiment_id)
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment result not found")
    return experiment


def application_has_history(db: Session, application_id: int) -> bool:
    """Return whether any dependent record prevents safe application deletion."""
    dependent_models = (
        CarbonBudget,
        BudgetPolicy,
        Workload,
        MonitoringRecord,
        PolicyEvent,
        WorkloadRun,
    )
    return any(
        db.scalar(
            select(func.count())
            .select_from(model)
            .where(model.application_id == application_id)
        )
        for model in dependent_models
    )
