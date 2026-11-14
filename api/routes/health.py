"""Health check and test endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from bench_finder.models.unified_models import ProcessedBench
from bench_finder.services.database import BenchDatabase

from ..api_models import HealthResponse
from ..dependencies import get_db


router = APIRouter()


@router.get(
    "/health",
    summary="Health Check",
    description="Simple health check endpoint to verify server status",
    response_model=HealthResponse,
    tags=["config"],
)
async def health_check(
    db: BenchDatabase = Depends(get_db),
) -> HealthResponse:
    """Check if the server is running and database is accessible."""
    try:
        with db.get_session() as session:
            session.query(ProcessedBench).limit(1).first()

        return HealthResponse(
            status="healthy",
            database="connected",
            mapillary="unified",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {e!s}",
        ) from e


# Test endpoints for stacktrace logging (remove in production)
@router.get(
    "/api/test-error",
    summary="Test 500 Error Endpoint",
    description="Test endpoint that triggers a 500 error to demonstrate stacktrace logging",
    tags=["config"],
)
async def test_error() -> None:
    """Test endpoint that raises an exception to demonstrate stacktrace logging."""
    raise ValueError(
        "This is a test error to demonstrate stacktrace logging in FastAPI logs"
    )


@router.get(
    "/api/test-400-error",
    summary="Test 400 Error Endpoint",
    description="Test endpoint that triggers a 400 error to demonstrate stacktrace logging",
    tags=["config"],
)
async def test_400_error() -> None:
    """Test endpoint that raises a ValueError to demonstrate 400 error stacktrace logging."""
    raise ValueError(
        "This is a test 400 error to demonstrate stacktrace logging in FastAPI logs"
    )


@router.get(
    "/api/test-validation-error",
    summary="Test Validation Error Endpoint",
    description="Test endpoint that triggers a validation error to demonstrate stacktrace logging",
    tags=["config"],
)
async def test_validation_error() -> dict[str, str]:
    """Test endpoint that demonstrates validation error stacktrace logging."""
    return {"message": "This endpoint requires a query parameter"}
