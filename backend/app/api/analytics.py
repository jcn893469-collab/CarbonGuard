"""Read-only analytics and CSV report endpoints."""

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.parameters import DatabasePathId
from app.schemas.limits import MAX_DATABASE_ID
from app.schemas.analytics import (
    AnalyticsApplicationsRead,
    AnalyticsOverviewRead,
    AnalyticsPoliciesRead,
    AnalyticsTrendRead,
    AnalyticsWorkloadsRead,
    ApplicationAnalyticsDetailRead,
)
from app.services.analytics import (
    MAX_POLICY_PAGE_SIZE,
    export_csv,
    get_application_analytics,
    get_application_comparison,
    get_overview,
    get_policy_snapshots,
    get_trend,
    get_workload_analytics,
    resolve_time_range,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])
Database = Annotated[Session, Depends(get_db)]
Interval = Literal["daily", "weekly", "monthly"]


@router.get("/overview", response_model=AnalyticsOverviewRead)
def read_analytics_overview(db: Database) -> AnalyticsOverviewRead:
    return get_overview(db)


@router.get("/trends", response_model=AnalyticsTrendRead)
def read_analytics_trends(
    db: Database,
    start: datetime | None = None,
    end: datetime | None = None,
    interval: Interval = Query(default="daily"),
    application_id: int | None = Query(
        default=None, gt=0, le=MAX_DATABASE_ID
    ),
) -> AnalyticsTrendRead:
    start_utc, end_utc = resolve_time_range(start, end)
    return get_trend(
        db,
        start=start_utc,
        end=end_utc,
        interval=interval,
        application_id=application_id,
    )


@router.get("/workloads", response_model=AnalyticsWorkloadsRead)
def read_workload_analytics(
    db: Database,
    start: datetime | None = None,
    end: datetime | None = None,
    application_id: int | None = Query(
        default=None, gt=0, le=MAX_DATABASE_ID
    ),
) -> AnalyticsWorkloadsRead:
    return get_workload_analytics(
        db,
        start=start,
        end=end,
        application_id=application_id,
    )


@router.get("/applications", response_model=AnalyticsApplicationsRead)
def read_application_analytics(
    db: Database,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> AnalyticsApplicationsRead:
    return get_application_comparison(db, skip=skip, limit=limit)


@router.get("/policies", response_model=AnalyticsPoliciesRead)
def read_policy_analytics(
    db: Database,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=MAX_POLICY_PAGE_SIZE, ge=1, le=MAX_POLICY_PAGE_SIZE),
) -> AnalyticsPoliciesRead:
    return get_policy_snapshots(
        db,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationAnalyticsDetailRead,
)
def read_application_detail_analytics(
    application_id: DatabasePathId,
    db: Database,
    start: datetime | None = None,
    end: datetime | None = None,
    interval: Interval = Query(default="daily"),
) -> ApplicationAnalyticsDetailRead:
    return get_application_analytics(
        db,
        application_id=application_id,
        start=start,
        end=end,
        interval=interval,
    )


@router.get("/export.csv", response_class=Response)
def download_analytics_csv(
    db: Database,
    start: datetime,
    end: datetime,
    application_id: int | None = Query(
        default=None, gt=0, le=MAX_DATABASE_ID
    ),
) -> Response:
    content = export_csv(
        db,
        start=start,
        end=end,
        application_id=application_id,
    )
    filename = "carbonguard-report.csv"
    if application_id is not None:
        filename = f"carbonguard-application-{application_id}-report.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
