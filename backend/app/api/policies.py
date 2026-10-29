"""Carbon-budget policy management and evaluation endpoints."""

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.parameters import DatabasePathId
from app.models import BudgetPolicy
from app.schemas.limits import MAX_DATABASE_ID
from app.schemas.policies import (
    BudgetEvaluationRead,
    BudgetPolicyCreate,
    BudgetPolicyRead,
    BudgetPolicyUpdate,
)
from app.services.database import (
    commit_or_conflict,
    get_application_or_404,
)
from app.services.policies import evaluate_policies, evaluate_policy

router = APIRouter(tags=["budget policies"])
Database = Annotated[Session, Depends(get_db)]
MAX_POLICY_PAGE_SIZE = 100


def _get_policy_or_404(db: Session, policy_id: int) -> BudgetPolicy:
    policy = db.get(BudgetPolicy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Budget policy not found")
    return policy


@router.post(
    "/budget-policies",
    response_model=BudgetPolicyRead,
    status_code=status.HTTP_201_CREATED,
)
def create_budget_policy(payload: BudgetPolicyCreate, db: Database) -> BudgetPolicy:
    get_application_or_404(db, payload.application_id)
    policy = BudgetPolicy(**payload.model_dump())
    db.add(policy)
    commit_or_conflict(
        db,
        "A budget policy already exists for this application or violates a database constraint",
    )
    db.refresh(policy)
    return policy


@router.get("/budget-policies", response_model=list[BudgetPolicyRead])
def list_budget_policies(
    db: Database,
    application_id: int | None = Query(
        default=None, gt=0, le=MAX_DATABASE_ID
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=MAX_POLICY_PAGE_SIZE),
) -> list[BudgetPolicy]:
    statement = select(BudgetPolicy).order_by(BudgetPolicy.id)
    if application_id is not None:
        statement = statement.where(BudgetPolicy.application_id == application_id)
    return list(db.scalars(statement.offset(skip).limit(limit)))


@router.get("/budget-policies/{policy_id}", response_model=BudgetPolicyRead)
def read_budget_policy(policy_id: DatabasePathId, db: Database) -> BudgetPolicy:
    return _get_policy_or_404(db, policy_id)


@router.patch("/budget-policies/{policy_id}", response_model=BudgetPolicyRead)
def update_budget_policy(
    policy_id: DatabasePathId,
    payload: BudgetPolicyUpdate,
    db: Database,
) -> BudgetPolicy:
    policy = _get_policy_or_404(db, policy_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="At least one field must be updated")
    if any(value is None for value in updates.values()):
        raise HTTPException(
            status_code=422,
            detail="Budget policy fields cannot be set to null",
        )
    warning = updates.get(
        "warning_threshold_percent", policy.warning_threshold_percent
    )
    critical = updates.get(
        "critical_threshold_percent", policy.critical_threshold_percent
    )
    if warning >= critical:
        raise HTTPException(
            status_code=422,
            detail="warning_threshold_percent must be lower than critical_threshold_percent",
        )
    for key, value in updates.items():
        setattr(policy, key, value)
    commit_or_conflict(db, "Budget policy violates a database constraint")
    db.refresh(policy)
    return policy


@router.delete(
    "/budget-policies/{policy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_budget_policy(policy_id: DatabasePathId, db: Database) -> Response:
    policy = _get_policy_or_404(db, policy_id)
    db.delete(policy)
    commit_or_conflict(db, "Budget policy could not be deleted")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/budget-policies/evaluate",
    response_model=list[BudgetEvaluationRead],
)
def evaluate_enabled_policies(
    db: Database,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=MAX_POLICY_PAGE_SIZE),
) -> list[BudgetEvaluationRead]:
    reference_time = datetime.now(timezone.utc)
    policies = db.scalars(
        select(BudgetPolicy)
        .where(BudgetPolicy.enabled.is_(True))
        .order_by(BudgetPolicy.id)
        .offset(skip)
        .limit(limit)
    )
    return evaluate_policies(db, list(policies), reference_time)


@router.post(
    "/budget-policies/{policy_id}/evaluate",
    response_model=BudgetEvaluationRead,
)
def evaluate_budget_policy(
    policy_id: DatabasePathId,
    db: Database,
) -> BudgetEvaluationRead:
    return evaluate_policy(
        db,
        _get_policy_or_404(db, policy_id),
        datetime.now(timezone.utc),
    )


@router.get(
    "/applications/{application_id}/budget-status",
    response_model=BudgetEvaluationRead,
)
def read_application_budget_status(
    application_id: DatabasePathId,
    db: Database,
) -> BudgetEvaluationRead:
    get_application_or_404(db, application_id)
    policy = db.scalar(
        select(BudgetPolicy).where(
            BudgetPolicy.application_id == application_id,
            BudgetPolicy.enabled.is_(True),
        )
    )
    if policy is None:
        raise HTTPException(
            status_code=404,
            detail="No enabled budget policy is configured for this application",
        )
    return evaluate_policy(db, policy, datetime.now(timezone.utc))
