"""HTTP endpoints for the CarbonGuard API."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Report whether the API process is responding."""
    return {
        "status": "healthy",
        "application": "CarbonGuard API",
        "version": "0.1.0",
    }


@router.get("/status", tags=["project"])
def implementation_status() -> dict[str, str]:
    """Describe the scope currently implemented by this service."""
    return {
        "project": "CarbonGuard",
        "phase": "Phase 8",
        "status": "release_validation_complete",
        "next_phase": "none",
    }
