"""Application and carbon-budget management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.parameters import DatabasePathId
from app.models import Application, CarbonBudget
from app.schemas.applications import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationUpdate,
    CarbonBudgetCreate,
    CarbonBudgetRead,
    CarbonBudgetUpdate,
)
from app.services.database import (
    application_has_history,
    commit_or_conflict,
    get_application_or_404,
    get_budget_or_404,
)

router = APIRouter(tags=["applications"])
Database = Annotated[Session, Depends(get_db)]


@router.post(
    "/applications",
    response_model=ApplicationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_application(payload: ApplicationCreate, db: Database) -> Application:
    application = Application(**payload.model_dump())
    db.add(application)
    commit_or_conflict(db, "An application with that name already exists")
    db.refresh(application)
    return application


@router.get("/applications", response_model=list[ApplicationRead])
def list_applications(
    db: Database,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[Application]:
    return list(
        db.scalars(
            select(Application).order_by(Application.id).offset(skip).limit(limit)
        )
    )


@router.get("/applications/{application_id}", response_model=ApplicationRead)
def read_application(application_id: DatabasePathId, db: Database) -> Application:
    return get_application_or_404(db, application_id)


@router.put("/applications/{application_id}", response_model=ApplicationRead)
def update_application(
    application_id: DatabasePathId,
    payload: ApplicationUpdate,
    db: Database,
) -> Application:
    application = get_application_or_404(db, application_id)
    for key, value in payload.model_dump().items():
        setattr(application, key, value)
    commit_or_conflict(db, "An application with that name already exists")
    db.refresh(application)
    return application


@router.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: DatabasePathId, db: Database) -> Response:
    application = get_application_or_404(db, application_id)
    if application_has_history(db, application_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application cannot be deleted while policies, budgets, or historical records exist",
        )
    db.delete(application)
    commit_or_conflict(
        db, "Application cannot be deleted while dependent records exist"
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/applications/{application_id}/budgets",
    response_model=CarbonBudgetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_budget(
    application_id: DatabasePathId,
    payload: CarbonBudgetCreate,
    db: Database,
) -> CarbonBudget:
    get_application_or_404(db, application_id)
    budget = CarbonBudget(application_id=application_id, **payload.model_dump())
    db.add(budget)
    commit_or_conflict(db, "Carbon budget violates a database constraint")
    db.refresh(budget)
    return budget


@router.get(
    "/applications/{application_id}/budgets",
    response_model=list[CarbonBudgetRead],
)
def list_application_budgets(
    application_id: DatabasePathId,
    db: Database,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[CarbonBudget]:
    get_application_or_404(db, application_id)
    return list(
        db.scalars(
            select(CarbonBudget)
            .where(CarbonBudget.application_id == application_id)
            .order_by(CarbonBudget.id)
            .offset(skip)
            .limit(limit)
        )
    )


@router.get("/budgets/{budget_id}", response_model=CarbonBudgetRead)
def read_budget(budget_id: DatabasePathId, db: Database) -> CarbonBudget:
    return get_budget_or_404(db, budget_id)


@router.put("/budgets/{budget_id}", response_model=CarbonBudgetRead)
def update_budget(
    budget_id: DatabasePathId,
    payload: CarbonBudgetUpdate,
    db: Database,
) -> CarbonBudget:
    budget = get_budget_or_404(db, budget_id)
    for key, value in payload.model_dump().items():
        setattr(budget, key, value)
    commit_or_conflict(db, "Carbon budget violates a database constraint")
    db.refresh(budget)
    return budget


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(budget_id: DatabasePathId, db: Database) -> Response:
    budget = get_budget_or_404(db, budget_id)
    db.delete(budget)
    commit_or_conflict(db, "Carbon budget could not be deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
