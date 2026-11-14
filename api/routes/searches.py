"""Search and configuration endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from bench_finder.models.enums import DataSource, DetectionSource, SearchStatus
from bench_finder.models.unified_models import BenchCandidate, ProcessedBench, Search
from bench_finder.services.database import BenchDatabase

from ..api_models import (
    ApiInfoResponse,
    ConfigResponse,
    SearchListResponse,
    SearchSummary,
)
from ..dependencies import (
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_START_LAT,
    DEFAULT_START_LNG,
    PAGE_SIZE,
    get_db,
)
from ..helpers import EnhancedErrorResponse


router = APIRouter()


@router.get(
    "/api/searches",
    summary="List Available Searches",
    description="Get list of completed search operations with bench counts",
    response_model=SearchListResponse,
    responses={
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
    },
    tags=["search"],
)
async def get_searches(
    db: BenchDatabase = Depends(get_db),
) -> SearchListResponse:
    """
    Get a list of completed search operations with metadata.

    Only completed searches with associated bench data are returned.
    """
    try:
        with db.get_session() as session:
            from sqlalchemy import func

            searches_query = (
                session.query(
                    Search, func.count(ProcessedBench.id).label("bench_count")
                )
                .outerjoin(BenchCandidate, Search.id == BenchCandidate.search_id)
                .outerjoin(
                    ProcessedBench,
                    BenchCandidate.id == ProcessedBench.bench_candidate_id,
                )
                .filter(Search.status == SearchStatus.COMPLETED)
                .group_by(Search.id)
                .order_by(Search.created_at.desc())
                .all()
            )

            searches = []
            for search, bench_count in searches_query:
                search_summary = SearchSummary(
                    id=search.id,
                    query=search.query,
                    start_lat=search.start_lat,
                    start_lng=search.start_lng,
                    search_radius=search.search_radius,
                    bench_count=bench_count,
                    created_at=search.created_at,
                )
                searches.append(search_summary)

            return SearchListResponse(searches=searches)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve searches: {e!s}",
        ) from e


@router.get(
    "/api/config",
    summary="Get Application Configuration",
    description="Get default configuration values for the frontend application",
    response_model=ConfigResponse,
    tags=["config"],
)
async def get_config() -> ConfigResponse:
    """Get application configuration for frontend initialization."""
    return ConfigResponse(
        default_start_lat=DEFAULT_START_LAT,
        default_start_lng=DEFAULT_START_LNG,
        default_min_confidence=DEFAULT_MIN_CONFIDENCE,
        page_size=PAGE_SIZE,
    )


@router.get(
    "/api/info",
    summary="Get API Information",
    description="Get comprehensive API information including capabilities and limits",
    response_model=ApiInfoResponse,
    tags=["config"],
)
async def get_api_info() -> ApiInfoResponse:
    """Get detailed API information including capabilities and usage limits."""
    return ApiInfoResponse(
        name="Bench Finder API",
        version="2.0.0",
        description="A comprehensive API for discovering and analyzing public benches using computer vision",
        supported_sources=[DataSource.OSM, DataSource.MAPILLARY],
        supported_detection_models=[
            DetectionSource.ROBOFLOW,
            DetectionSource.ULTRALYTICS,
            DetectionSource.MAPILLARY,
        ],
        features=[
            "spatial_search",
            "confidence_filtering",
            "multi_source_data",
            "image_analysis",
            "detection_visualization",
            "statistics_analytics",
            "bbox_queries",
            "random_discovery",
        ],
        limits={
            "max_page_size": 50,
            "max_bbox_results": 500,
            "max_search_radius": 10000,
        },
        endpoints={
            "benches": "/api/benches",
            "random_bench": "/api/benches/random",
            "bbox_search": "/api/benches/bbox",
            "searches": "/api/searches",
            "config": "/api/config",
            "health": "/health",
            "docs": "/docs",
            "redoc": "/redoc",
        },
    )
