"""Energy and carbon estimation endpoints."""

from fastapi import APIRouter, HTTPException

from app.schemas.estimates import EstimateRequest, EstimateResponse
from app.services.estimation import estimate_energy_and_emissions

router = APIRouter(tags=["estimates"])


@router.post("/estimates", response_model=EstimateResponse)
def create_estimate(request: EstimateRequest) -> EstimateResponse:
    """Estimate energy and emissions without storing or modifying user data."""
    try:
        return estimate_energy_and_emissions(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
