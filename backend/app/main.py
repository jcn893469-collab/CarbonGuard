"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import (
    analytics,
    applications,
    estimates,
    policies,
    records,
    routes,
    simulation,
)
from app.core.config import get_cors_origins
from app.core.middleware import SecurityHeadersAndBodyLimitMiddleware

app = FastAPI(
    title="CarbonGuard API",
    description="CarbonGuard API for workload estimates, policy evaluation, analytics, and reports.",
    version="0.1.0",
)

app.add_middleware(SecurityHeadersAndBodyLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_response(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return useful validation details without reflecting submitted values."""
    details = [
        {
            "loc": list(error["loc"]),
            "msg": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"detail": details})


@app.get("/", tags=["project"])
def root() -> dict[str, str]:
    """Return a concise project status message."""
    return {
        "message": "CarbonGuard API is running.",
        "status": "service_ready",
    }


app.include_router(analytics.router, prefix="/api")
app.include_router(routes.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(records.router, prefix="/api")
app.include_router(estimates.router, prefix="/api")
app.include_router(simulation.router, prefix="/api")
app.include_router(policies.router, prefix="/api")
