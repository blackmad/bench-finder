#!/usr/bin/env python3
"""
FastAPI server for bench finder application with comprehensive OpenAPI documentation.
Migrated from Flask with improved type safety and automatic API documentation.
"""

import logging
import math
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime

# Any import removed - not used
import uvicorn
from fastapi import Body, FastAPI, HTTPException, Path, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from bench_finder.config import DATABASE_PATH, IMAGES_DIR
from bench_finder.models.enums import (
    BenchReportType,
    DataSource,
    DetectionSource,
    LocationMethod,
    SearchStatus,
)
from bench_finder.models.unified_models import (
    BenchCandidate,
    Detection,
    DetectionItem,
    Image,
    ProcessedBench,
    Search,
)
from bench_finder.services.database import BenchDatabase

from .api_models import (
    ApiDetectionItem,
    ApiInfoResponse,
    BenchDetectionData,
    BenchListResponse,
    BenchMode,
    ConfigResponse,
    ErrorResponse,
    HealthResponse,
    ImageListResponse,
    ImageResponse,
    ImageWithDetectionData,
    MissingBenchReportResponse,
    PaginationInfo,
    ReportResponse,
    SearchListResponse,
    SearchSummary,
    SegmentationData,
    WebBenchData,
)


logger = logging.getLogger(__name__)


# Configuration constants
DEFAULT_START_LAT = 52.3613577  # Amsterdam, Netherlands (matches actual data)
DEFAULT_START_LNG = 4.8666322
DEFAULT_MIN_CONFIDENCE = 0
PAGE_SIZE = 20


def sort_images_by_best(
    image_filenames: list[str], image_ids: list[int], best_image_id: int | None
) -> tuple[list[str], list[int]]:
    """
    Sort image arrays so the best image is first.

    Args:
        image_filenames: List of image filenames
        image_ids: List of image IDs (must match filenames in order)
        best_image_id: ID of the best image, or None

    Returns:
        Tuple of (sorted_filenames, sorted_ids) with best image first
    """
    if not best_image_id or not image_ids:
        return image_filenames, image_ids

    # Find the index of the best image
    try:
        best_index = image_ids.index(best_image_id)
    except ValueError:
        # best_image_id not in the list, return as-is
        return image_filenames, image_ids

    # If it's already first, no need to sort
    if best_index == 0:
        return image_filenames, image_ids

    # Reorder so best image is first
    sorted_filenames = [image_filenames[best_index]] + [
        f for i, f in enumerate(image_filenames) if i != best_index
    ]
    sorted_ids = [image_ids[best_index]] + [
        img_id for i, img_id in enumerate(image_ids) if i != best_index
    ]

    return sorted_filenames, sorted_ids


class EnhancedErrorResponse(BaseModel):
    """Enhanced error response with detailed debugging information."""

    error: str = Field(..., description="Human-readable error message")

    error_code: str | None = Field(
        default=None,
        description="Machine-readable error code for programmatic handling",
    )

    detail: str | None = Field(
        default=None, description="Additional error details and context"
    )

    suggestions: list[str] | None = Field(
        default=None, description="Suggested actions to resolve the error"
    )

    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="When the error occurred"
    )


# Enhanced Pydantic models for FastAPI with OpenAPI documentation
class BenchQueryParams(BaseModel):
    """Query parameters for bench listing endpoints."""

    page: int = Field(0, ge=0, description="Page number (0-based)")
    page_size: int = Field(
        PAGE_SIZE, ge=1, le=50, description="Items per page (max 50)"
    )
    min_confidence: float = Field(
        DEFAULT_MIN_CONFIDENCE,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence score",
    )
    start_lat: float = Field(
        DEFAULT_START_LAT,
        ge=-90.0,
        le=90.0,
        description="Starting latitude for distance calculations",
    )
    start_lng: float = Field(
        DEFAULT_START_LNG,
        ge=-180.0,
        le=180.0,
        description="Starting longitude for distance calculations",
    )
    sort_by: str = Field(
        "distance",
        pattern="^(distance|confidence|images|recent)$",
        description="Sort criteria",
    )


class BboxQueryParams(BaseModel):
    """Query parameters for bounding box bench queries."""

    north: float = Field(
        ..., ge=-90.0, le=90.0, description="Northern latitude boundary"
    )
    south: float = Field(
        ..., ge=-90.0, le=90.0, description="Southern latitude boundary"
    )
    east: float = Field(
        ..., ge=-180.0, le=180.0, description="Eastern longitude boundary"
    )
    west: float = Field(
        ..., ge=-180.0, le=180.0, description="Western longitude boundary"
    )
    min_confidence: float = Field(
        DEFAULT_MIN_CONFIDENCE,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence score",
    )
    source: DataSource | None = Field(None, description="Filter by data source")
    sort_by: str = Field(
        "distance",
        pattern="^(distance|confidence|images|recent)$",
        description="Sort criteria",
    )
    limit: int = Field(200, ge=1, le=500, description="Maximum number of results")


# MapillarySearchRequest removed - using unified search approach


class BboxBenchResponse(BaseModel):
    """Response model for bounding box bench queries."""

    benches: list[WebBenchData] = Field(
        ..., description="List of benches within the bounding box"
    )
    total_count: int = Field(..., ge=0, description="Total number of benches returned")
    bbox: dict[str, float] = Field(
        ..., description="The requested bounding box coordinates"
    )


# Application lifecycle management
@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Manage application lifecycle - startup and shutdown events."""
    # Startup

    print("🚀 Starting Bench Finder FastAPI server...")
    print(f"📁 Database: {DATABASE_PATH}")
    print(f"🖼️  Images directory: {IMAGES_DIR}")

    # Configure logging for better error visibility
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),  # Console output
        ],
    )

    # Set uvicorn loggers to show more detail
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    # Mapillary service initialization removed - using unified approach

    # Ensure required directories exist
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    print("✅ Server initialization complete")

    yield

    # Shutdown
    print("🛑 Shutting down Bench Finder server...")


# Create FastAPI application
app = FastAPI(
    title="Bench Finder API",
    description="""
    A comprehensive API for discovering and analyzing public benches using computer vision.

    This API provides access to bench detection data from multiple sources:
    - **OpenStreetMap (OSM)**: Crowdsourced geographic data
    - **Mapillary**: Street-level imagery with AI-powered object detection
    - **Custom Detection Models**: Roboflow and Ultralytics YOLO models

    ## Features

    - 🔍 **Search & Discovery**: Find benches by location, confidence, and source
    - 📊 **Advanced Analytics**: Get detailed statistics and detection metadata
    - 🗺️ **Spatial Queries**: Bounding box searches for map applications
    - 🖼️ **Image Analysis**: Access detection visualizations and segmentation data
    - 📱 **Web Interface**: Full-featured frontend with infinite scroll and filtering

    ## Data Sources

    - **OSM**: Traditional geographic data with bench locations
    - **Mapillary**: AI-detected benches from street imagery with confidence scores
    - **Multi-Model Detection**: Combines Roboflow and Ultralytics for higher accuracy

    ## Authentication

    Most endpoints are public, but Mapillary integration requires proper API token configuration.
    """,
    version="2.0.0",
    contact={
        "name": "Bench Finder Project",
        "url": "https://github.com/your-username/bench_finder",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {
            "name": "benches",
            "description": "Core bench discovery and listing operations",
        },
        {
            "name": "search",
            "description": "Search management and historical queries",
        },
        {
            "name": "images",
            "description": "Image serving and detection visualization",
        },
        {
            "name": "mapillary",
            "description": "Mapillary-specific operations and street imagery",
        },
        {
            "name": "reporting",
            "description": "User reporting for bad detections and missing benches",
        },
        {
            "name": "statistics",
            "description": "Analytics and performance metrics",
        },
        {
            "name": "config",
            "description": "Application configuration and metadata",
        },
    ],
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add custom exception handler for detailed error logging
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler that logs full stacktraces for debugging."""
    import logging
    import traceback

    # Set up logging if not already configured
    logger = logging.getLogger(__name__)

    # Log the full stacktrace
    logger.error(f"🚨 Unhandled exception in {request.method} {request.url}:")
    logger.error(f"Exception type: {type(exc).__name__}")
    logger.error(f"Exception message: {exc!s}")
    logger.error("Full stacktrace:")
    logger.error(traceback.format_exc())

    # Also print to console for immediate visibility
    print(f"🚨 Unhandled exception in {request.method} {request.url}:")
    print(f"Exception type: {type(exc).__name__}")
    print(f"Exception message: {exc!s}")
    print("Full stacktrace:")
    traceback.print_exc()

    # Return a generic error response
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if str(exc) else "An unexpected error occurred",
            "type": type(exc).__name__,
        },
    )


# Mount static files for images
if os.path.exists(IMAGES_DIR):
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


# Global exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions with proper HTTP status and stacktrace logging."""
    import logging
    import traceback

    logger = logging.getLogger(__name__)

    # Log the full stacktrace for 400 errors too
    logger.warning(f"🚨 ValueError in {request.method} {request.url}:")
    logger.warning(f"Exception type: {type(exc).__name__}")
    logger.warning(f"Exception message: {exc!s}")
    logger.warning("Full stacktrace:")
    logger.warning(traceback.format_exc())

    # Also print to console for immediate visibility
    print(f"🚨 ValueError in {request.method} {request.url}:")
    print(f"Exception type: {type(exc).__name__}")
    print(f"Exception message: {exc!s}")
    print("Full stacktrace:")
    traceback.print_exc()

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(error="Invalid input", detail=str(exc)).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException with stacktrace logging for 400-level errors."""
    import logging
    import traceback

    logger = logging.getLogger(__name__)

    # Only log stacktraces for 400-level errors (not 404s, etc.)
    if 400 <= exc.status_code < 500:
        logger.warning(
            f"🚨 HTTPException {exc.status_code} in {request.method} {request.url}:"
        )
        logger.warning(f"Exception type: {type(exc).__name__}")
        logger.warning(f"Exception message: {exc.detail!s}")
        logger.warning("Full stacktrace:")
        logger.warning(traceback.format_exc())

        # Also print to console for immediate visibility
        print(f"🚨 HTTPException {exc.status_code} in {request.method} {request.url}:")
        print(f"Exception type: {type(exc).__name__}")
        print(f"Exception message: {exc.detail!s}")
        print("Full stacktrace:")
        traceback.print_exc()

    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error="HTTP Error", detail=str(exc.detail)).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors with stacktrace logging."""
    import logging
    import traceback

    logger = logging.getLogger(__name__)

    # Log the full stacktrace for validation errors
    logger.warning(f"🚨 ValidationError in {request.method} {request.url}:")
    logger.warning(f"Exception type: {type(exc).__name__}")
    logger.warning(f"Exception message: {exc!s}")
    logger.warning("Full stacktrace:")
    logger.warning(traceback.format_exc())

    # Also print to console for immediate visibility
    print(f"🚨 ValidationError in {request.method} {request.url}:")
    print(f"Exception type: {type(exc).__name__}")
    print(f"Exception message: {exc!s}")
    print("Full stacktrace:")
    traceback.print_exc()

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="Validation Error", detail=f"Request validation failed: {exc!s}"
        ).model_dump(),
    )


# Utility functions
def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great circle distance between two points using Haversine formula.
    Returns distance in meters.
    """
    # Convert decimal degrees to radians
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])

    # Haversine formula
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    # Earth's radius in meters
    r = 6371000
    return c * r


# Health check endpoint
@app.get(
    "/health",
    summary="Health Check",
    description="Simple health check endpoint to verify server status",
    response_model=dict[str, str],
    tags=["config"],
)
async def health_check():
    """Check if the server is running and database is accessible."""
    try:
        # Test database connection using SQLAlchemy ORM
        db = BenchDatabase()
        with db.get_session() as session:
            # Simple query to test database connectivity
            session.query(ProcessedBench).limit(1).first()

        return HealthResponse(
            status="healthy",
            database="connected",
            mapillary="unified",  # Using unified approach
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {e!s}",
        ) from e


# Helper function to get detection items for a bench
def get_detection_items_for_bench(
    session, bench_candidate_id: int
) -> list[ApiDetectionItem]:
    """Get all detection items for a specific bench candidate using SQLAlchemy ORM."""

    # Query detection items with proper joins using ORM
    # Start from ProcessedBench, join to BenchCandidate, Image, Detection, DetectionItem
    detection_items_query = (
        session.query(DetectionItem)
        .join(Detection, DetectionItem.detection_id == Detection.id)
        .join(Image, Detection.image_id == Image.id)
        .join(BenchCandidate, Image.bench_candidate_id == BenchCandidate.id)
        .filter(BenchCandidate.id == bench_candidate_id)
        .order_by(DetectionItem.confidence.desc())
        .all()
    )

    detection_items = []
    for item in detection_items_query:
        # Ensure bbox and polygon are proper model instances, not dicts
        bbox = None
        if item.bbox:
            if isinstance(item.bbox, dict):
                # Convert dict to BoundingBox model
                from bench_finder.models.unified_models import BoundingBox

                bbox = BoundingBox(**item.bbox)
            else:
                bbox = item.bbox  # Already a BoundingBox instance

        polygon = None
        if item.polygon:
            if isinstance(item.polygon, dict):
                # Convert dict to Polygon model
                from bench_finder.models.unified_models import Polygon

                polygon = Polygon(**item.polygon)
            else:
                polygon = item.polygon  # Already a Polygon instance

        # Create a new ApiDetectionItem with proper model instances
        detection_item = ApiDetectionItem(
            detection_id=item.detection_id,
            confidence=item.confidence,
            bbox=bbox,
            class_name=item.class_name,
            polygon=polygon,
        )
        detection_items.append(detection_item)

    return detection_items


# Unified helper function for getting a single bench by ID
def _safe_convert_source(source) -> DataSource:
    """Safely convert a source value to DataSource enum."""
    if isinstance(source, str):
        try:
            return DataSource(source.upper())
        except ValueError:
            return DataSource.OSM
    elif source is None:
        return DataSource.OSM
    else:
        return source


def get_bench_by_id(
    bench_id: int,
    include_detection_data: bool = False,
) -> WebBenchData:
    """
    Get a specific bench by ID with all its data using SQLAlchemy ORM.

    Uses ProcessedBench -> BenchCandidate -> Image -> Detection -> DetectionItem

    Args:
        bench_id: The ID of the ProcessedBench to retrieve
        include_detection_data: Whether to include detection items in response

    Returns:
        WebBenchData object with bench information

    Raises:
        HTTPException: If bench not found or other error occurs
    """
    try:
        db = BenchDatabase()
        with db.get_session() as session:
            from sqlalchemy.orm import joinedload

            # Start from ProcessedBench, join to BenchCandidate and related data
            processed_bench = (
                session.query(ProcessedBench)
                .options(
                    joinedload(ProcessedBench.bench_candidate),
                    joinedload(ProcessedBench.best_detection).joinedload(
                        Detection.detection_items
                    ),
                    joinedload(ProcessedBench.best_image),
                )
                .filter(ProcessedBench.id == bench_id)
                .first()
            )

            if not processed_bench:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"ProcessedBench with ID {bench_id} not found",
                )

            bench_candidate = processed_bench.bench_candidate

            # Get successful images for this bench candidate using ORM
            successful_images = (
                session.query(Image)
                .filter(
                    Image.bench_candidate_id == bench_candidate.id,
                    Image.capture_success,
                )
                .all()
            )

            image_count = len(successful_images)
            # Build matched pairs - only include images with filenames
            image_filenames = []
            image_ids = []
            for img in successful_images:
                if img.filename:
                    image_filenames.append(img.filename)
                    image_ids.append(img.id)

            # Sort images so best image is first
            best_image_id = processed_bench.best_image_id
            image_filenames, image_ids = sort_images_by_best(
                image_filenames, image_ids, best_image_id
            )

            # Initialize confidence scores - don't coalesce, just use best_detection if available
            best_confidence = 0.0
            roboflow_confidence = 0.0
            ultralytics_confidence = 0.0
            mapillary_confidence = 0.0
            detection_type = DetectionSource.NONE
            has_segmentation = False
            bench_found = processed_bench.detection_status == "detected"

            # Get best detection if available
            best_detection = processed_bench.best_detection
            if best_detection:
                best_confidence = best_detection.max_confidence
                detection_type = best_detection.source

                # Check for segmentation by looking at DetectionItems polygon field
                if best_detection.detection_items:
                    has_segmentation = any(
                        item.polygon is not None
                        for item in best_detection.detection_items
                    )

                # Set source-specific confidence - just use the best_detection's max_confidence
                # Don't coalesce across detections
                if best_detection.source == DetectionSource.ROBOFLOW:
                    roboflow_confidence = best_detection.max_confidence
                elif best_detection.source == DetectionSource.ULTRALYTICS:
                    ultralytics_confidence = best_detection.max_confidence
                elif best_detection.source == DetectionSource.MAPILLARY:
                    mapillary_confidence = best_detection.max_confidence

            # Get detection items if requested
            detection_items = None
            if include_detection_data:
                detection_items = get_detection_items_for_bench(
                    session, bench_candidate.id
                )

            # Ensure source is properly converted to enum
            bench_source = _safe_convert_source(bench_candidate.source)

            return WebBenchData(
                id=processed_bench.id,
                provider_id=bench_candidate.provider_id,
                lat=bench_candidate.lat,
                lng=bench_candidate.lng,
                tags=bench_candidate.tags or {},
                source=bench_source,
                external_id=bench_candidate.external_id,
                bench_found=bench_found,
                best_confidence=best_confidence,
                roboflow_confidence=roboflow_confidence,
                ultralytics_confidence=ultralytics_confidence,
                mapillary_confidence=mapillary_confidence,
                detection_type=detection_type,
                has_segmentation=has_segmentation,
                image_count=image_count,
                image_filenames=image_filenames,
                image_ids=image_ids,
                best_image_id=processed_bench.best_image_id,
                best_detection_id=processed_bench.best_detection_id,
                distance_meters=0,  # Not applicable for single bench
                distance_km=0.0,  # Not applicable for single bench
                detection_items=detection_items,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get bench {bench_id}: {e!s}",
        ) from e


# Utility function for bench data processing using SQLAlchemy ORM
def get_high_confidence_benches_filtered(
    page: int = 0,
    page_size: int = PAGE_SIZE,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    start_lat: float = DEFAULT_START_LAT,
    start_lng: float = DEFAULT_START_LNG,
    sort_by: str = "distance",
    mode: BenchMode = BenchMode.BENCHES,
    include_detection_data: bool = False,
    source: DataSource | None = None,
) -> BenchListResponse:
    """
    Get benches with configurable detection modes from all sources using SQLAlchemy ORM.
    Optimized to minimize joins and GROUP BYs using subqueries.
    """
    try:
        db = BenchDatabase()
        with db.get_session() as session:
            from sqlalchemy import case, func
            from sqlalchemy.orm import aliased
            from sqlalchemy.types import String as SAString

            # Create subquery for image aggregation - eliminates GROUP BY from main query
            image_subquery = (
                session.query(
                    Image.bench_candidate_id,
                    func.count(func.distinct(Image.id)).label("image_count"),
                    func.group_concat(func.distinct(Image.filename)).label(
                        "image_filenames"
                    ),
                    func.group_concat(
                        func.distinct(func.cast(Image.id, SAString))
                    ).label("image_ids"),
                )
                .filter(Image.capture_success == 1)
                .group_by(Image.bench_candidate_id)
                .subquery()
            )
            img_subq = aliased(image_subquery)

            # Create subquery for segmentation check - eliminates N+1 query
            # Check if polygon JSON column is not null
            segmentation_subquery = (
                session.query(
                    DetectionItem.detection_id,
                    func.max(
                        case(
                            (DetectionItem.__table__.c.polygon.isnot(None), 1), else_=0
                        )
                    ).label("has_segmentation"),
                )
                .group_by(DetectionItem.detection_id)
                .subquery()
            )
            seg_subq = aliased(segmentation_subquery)

            # Build main query with minimal joins - no GROUP BY needed!
            query = (
                session.query(
                    ProcessedBench.id.label("processed_bench_id"),
                    BenchCandidate.id.label("bench_candidate_id"),
                    BenchCandidate.provider_id,
                    BenchCandidate.lat,
                    BenchCandidate.lng,
                    BenchCandidate.tags,
                    BenchCandidate.source,
                    BenchCandidate.external_id,
                    func.coalesce(Detection.max_confidence, 0.0).label(
                        "best_confidence"
                    ),
                    func.coalesce(Detection.source, DetectionSource.NONE).label(
                        "detection_source"
                    ),
                    func.coalesce(img_subq.c.image_count, 0).label("image_count"),
                    func.coalesce(img_subq.c.image_filenames, "").label(
                        "image_filenames"
                    ),
                    func.coalesce(img_subq.c.image_ids, "").label("image_ids"),
                    ProcessedBench.detection_status,
                    ProcessedBench.best_image_id,
                    Detection.id.label("best_detection_id"),
                    func.coalesce(seg_subq.c.has_segmentation, 0).label(
                        "has_segmentation"
                    ),
                )
                .join(
                    BenchCandidate,
                    ProcessedBench.bench_candidate_id == BenchCandidate.id,
                )
                .outerjoin(Detection, ProcessedBench.best_detection_id == Detection.id)
                .outerjoin(img_subq, BenchCandidate.id == img_subq.c.bench_candidate_id)
                .outerjoin(seg_subq, Detection.id == seg_subq.c.detection_id)
            )

            # Add source filtering if specified
            if source is not None:
                query = query.filter(BenchCandidate.source == source)

            # Filter by mode
            if mode == BenchMode.BENCHES:
                query = query.filter(
                    ProcessedBench.detection_status == "detected",
                    func.coalesce(Detection.max_confidence, 0.0) >= min_confidence,
                )
            elif mode == BenchMode.NO_BENCH:
                query = query.filter(ProcessedBench.detection_status == "no_bench")

            # Optimized total count - count distinct IDs instead of distinct().count()
            total_count_query = query.with_entities(ProcessedBench.id).distinct()
            total_count = (
                session.query(func.count())
                .select_from(total_count_query.subquery())
                .scalar()
                or 0
            )

            # Apply sorting
            if sort_by == "confidence":
                query = query.order_by(
                    func.coalesce(Detection.max_confidence, 0.0).desc(),
                    ProcessedBench.id,
                )
            elif sort_by == "images":
                query = query.order_by(
                    func.coalesce(img_subq.c.image_count, 0).desc(),
                    func.coalesce(Detection.max_confidence, 0.0).desc(),
                    ProcessedBench.id,
                )
            elif sort_by == "recent":
                query = query.order_by(ProcessedBench.id.desc())
            else:  # distance (default)
                distance_expr = (BenchCandidate.lat - start_lat) * (
                    BenchCandidate.lat - start_lat
                ) + (BenchCandidate.lng - start_lng) * (BenchCandidate.lng - start_lng)
                query = query.order_by(
                    distance_expr.asc(),
                    func.coalesce(Detection.max_confidence, 0.0).desc(),
                )

            # Apply pagination
            offset = page * page_size
            results = query.offset(offset).limit(page_size).all()

            # Batch load detection items if requested - eliminates N+1 query
            detection_items_map = {}
            if include_detection_data:
                # Collect all bench_candidate_ids
                bench_candidate_ids = [r.bench_candidate_id for r in results]
                if bench_candidate_ids:
                    # Single optimized query with joins to get all data at once
                    detection_items_query = (
                        session.query(
                            DetectionItem,
                            Image.bench_candidate_id,
                        )
                        .join(Detection, DetectionItem.detection_id == Detection.id)
                        .join(Image, Detection.image_id == Image.id)
                        .filter(Image.bench_candidate_id.in_(bench_candidate_ids))
                        .order_by(DetectionItem.confidence.desc())
                        .all()
                    )
                    # Group by bench_candidate_id
                    for item, bc_id in detection_items_query:
                        if bc_id not in detection_items_map:
                            detection_items_map[bc_id] = []
                        # Ensure bbox and polygon are proper model instances
                        bbox = None
                        if item.bbox:
                            if isinstance(item.bbox, dict):
                                from bench_finder.models.unified_models import (
                                    BoundingBox,
                                )

                                bbox = BoundingBox(**item.bbox)
                            else:
                                bbox = item.bbox
                        polygon = None
                        if item.polygon:
                            if isinstance(item.polygon, dict):
                                from bench_finder.models.unified_models import Polygon

                                polygon = Polygon(**item.polygon)
                            else:
                                polygon = item.polygon
                        detection_items_map[bc_id].append(
                            ApiDetectionItem(
                                detection_id=item.detection_id,
                                confidence=item.confidence,
                                bbox=bbox,
                                class_name=item.class_name,
                                polygon=polygon,
                            )
                        )

            # Process results
            benches = []
            for result in results:
                bench_candidate_id = result.bench_candidate_id
                best_confidence = result.best_confidence or 0.0
                detection_source = result.detection_source or DetectionSource.NONE

                # Parse image data
                image_filenames_str = result.image_filenames or ""
                image_ids_str = result.image_ids or ""
                image_filenames = (
                    image_filenames_str.split(",") if image_filenames_str else []
                )
                image_ids = (
                    [int(x) for x in image_ids_str.split(",") if x]
                    if image_ids_str
                    else []
                )

                # Sort images so best image is first
                image_filenames, image_ids = sort_images_by_best(
                    image_filenames, image_ids, result.best_image_id
                )

                # Has segmentation is now from the query (no N+1!)
                has_segmentation = bool(result.has_segmentation)

                # Calculate distance
                distance = calculate_distance(
                    start_lat, start_lng, result.lat, result.lng
                )

                # Get detection items from batch-loaded map
                detection_items = (
                    detection_items_map.get(bench_candidate_id)
                    if include_detection_data
                    else None
                )

                # Set source-specific confidence
                roboflow_confidence = 0.0
                ultralytics_confidence = 0.0
                mapillary_confidence = 0.0
                if detection_source == DetectionSource.ROBOFLOW:
                    roboflow_confidence = best_confidence
                elif detection_source == DetectionSource.ULTRALYTICS:
                    ultralytics_confidence = best_confidence
                elif detection_source == DetectionSource.MAPILLARY:
                    mapillary_confidence = best_confidence

                bench_data = WebBenchData(
                    id=result.processed_bench_id,
                    provider_id=result.provider_id,
                    lat=result.lat,
                    lng=result.lng,
                    tags=result.tags or {},
                    source=_safe_convert_source(result.source),
                    external_id=result.external_id,
                    bench_found=result.detection_status == "detected",
                    best_confidence=round(best_confidence, 3),
                    roboflow_confidence=round(roboflow_confidence, 3),
                    ultralytics_confidence=round(ultralytics_confidence, 3),
                    mapillary_confidence=round(mapillary_confidence, 3),
                    detection_type=detection_source,
                    has_segmentation=has_segmentation,
                    image_count=result.image_count or 0,
                    image_filenames=image_filenames,
                    image_ids=image_ids,
                    best_image_id=result.best_image_id,
                    best_detection_id=result.best_detection_id,
                    distance_meters=round(distance),
                    distance_km=round(distance / 1000, 2),
                    detection_items=detection_items,
                )

                benches.append(bench_data)

            pagination = PaginationInfo(
                page=page,
                page_size=page_size,
                total_count=total_count,
                total_pages=math.ceil(total_count / page_size),
                has_next=(page + 1) * page_size < total_count,
            )

            return BenchListResponse(benches=benches, pagination=pagination)

    except Exception as e:
        print(f"Error getting high confidence benches: {e}")
        import traceback

        traceback.print_exc()
        return BenchListResponse(
            benches=[],
            pagination=PaginationInfo(
                page=0,
                page_size=page_size,
                total_count=0,
                total_pages=0,
                has_next=False,
            ),
        )


# BENCH ENDPOINTS
@app.get(
    "/api/benches",
    summary="List Benches",
    description="Get paginated list of benches with high confidence detections, sorted by various criteria",
    response_model=BenchListResponse,
    responses={
        400: {
            "model": EnhancedErrorResponse,
            "description": "Invalid query parameters",
        },
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["benches"],
)
async def get_benches(
    page: int = Query(0, ge=0, le=1000, description="Page number (0-based)"),
    page_size: int = Query(
        PAGE_SIZE, ge=1, le=50, description="Items per page (max 50)"
    ),
    min_confidence: float = Query(
        DEFAULT_MIN_CONFIDENCE,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence",
    ),
    start_lat: float = Query(
        DEFAULT_START_LAT,
        ge=-90.0,
        le=90.0,
        description="Starting latitude for distance sorting",
    ),
    start_lng: float = Query(
        DEFAULT_START_LNG,
        ge=-180.0,
        le=180.0,
        description="Starting longitude for distance sorting",
    ),
    sort_by: str = Query(
        "distance",
        pattern="^(distance|confidence|images|recent)$",
        description="Sort criteria",
    ),
    source: DataSource | None = Query(
        None,
        description="Filter by data source: 'osm' or 'mapillary' (default: all sources)",
    ),
    mode: BenchMode = Query(
        BenchMode.BENCHES,
        description="Return mode: 'benches' (detected), 'no_bench' (not detected), or 'both'",
    ),
    include_detection_data: bool = Query(
        False,
        description="Include detection items (bbox, polygon) in response (default: False)",
    ),
):
    """
    Retrieve a paginated list of benches with configurable detection modes.

    This endpoint returns bench candidates based on the specified mode:
    - `benches`: Only candidates where benches were detected (default)
    - `no_bench`: Only candidates where no benches were detected
    - `both`: Return both types of candidates

    Results can be sorted by various criteria including distance from a reference point,
    detection confidence, number of images, or creation date.

    **Sorting Options:**
    - `distance`: Sort by distance from start_lat/start_lng (default)
    - `confidence`: Sort by highest detection confidence first
    - `images`: Sort by number of images per bench
    - `recent`: Sort by most recently added benches

    **Data Sources:**
    - `osm`: OpenStreetMap data with computer vision detections
    - `mapillary`: Street-level imagery from Mapillary with AI detections
    """
    try:
        result = get_high_confidence_benches_filtered(
            page=page,
            page_size=page_size,
            min_confidence=min_confidence,
            start_lat=start_lat,
            start_lng=start_lng,
            sort_by=sort_by,
            mode=mode,
            include_detection_data=include_detection_data,
            source=source,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve benches: {e!s}",
        ) from e


# Source-specific endpoint removed - use unified /api/benches endpoint instead


@app.get(
    "/api/benches/random",
    summary="Get Random Bench",
    description="Get a randomly selected bench that meets the specified criteria",
    response_model=WebBenchData,
    responses={
        404: {
            "model": EnhancedErrorResponse,
            "description": "No benches found matching criteria",
        },
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["benches"],
)
async def get_random_bench(
    min_confidence: float = Query(
        DEFAULT_MIN_CONFIDENCE,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence",
    ),
    mode: BenchMode = Query(
        BenchMode.BENCHES,
        description="Return mode: 'benches' (detected), 'no_bench' (not detected), or 'both'",
    ),
    include_detection_data: bool = Query(
        False,
        description="Include detection items (bbox, polygon) in response (default: False)",
    ),
    source: DataSource | None = Query(
        None,
        description="Filter by data source: 'osm' or 'mapillary' (default: all sources)",
    ),
):
    """
    Get a randomly selected bench that meets the specified criteria.

    This is useful for exploring the dataset or providing "discover" functionality
    in user interfaces. The randomization is performed at the database level
    for efficiency.

    **Source Filtering:**
    - `osm`: Filter to only OpenStreetMap sourced benches
    - `mapillary`: Filter to only Mapillary sourced benches
    - `null` (default): Include all sources
    """
    try:
        db = BenchDatabase()
        with db.get_session() as session:
            from sqlalchemy import func

            # Start from ProcessedBench, join to BenchCandidate and Detection
            base_query = (
                session.query(ProcessedBench)
                .join(
                    BenchCandidate,
                    ProcessedBench.bench_candidate_id == BenchCandidate.id,
                )
                .outerjoin(Detection, ProcessedBench.best_detection_id == Detection.id)
            )

            # Add source filtering if specified
            if source is not None:
                base_query = base_query.filter(BenchCandidate.source == source)

            if mode == BenchMode.BENCHES:
                # Only benches with detected benches
                base_query = base_query.filter(
                    ProcessedBench.detection_status == "detected",
                    Detection.max_confidence >= min_confidence,
                )
            elif mode == BenchMode.NO_BENCH:
                # Only benches without detected benches
                base_query = base_query.filter(
                    ProcessedBench.detection_status == "no_bench"
                )
            # For BOTH mode, no additional filtering needed

            # Get random bench
            random_bench = base_query.order_by(func.random()).first()

            if not random_bench:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No benches found matching the specified criteria",
                )

            # Use the unified helper to get bench data
            bench_data = get_bench_by_id(
                bench_id=random_bench.id,
                include_detection_data=include_detection_data,
            )

            return bench_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get random bench: {e!s}",
        ) from e


@app.get(
    "/api/bench/{bench_id}",
    summary="Get Bench by ID",
    description="Get detailed information for a specific bench by its ID",
    response_model=WebBenchData,
    responses={
        404: {
            "model": EnhancedErrorResponse,
            "description": "Bench not found",
        },
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["benches"],
)
async def get_bench_by_id_endpoint(
    bench_id: int = Path(..., description="Bench ID to retrieve"),
    include_detection_data: bool = Query(
        False,
        description="Include detection items (bbox, polygon) in response (default: False)",
    ),
):
    """
    Get detailed information for a specific bench by its ID.

    This endpoint provides comprehensive bench data including:
    - Basic bench information (location, source, tags)
    - Image count and filenames
    - Detection confidence scores from all sources
    - Optional detection items with bounding boxes and polygons
    """
    bench_data = get_bench_by_id(
        bench_id=bench_id,
        include_detection_data=include_detection_data,
    )

    return bench_data


@app.get(
    "/api/benches/bbox",
    summary="Get Benches in Bounding Box",
    description="Get benches within a geographic bounding box for map applications",
    response_model=BboxBenchResponse,
    responses={
        400: {
            "model": EnhancedErrorResponse,
            "description": "Invalid bounding box parameters",
        },
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["benches"],
)
async def get_benches_in_bbox(
    north: float = Query(
        ..., ge=-90.0, le=90.0, description="Northern latitude boundary"
    ),
    south: float = Query(
        ..., ge=-90.0, le=90.0, description="Southern latitude boundary"
    ),
    east: float = Query(
        ..., ge=-180.0, le=180.0, description="Eastern longitude boundary"
    ),
    west: float = Query(
        ..., ge=-180.0, le=180.0, description="Western longitude boundary"
    ),
    min_confidence: float = Query(
        DEFAULT_MIN_CONFIDENCE,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence",
    ),
    source: DataSource | None = Query(
        None,
        description="Filter by data source: 'osm' or 'mapillary' (default: all sources)",
    ),
    mode: BenchMode = Query(
        BenchMode.BENCHES,
        description="Return mode: 'benches' (detected), 'no_bench' (not detected), or 'both'",
    ),
    sort_by: str = Query(
        "distance",
        pattern="^(distance|confidence|images|recent)$",
        description="Sort criteria",
    ),
    limit: int = Query(200, ge=1, le=500, description="Maximum number of results"),
    include_detection_data: bool = Query(
        False,
        description="Include detection items (bbox, polygon) in response (default: False)",
    ),
):
    """
    Get benches within a geographic bounding box.

    This endpoint is optimized for map applications that need to display benches
    within a specific viewport. The bounding box is defined by north/south latitude
    boundaries and east/west longitude boundaries.

    **Mode Options:**
    - `benches`: Only return candidates where benches were detected (default)
    - `no_bench`: Only return candidates where no benches were detected
    - `both`: Return both types of candidates

    **Source Filtering:**
    - `osm`: Filter to only OpenStreetMap sourced benches
    - `mapillary`: Filter to only Mapillary sourced benches
    - `null` (default): Include all sources

    **Geographic Validation:**
    - North must be greater than South
    - East must be greater than West
    - All coordinates must be within valid lat/lng ranges

    **Performance Notes:**
    - Results are limited to prevent excessive data transfer
    - Distance sorting uses the bounding box center as reference point
    """
    try:
        # Validate bounding box first
        if north <= south:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="North boundary must be greater than south boundary",
            )

        if east <= west:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="East boundary must be greater than west boundary",
            )

        # Get individual bench results using ORM - start from ProcessedBench
        db = BenchDatabase()
        with db.get_session() as session:
            from sqlalchemy import func

            # Start from ProcessedBench, join to BenchCandidate and Detection
            base_query = (
                session.query(
                    ProcessedBench.id.label("processed_bench_id"),
                    BenchCandidate.id.label("bench_candidate_id"),
                    BenchCandidate.provider_id,
                    BenchCandidate.lat,
                    BenchCandidate.lng,
                    BenchCandidate.tags,
                    BenchCandidate.source,
                    BenchCandidate.external_id,
                    func.coalesce(Detection.max_confidence, 0.0).label(
                        "best_confidence"
                    ),
                    func.coalesce(Detection.source, DetectionSource.NONE).label(
                        "detection_source"
                    ),
                    Detection.id.label("best_detection_id"),
                    ProcessedBench.detection_status,
                    ProcessedBench.best_image_id,
                    func.count(func.distinct(Image.id)).label("image_count"),
                    func.group_concat(func.distinct(Image.filename)).label(
                        "image_filenames"
                    ),
                    func.group_concat(func.distinct(Image.id)).label("image_ids"),
                )
                .join(
                    BenchCandidate,
                    ProcessedBench.bench_candidate_id == BenchCandidate.id,
                )
                .outerjoin(Detection, ProcessedBench.best_detection_id == Detection.id)
                .outerjoin(
                    Image,
                    (Image.bench_candidate_id == BenchCandidate.id)
                    & (Image.capture_success == 1),
                    full=False,
                )
                .filter(
                    BenchCandidate.lat.between(south, north),
                    BenchCandidate.lng.between(west, east),
                )
                .group_by(
                    ProcessedBench.id,
                    BenchCandidate.id,
                    BenchCandidate.provider_id,
                    BenchCandidate.lat,
                    BenchCandidate.lng,
                    BenchCandidate.tags,
                    BenchCandidate.source,
                    BenchCandidate.external_id,
                    Detection.max_confidence,
                    Detection.source,
                    ProcessedBench.detection_status,
                    ProcessedBench.best_image_id,
                    Detection.id,
                )
            )

            # Add source filtering if specified
            if source is not None:
                base_query = base_query.filter(BenchCandidate.source == source)

            # Apply mode-specific filtering
            if mode == BenchMode.BENCHES:
                base_query = base_query.filter(
                    ProcessedBench.detection_status == "detected",
                    func.coalesce(Detection.max_confidence, 0.0) >= min_confidence,
                )
            elif mode == BenchMode.NO_BENCH:
                base_query = base_query.filter(
                    ProcessedBench.detection_status == "no_bench"
                )

            # Apply sorting
            center_lat = (north + south) / 2
            center_lng = (east + west) / 2

            if sort_by == "confidence":
                base_query = base_query.order_by(
                    func.coalesce(Detection.max_confidence, 0.0).desc(),
                    ProcessedBench.id,
                )
            elif sort_by == "images":
                base_query = base_query.order_by(
                    func.count(func.distinct(Image.id)).desc(),
                    func.coalesce(Detection.max_confidence, 0.0).desc(),
                    ProcessedBench.id,
                )
            elif sort_by == "recent":
                base_query = base_query.order_by(ProcessedBench.id.desc())
            else:  # distance (default)
                distance_expr = (BenchCandidate.lat - center_lat) * (
                    BenchCandidate.lat - center_lat
                ) + (BenchCandidate.lng - center_lng) * (
                    BenchCandidate.lng - center_lng
                )
                base_query = base_query.order_by(
                    distance_expr.asc(),
                    func.coalesce(Detection.max_confidence, 0.0).desc(),
                )

            # Apply limit
            results = base_query.limit(limit).all()

            # Process results
            benches = []
            for result in results:
                # Use named column access
                bench_candidate_id = result.bench_candidate_id
                best_confidence = result.best_confidence or 0.0
                detection_source = result.detection_source or DetectionSource.NONE

                # Parse image data
                image_filenames_str = result.image_filenames or ""
                image_ids_str = result.image_ids or ""
                image_filenames = (
                    image_filenames_str.split(",") if image_filenames_str else []
                )
                image_ids = (
                    [int(x) for x in image_ids_str.split(",") if x]
                    if image_ids_str
                    else []
                )

                # Sort images so best image is first
                image_filenames, image_ids = sort_images_by_best(
                    image_filenames, image_ids, result.best_image_id
                )

                # Check for segmentation - check DetectionItems polygon field
                has_segmentation = False
                best_detection_id = result.best_detection_id
                if best_detection_id:
                    has_segmentation_query = (
                        session.query(DetectionItem)
                        .filter(DetectionItem.detection_id == best_detection_id)
                        .filter(DetectionItem.polygon.isnot(None))
                        .first()
                    )
                    has_segmentation = has_segmentation_query is not None

                # Calculate distance from center
                distance = calculate_distance(
                    center_lat, center_lng, result.lat, result.lng
                )

                # Set source-specific confidence - don't coalesce, just use best_detection
                roboflow_confidence = 0.0
                ultralytics_confidence = 0.0
                mapillary_confidence = 0.0
                if detection_source == DetectionSource.ROBOFLOW:
                    roboflow_confidence = best_confidence
                elif detection_source == DetectionSource.ULTRALYTICS:
                    ultralytics_confidence = best_confidence
                elif detection_source == DetectionSource.MAPILLARY:
                    mapillary_confidence = best_confidence

                # Get detection items if requested
                detection_items = None
                if include_detection_data:
                    detection_items = get_detection_items_for_bench(
                        session, bench_candidate_id
                    )

                bench_data = WebBenchData(
                    id=result.processed_bench_id,
                    provider_id=result.provider_id,
                    lat=result.lat,
                    lng=result.lng,
                    tags=result.tags or {},
                    source=_safe_convert_source(result.source),
                    external_id=result.external_id,
                    bench_found=result.detection_status == "detected",
                    best_confidence=round(best_confidence, 3),
                    roboflow_confidence=round(roboflow_confidence, 3),
                    ultralytics_confidence=round(ultralytics_confidence, 3),
                    mapillary_confidence=round(mapillary_confidence, 3),
                    detection_type=detection_source,
                    has_segmentation=has_segmentation,
                    image_count=result.image_count or 0,
                    image_filenames=image_filenames,
                    image_ids=image_ids,
                    best_image_id=result.best_image_id,
                    best_detection_id=result.best_detection_id,
                    distance_meters=round(distance),
                    distance_km=round(distance / 1000, 2),
                    detection_items=detection_items,
                )

                benches.append(bench_data)

            return BboxBenchResponse(
                benches=benches,
                total_count=len(benches),
                bbox={"north": north, "south": south, "east": east, "west": west},
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get benches in bounding box: {e!s}",
        ) from e


# SEARCH AND CONFIGURATION ENDPOINTS
@app.get(
    "/api/searches",
    summary="List Available Searches",
    description="Get list of completed search operations with bench counts",
    response_model=SearchListResponse,
    responses={
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
    },
    tags=["search"],
)
async def get_searches():
    """
    Get a list of completed search operations with metadata.

    This endpoint returns historical search data that can be used to:
    - Display previous search locations in the UI
    - Show search statistics and bench counts
    - Enable users to revisit successful search areas

    Only completed searches with associated bench data are returned.
    """
    try:
        db = BenchDatabase()
        with db.get_session() as session:
            from sqlalchemy import func

            # Query searches with bench counts using ORM - via ProcessedBench
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


@app.get(
    "/api/config",
    summary="Get Application Configuration",
    description="Get default configuration values for the frontend application",
    response_model=ConfigResponse,
    tags=["config"],
)
async def get_config():
    """
    Get application configuration for frontend initialization.

    This endpoint provides default values that the frontend can use for:
    - Initial map center coordinates
    - Default confidence thresholds
    - Pagination settings
    - API version information

    These values are used to initialize the user interface with sensible defaults
    based on the available data in the system.
    """
    return ConfigResponse(
        default_start_lat=DEFAULT_START_LAT,
        default_start_lng=DEFAULT_START_LNG,
        default_min_confidence=DEFAULT_MIN_CONFIDENCE,
        page_size=PAGE_SIZE,
    )


@app.get(
    "/api/info",
    summary="Get API Information",
    description="Get comprehensive API information including capabilities and limits",
    response_model=ApiInfoResponse,
    tags=["config"],
)
async def get_api_info():
    """
    Get detailed API information including capabilities and usage limits.

    This endpoint provides comprehensive metadata about the API including:
    - Supported data sources and detection models
    - Available features and endpoints
    - Usage limits and performance constraints
    - Version information
    """
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


# IMAGE AND DETECTION ENDPOINTS
@app.get(
    "/images/{filename}",
    summary="Serve Bench Images",
    description="Serve bench images from the images directory",
    response_class=FileResponse,
    responses={
        404: {"model": EnhancedErrorResponse, "description": "Image not found"},
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["images"],
)
async def serve_image(filename: str = Path(..., description="Image filename")):
    """
    Serve bench images from the configured storage backend (local or Firebase).

    This endpoint serves static image files that have been captured and processed
    as part of the bench detection pipeline. It supports both local filesystem
    storage and Firebase Storage for cloud hosting.

    **Storage Backends:**
    - **Local**: Images served directly from filesystem
    - **Firebase**: Images are redirected to Firebase Storage URLs (if available in DB)

    **Security Notes:**
    - Only files within the configured images directory are served (local mode)
    - Path traversal attacks are prevented by FastAPI's path validation
    - File existence is validated before serving
    """
    try:
        # First, check if the image exists in the database with a Firebase URL
        db = BenchDatabase()
        with db.get_session() as session:
            image = session.query(Image).filter(Image.filename == filename).first()

            # If image has Firebase URL, redirect to it
            if image and image.firebase_url:
                from fastapi.responses import RedirectResponse

                return RedirectResponse(
                    url=image.firebase_url, status_code=status.HTTP_302_FOUND
                )

        # Fallback to local file serving
        images_path = os.path.abspath(IMAGES_DIR)
        file_path = os.path.join(images_path, filename)

        # Security check: ensure the resolved path is within the images directory
        if not os.path.abspath(file_path).startswith(images_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
            )

        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image '{filename}' not found",
            )

        return FileResponse(
            file_path,
            media_type="image/jpeg",  # Assuming JPEG images, could be made dynamic
            headers={"Cache-Control": "public, max-age=3600"},  # Cache for 1 hour
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to serve image: {e!s}",
        ) from e


@app.get(
    "/api/image/{image_id}/segmentation",
    summary="Get Detection Visualization Data",
    description="Get detection visualization data for a specific image (segmentation and bounding boxes)",
    response_model=SegmentationData,
    responses={
        404: {
            "model": EnhancedErrorResponse,
            "description": "Image not found",
        },
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["images"],
)
async def get_image_segmentation(
    image_id: int = Path(..., ge=1, description="Image ID"),
):
    """
    Get detection visualization data for a specific image.

    This endpoint returns detection data that can be used to visualize:
    - **Segmentation polygons** from Ultralytics YOLO models
    - **Bounding boxes** from Roboflow models
    - **Combined visualizations** when both are available

    The response includes the original image filename, detection coordinates,
    confidence scores, and metadata needed for accurate visualization overlay.

    **Detection Types:**
    - `segmentation`: Polygon-based detection outlines
    - `bounding_box`: Rectangular detection regions
    - `both`: Combined segmentation and bounding box data

    **Note:** If no detection data is found for the image, an empty response
    is returned (empty detection_items list) rather than raising a 404 error.
    """
    try:
        db = BenchDatabase()
        with db.get_session() as session:
            from sqlalchemy.orm import joinedload

            # Get image with detections using ORM
            image = (
                session.query(Image)
                .options(
                    joinedload(Image.detections).joinedload(Detection.detection_items)
                )
                .filter(Image.id == image_id)
                .first()
            )

            if not image:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Image with ID {image_id} not found",
                )

            # Filter detections that have benches
            detections = [d for d in image.detections if d.has_bench]

            if not detections:
                # Return empty segmentation data instead of raising an exception
                return SegmentationData(
                    filename=image.filename or "unknown",
                    detection_type="bounding_box",  # Default when no data
                    detection_items=[],
                    image_shape=None,
                    segmentation_available=False,
                    bounding_box_available=False,
                    confidence_score=0.0,
                    source=DetectionSource.NONE,
                )

            # Collect all detection items from all detections
            all_detection_items = []
            max_confidence = 0.0
            detection_sources = set()
            has_segmentation = False
            has_bounding_box = False

            for detection in detections:
                for item in detection.detection_items:
                    # Ensure bbox and polygon are proper model instances, not dicts
                    bbox = None
                    if item.bbox:
                        if isinstance(item.bbox, dict):
                            # Convert dict to BoundingBox model
                            from bench_finder.models.unified_models import BoundingBox

                            bbox = BoundingBox(**item.bbox)
                        else:
                            bbox = item.bbox  # Already a BoundingBox instance

                    polygon = None
                    if item.polygon:
                        if isinstance(item.polygon, dict):
                            # Convert dict to Polygon model
                            from bench_finder.models.unified_models import Polygon

                            polygon = Polygon(**item.polygon)
                        else:
                            polygon = item.polygon  # Already a Polygon instance

                    # Create a new ApiDetectionItem with proper model instances
                    detection_item = ApiDetectionItem(
                        detection_id=item.detection_id,
                        confidence=item.confidence,
                        bbox=bbox,
                        class_name=item.class_name,
                        polygon=polygon,
                    )
                    all_detection_items.append(detection_item)

                    # Track capabilities
                    if item.polygon:
                        has_segmentation = True
                    if item.bbox:
                        has_bounding_box = True

                # Track max confidence and sources
                max_confidence = max(max_confidence, detection.max_confidence or 0.0)
                detection_sources.add(detection.source)

            # Determine detection type based on available data (not source)
            if has_segmentation and has_bounding_box:
                detection_type = "both"
            elif has_segmentation:
                detection_type = "segmentation"
            else:
                detection_type = "bounding_box"

            # Use the actual detection source from the first detection (not inferred from type)
            # If multiple detections, use the one with highest confidence
            primary_source = DetectionSource.ROBOFLOW  # Default
            if detection_sources:
                # Get the detection with highest confidence to determine primary source
                best_detection = max(detections, key=lambda d: d.max_confidence or 0.0)
                primary_source = best_detection.source

            return SegmentationData(
                filename=image.filename or "unknown",
                detection_type=detection_type,
                detection_items=all_detection_items,
                image_shape=None,  # Not available in unified model
                segmentation_available=has_segmentation,
                bounding_box_available=has_bounding_box,
                confidence_score=max_confidence,
                source=primary_source,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve detection data: {e!s}",
        ) from e


@app.get(
    "/api/bench/{bench_id}/images",
    summary="Get Bench Images",
    description="Get all images for a specific bench with metadata",
    response_model=ImageListResponse,
    responses={
        404: {"model": EnhancedErrorResponse, "description": "Bench not found"},
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["images"],
)
async def get_bench_images(bench_id: int = Path(..., ge=1, description="Bench ID")):
    """
    Get all images associated with a specific bench.

    This endpoint returns comprehensive image metadata including:
    - Image filenames and file paths
    - Capture headings (camera direction)
    - File sizes and capture status
    - Error information for failed captures

    Images are sorted by heading to provide a consistent viewing order
    representing different viewpoints around the bench.

    **Use Cases:**
    - Image gallery displays
    - 360-degree bench viewing
    - Debugging capture issues
    - Metadata analysis
    """
    try:
        db = BenchDatabase()
        with db.get_session() as session:
            # Verify ProcessedBench exists using ORM
            processed_bench = (
                session.query(ProcessedBench)
                .filter(ProcessedBench.id == bench_id)
                .first()
            )

            if not processed_bench:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"ProcessedBench with ID {bench_id} not found",
                )

            bench_candidate_id = processed_bench.bench_candidate_id

            # Get all successful images for the bench candidate using ORM
            images_query = (
                session.query(Image)
                .filter(
                    Image.bench_candidate_id == bench_candidate_id,
                    Image.capture_success == 1,
                )
                .order_by(Image.heading)
                .all()
            )

            images = []
            for image in images_query:
                image_response = ImageResponse(
                    id=image.id,
                    bench_id=bench_id,  # Use ProcessedBench id for API compatibility
                    heading=image.heading,
                    filepath=image.filepath,
                    filename=image.filename,
                    file_size=image.file_size,
                    capture_success=image.capture_success,
                    capture_error=image.capture_error,
                    created_at=image.created_at,
                )
                images.append(image_response)

            return ImageListResponse(images=images)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve bench images: {e!s}",
        ) from e


@app.get(
    "/api/bench/{bench_id}/detections",
    summary="Get Bench Detection Data",
    description="Get comprehensive detection data for a specific bench including all images and detection items",
    response_model=BenchDetectionData,
    responses={
        404: {"model": EnhancedErrorResponse, "description": "Bench not found"},
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["images"],
)
async def get_bench_detections(bench_id: int = Path(..., ge=1, description="Bench ID")):
    """
    Get comprehensive detection data for a specific bench.

    This endpoint returns all detection data associated with a bench, including:
    - All images with their detection items
    - Bounding box coordinates for each detection
    - Polygon/segmentation data when available
    - Confidence scores and detection metadata
    - Detection source information (Roboflow, Ultralytics, etc.)

    **Use Cases:**
    - Detailed analysis of bench detections
    - Visualization of detection overlays
    - Quality assessment of detection results
    - Debugging detection issues

    **Response Structure:**
    - `bench_id`: The bench identifier
    - `images`: List of images with their detection data
    - `detection_items`: List of DetectionItem objects with bbox and polygon data
    - `confidence_scores`: Best confidence across all detections
    - `detection_sources`: List of detection backends used
    """
    try:
        db = BenchDatabase()
        with db.get_session() as session:
            from sqlalchemy.orm import joinedload

            # Get ProcessedBench info using ORM
            processed_bench = (
                session.query(ProcessedBench)
                .filter(ProcessedBench.id == bench_id)
                .first()
            )

            if not processed_bench:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"ProcessedBench with ID {bench_id} not found",
                )

            bench_candidate_id = processed_bench.bench_candidate_id

            # Get bench candidate for lat/lng
            bench_candidate = (
                session.query(BenchCandidate)
                .filter(BenchCandidate.id == bench_candidate_id)
                .first()
            )

            if not bench_candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"BenchCandidate with ID {bench_candidate_id} not found",
                )

            # Get all images for this bench candidate with their detection data using ORM
            images_query = (
                session.query(Image)
                .options(
                    joinedload(Image.detections).joinedload(Detection.detection_items)
                )
                .filter(Image.bench_candidate_id == bench_candidate_id)
                .order_by(Image.heading)
                .all()
            )

            if not images_query:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No images found for bench ID {bench_id}",
                )

            # Process images and their detection data
            images_data = []
            detection_sources = set()
            best_confidence = 0.0
            images_with_detections = 0

            for image in images_query:
                detection_items = []

                for detection in image.detections:
                    for item in detection.detection_items:
                        # Ensure bbox and polygon are proper model instances, not dicts
                        bbox = None
                        if item.bbox:
                            if isinstance(item.bbox, dict):
                                # Convert dict to BoundingBox model
                                from bench_finder.models.unified_models import (
                                    BoundingBox,
                                )

                                bbox = BoundingBox(**item.bbox)
                            else:
                                bbox = item.bbox  # Already a BoundingBox instance

                        polygon = None
                        if item.polygon:
                            if isinstance(item.polygon, dict):
                                # Convert dict to Polygon model
                                from bench_finder.models.unified_models import Polygon

                                polygon = Polygon(**item.polygon)
                            else:
                                polygon = item.polygon  # Already a Polygon instance

                        # Create a new ApiDetectionItem with proper model instances
                        detection_item = ApiDetectionItem(
                            detection_id=item.detection_id,
                            confidence=item.confidence,
                            bbox=bbox,
                            class_name=item.class_name,
                            polygon=polygon,
                        )
                        detection_items.append(detection_item)

                        # Track best confidence and sources
                        best_confidence = max(best_confidence, item.confidence)
                        detection_sources.add(detection.source)

                # Count images with detections
                if detection_items:
                    images_with_detections += 1

                image_data = ImageWithDetectionData(
                    image_id=image.id,
                    filename=image.filename,
                    heading=image.heading,
                    capture_success=image.capture_success,
                    detection_items=detection_items,
                )
                images_data.append(image_data)

            return BenchDetectionData(
                bench_id=bench_id,
                bench_lat=bench_candidate.lat,
                bench_lng=bench_candidate.lng,
                total_images=len(images_data),
                images_with_detections=images_with_detections,
                best_confidence=best_confidence,
                detection_sources=list(detection_sources),
                images=images_data,
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve bench detection data: {e!s}",
        ) from e


# Mapillary endpoints removed - using unified approach


# REPORTING ENDPOINTS
@app.post(
    "/api/benches/{bench_id}/report",
    summary="Report Bad Bench Detection",
    description="Report a bad bench detection with optional description and image data",
    response_model=ReportResponse,
    responses={
        400: {
            "model": EnhancedErrorResponse,
            "description": "Invalid bench ID or request data",
        },
        404: {"model": EnhancedErrorResponse, "description": "Bench not found"},
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["reporting"],
)
async def report_bad_bench(
    request: Request,
    bench_id: int = Path(..., gt=0, description="Bench ID to report"),
    report_type: BenchReportType = Body(
        BenchReportType.BAD_DETECTION, description="Type of report"
    ),
    description: str | None = Body(
        None, description="Optional description of the issue"
    ),
    image_id: int | None = Body(None, description="Specific image ID being reported"),
    user_location_lat: float | None = Body(None, description="User's GPS latitude"),
    user_location_lng: float | None = Body(None, description="User's GPS longitude"),
):
    """
    Report a bad bench detection.

    This endpoint allows users to report issues with bench detections, such as:
    - **bad_detection**: AI incorrectly identified a bench where there isn't one
    - **incorrect_location**: Bench location is wrong
    - **poor_image_quality**: Image quality makes detection unreliable
    - **other**: Other issues (requires description)

    **Process:**
    1. Validate bench exists in database
    2. Store report with metadata (user agent, IP, timestamp)
    3. Optionally copy the reported image for review
    4. Return confirmation of successful report

    **Privacy:**
    Only basic metadata is stored for spam prevention and debugging.
    """
    try:
        import os
        import shutil
        from datetime import datetime

        from bench_finder.services.database import BenchDatabase

        db = BenchDatabase()

        with db.get_session() as session:
            # Verify ProcessedBench exists using ORM
            processed_bench = (
                session.query(ProcessedBench)
                .filter(ProcessedBench.id == bench_id)
                .first()
            )

            if not processed_bench:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"ProcessedBench with ID {bench_id} not found",
                )

            bench_candidate_id = processed_bench.bench_candidate_id

            # Get bench candidate for metadata
            bench_candidate = (
                session.query(BenchCandidate)
                .filter(BenchCandidate.id == bench_candidate_id)
                .first()
            )

            if not bench_candidate:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"BenchCandidate with ID {bench_candidate_id} not found",
                )

            # Verify image exists if provided using ORM
            reported_image_filename = None
            if image_id:
                image = (
                    session.query(Image)
                    .filter(
                        Image.id == image_id,
                        Image.bench_candidate_id == bench_candidate_id,
                    )
                    .first()
                )

                if image and image.filename:
                    # Copy the image for review purposes
                    source_path = os.path.join(IMAGES_DIR, image.filename)
                    if os.path.exists(source_path):
                        # Create reports directory if it doesn't exist
                        reports_dir = os.path.join(IMAGES_DIR, "reports")
                        os.makedirs(reports_dir, exist_ok=True)

                        # Create unique filename for the report
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        reported_image_filename = (
                            f"report_{bench_id}_{timestamp}_{image.filename}"
                        )
                        dest_path = os.path.join(reports_dir, reported_image_filename)

                        try:
                            shutil.copy2(source_path, dest_path)
                        except Exception as e:
                            print(f"Warning: Failed to copy reported image: {e}")
                            reported_image_filename = None

            # Get client information
            user_agent = request.headers.get("user-agent", "")
            client_host = request.client.host if request.client else None

            # Create report using ORM - BenchReport uses bench_candidate_id
            from bench_finder.models.unified_models import BenchReport

            report = BenchReport(
                bench_candidate_id=bench_candidate_id,
                image_id=image_id,
                report_type=report_type,
                description=description,
                user_agent=user_agent,
                ip_address=client_host,
                user_location_lat=user_location_lat,
                user_location_lng=user_location_lng,
                reported_image_filename=reported_image_filename,
                extra_metadata={
                    "processed_bench_id": bench_id,
                    "bench_source": bench_candidate.source,
                    "bench_provider_id": bench_candidate.provider_id,
                    "timestamp": datetime.now().isoformat(),
                },
            )

            session.add(report)
            session.commit()
            session.refresh(report)
            report_id = report.id

            return ReportResponse(
                success=True,
                report_id=report_id,
                message="Thank you for your report. It will be reviewed by our team.",
                bench_id=bench_id,
                report_type=report_type,
                created_at=datetime.now().isoformat(),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit report: {e!s}",
        ) from e


@app.post(
    "/api/missing-benches",
    summary="Report Missing Bench",
    description="Report a missing bench at a specific location with optional photo",
    response_model=MissingBenchReportResponse,
    responses={
        400: {
            "model": EnhancedErrorResponse,
            "description": "Invalid location or request data",
        },
        413: {"model": EnhancedErrorResponse, "description": "Image file too large"},
        500: {"model": EnhancedErrorResponse, "description": "Internal server error"},
    },
    tags=["reporting"],
)
async def report_missing_bench(
    request: Request,
    lat: float = Body(..., ge=-90.0, le=90.0, description="Bench latitude"),
    lng: float = Body(..., ge=-180.0, le=180.0, description="Bench longitude"),
    description: str | None = Body(None, description="Description of the bench"),
    location_method: str = Body(
        LocationMethod.GPS, description="How location was determined (gps, map_click)"
    ),
    user_location_lat: float | None = Body(None, description="User's GPS latitude"),
    user_location_lng: float | None = Body(None, description="User's GPS longitude"),
    accuracy_meters: float | None = Body(None, description="GPS accuracy in meters"),
    image_data: str | None = Body(None, description="Base64 encoded image data"),
):
    """
    Report a missing bench at a specific location.

    This endpoint allows users to report benches that exist in real life but are not
    in the system. It supports two location methods:

    **GPS Location ("RIGHT HERE" mode):**
    - Uses the user's current GPS coordinates
    - Includes accuracy information
    - Best for reporting benches at user's current location

    **Map Click ("MAP VIEW" mode):**
    - User clicks on a map to specify location
    - More precise for distant locations
    - Allows planning and remote reporting

    **Photo Upload:**
    - Optional base64-encoded image of the bench
    - Helps verify the report during review
    - Images are resized and compressed automatically

    **Process:**
    1. Validate location coordinates
    2. Process and store uploaded image (if provided)
    3. Store report with metadata
    4. Return confirmation with report ID
    """
    try:
        import base64
        import io
        import os
        from datetime import datetime

        from PIL import Image

        from bench_finder.services.database import BenchDatabase

        db = BenchDatabase()

        # Process uploaded image if provided
        uploaded_image_filename = None
        if image_data:
            try:
                # Decode base64 image
                if "," in image_data:
                    _header, image_data = image_data.split(",", 1)

                image_bytes = base64.b64decode(image_data)

                # Check file size (max 10MB)
                if len(image_bytes) > 10 * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Image file too large. Maximum size is 10MB.",
                    )

                # Process with PIL
                image = Image.open(io.BytesIO(image_bytes))

                # Convert to RGB if necessary
                if image.mode in ("RGBA", "P"):
                    image = image.convert("RGB")

                # Resize if too large (max 2048px on longest side)
                max_size = 2048
                if max(image.size) > max_size:
                    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

                # Save processed image
                missing_reports_dir = os.path.join(IMAGES_DIR, "missing_reports")
                os.makedirs(missing_reports_dir, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[
                    :-3
                ]  # Include milliseconds
                uploaded_image_filename = f"missing_{timestamp}_{lat}_{lng}.jpg"
                image_path = os.path.join(missing_reports_dir, uploaded_image_filename)

                image.save(image_path, "JPEG", quality=85, optimize=True)

            except Exception as e:
                print(f"Warning: Failed to process uploaded image: {e}")
                uploaded_image_filename = None

        # Get client information
        user_agent = request.headers.get("user-agent", "")
        client_host = request.client.host if request.client else None

        with db.get_session() as session:
            # Create missing bench report using ORM
            from bench_finder.models.unified_models import MissingBenchReport

            report = MissingBenchReport(
                lat=lat,
                lng=lng,
                description=description,
                user_agent=user_agent,
                ip_address=client_host,
                user_location_lat=user_location_lat,
                user_location_lng=user_location_lng,
                location_method=location_method,
                uploaded_image_filename=uploaded_image_filename,
                accuracy_meters=accuracy_meters,
                extra_metadata={
                    "timestamp": datetime.now().isoformat(),
                    "has_image": uploaded_image_filename is not None,
                },
            )

            session.add(report)
            session.commit()
            session.refresh(report)
            report_id = report.id

            return MissingBenchReportResponse(
                success=True,
                report_id=report_id,
                message="Thank you for reporting this missing bench. It will be reviewed by our team.",
                location={"lat": lat, "lng": lng},
                location_method=location_method,
                has_image=uploaded_image_filename is not None,
                created_at=datetime.now().isoformat(),
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit missing bench report: {e!s}",
        ) from e


# STATISTICS ENDPOINTS
# Source-specific statistics endpoint removed - use unified approach


# Test endpoints for stacktrace logging (remove in production)
@app.get(
    "/api/test-error",
    summary="Test 500 Error Endpoint",
    description="Test endpoint that triggers a 500 error to demonstrate stacktrace logging",
    tags=["config"],
)
async def test_error():
    """Test endpoint that raises an exception to demonstrate stacktrace logging."""
    raise ValueError(
        "This is a test error to demonstrate stacktrace logging in FastAPI logs"
    )


@app.get(
    "/api/test-400-error",
    summary="Test 400 Error Endpoint",
    description="Test endpoint that triggers a 400 error to demonstrate stacktrace logging",
    tags=["config"],
)
async def test_400_error():
    """Test endpoint that raises a ValueError to demonstrate 400 error stacktrace logging."""
    raise ValueError(
        "This is a test 400 error to demonstrate stacktrace logging in FastAPI logs"
    )


@app.get(
    "/api/test-validation-error",
    summary="Test Validation Error Endpoint",
    description="Test endpoint that triggers a validation error to demonstrate stacktrace logging",
    tags=["config"],
)
async def test_validation_error():
    """Test endpoint that demonstrates validation error stacktrace logging."""
    return {"message": "This endpoint requires a query parameter"}


if __name__ == "__main__":
    print("🚀 Starting Bench Finder FastAPI server with uvicorn...")
    print("📚 API documentation will be available at: http://localhost:8866/docs")
    print("🔄 Alternative docs at: http://localhost:8866/redoc")
    print("🔄 Auto-reload enabled - server will restart on Python file changes")

    uvicorn.run(
        "api.fastapi_server:app",
        host="0.0.0.0",
        port=8866,
        reload=True,
        log_level="info",  # Changed from debug to info for cleaner logs
        access_log=True,  # Enable access logs
        reload_dirs=["api", "bench_finder"],  # Watch these directories for changes
        reload_includes=["*.py"],  # Only watch Python files
        reload_excludes=["*.pyc", "__pycache__", "*.log"],  # Exclude compiled files
    )
