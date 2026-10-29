"""Reusable FastAPI path constraints for SQL integer primary keys."""

from typing import Annotated

from fastapi import Path

from app.schemas.limits import MAX_DATABASE_ID

DatabasePathId = Annotated[int, Path(gt=0, le=MAX_DATABASE_ID)]
