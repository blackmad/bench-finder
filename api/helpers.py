"""Shared helper functions and models for FastAPI routes."""

import math
from datetime import UTC, datetime

from fastapi import HTTPException, status
from pydantic import BaseModel, Field

from bench_finder.models.enums import DataSource, DetectionSource
from bench_finder.models.unified_models import (
    BenchCandidate,
    Detection,
    DetectionItem,
    Image,
    ProcessedBench,
)
from bench_finder.services.database import BenchDatabase

from .api_models import (
    ApiDetectionItem,
    StructuredAddress,
    WebBenchData,
)
from .dependencies import (
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_START_LAT,
    DEFAULT_START_LNG,
    PAGE_SIZE,
)


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
    source: DataSource | None = Field(
        DataSource.OSM,
        description="Filter by data source (default: OSM, None for all sources)",
    )
    sort_by: str = Field(
        "distance",
        pattern="^(distance|confidence|images|recent)$",
        description="Sort criteria",
    )
    limit: int = Field(200, ge=1, le=500, description="Maximum number of results")


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

    # Safety check: ensure lists are the same length
    if len(image_filenames) != len(image_ids):
        # If lists are out of sync, return as-is to avoid index errors
        return image_filenames, image_ids

    # Find the index of the best image
    try:
        best_index = image_ids.index(best_image_id)
    except ValueError:
        # best_image_id not in the list, return as-is
        return image_filenames, image_ids

    # Bounds check: ensure best_index is valid for both lists
    if (
        best_index < 0
        or best_index >= len(image_filenames)
        or best_index >= len(image_ids)
    ):
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


def build_image_urls(images: list[Image], image_ids: list[int]) -> list[str]:
    """
    Build image URLs from Image objects, using firebase_url when available,
    otherwise falling back to /images/{filename} format.
    """
    # Create a map of image_id -> Image for quick lookup
    image_map = {img.id: img for img in images}

    urls = []
    for img_id in image_ids:
        img = image_map.get(img_id)
        if img and img.firebase_url:
            urls.append(img.firebase_url)
        elif img and img.filename:
            urls.append(f"/images/{img.filename}")
        else:
            urls.append("/images/unknown")
    return urls


def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great circle distance between two points using Haversine formula.
    Returns distance in meters.
    """
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])

    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    r = 6371000
    return c * r


def get_detection_items_for_bench(
    session, bench_candidate_id: int
) -> list[ApiDetectionItem]:
    """Get all detection items for a specific bench candidate using SQLAlchemy ORM."""

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
        bbox = None
        if item.bbox:
            if isinstance(item.bbox, dict):
                from bench_finder.models.unified_models import BoundingBox

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

        detection_item = ApiDetectionItem(
            detection_id=item.detection_id,
            confidence=item.confidence,
            bbox=bbox,
            class_name=item.class_name,
            polygon=polygon,
        )
        detection_items.append(detection_item)

    return detection_items


def _build_structured_address(result) -> "StructuredAddress | None":
    """Build StructuredAddress from query result with reverse geocode fields."""
    if not hasattr(result, "rg_formatted_address") or not result.rg_formatted_address:
        return None

    return StructuredAddress(
        formatted_address=result.rg_formatted_address,
        street_number=getattr(result, "rg_street_number", None),
        street_name=getattr(result, "rg_street_name", None),
        city=getattr(result, "rg_city", None),
        state=getattr(result, "rg_state", None),
        postal_code=getattr(result, "rg_postal_code", None),
        country=getattr(result, "rg_country", None),
    )


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
    db: BenchDatabase,
    include_detection_data: bool = False,
) -> WebBenchData:
    """
    Get a specific bench by ID with all its data using SQLAlchemy ORM.

    Uses ProcessedBench -> BenchCandidate -> Image -> Detection -> DetectionItem
    """
    try:
        with db.get_session() as session:
            from sqlalchemy.orm import joinedload

            processed_bench = (
                session.query(ProcessedBench)
                .options(
                    joinedload(ProcessedBench.bench_candidate).joinedload(
                        BenchCandidate.reverse_geocode
                    ),
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

            successful_images = (
                session.query(Image)
                .filter(
                    Image.bench_candidate_id == bench_candidate.id,
                    Image.capture_success,
                )
                .all()
            )

            image_count = len(successful_images)
            image_filenames = []
            image_ids = []
            for img in successful_images:
                if img.filename:
                    image_filenames.append(img.filename)
                    image_ids.append(img.id)

            best_image_id = processed_bench.best_image_id
            image_filenames, image_ids = sort_images_by_best(
                image_filenames, image_ids, best_image_id
            )

            best_confidence = 0.0
            roboflow_confidence = 0.0
            ultralytics_confidence = 0.0
            mapillary_confidence = 0.0
            detection_type = DetectionSource.NONE
            has_segmentation = False
            bench_found = processed_bench.detection_status == "detected"

            best_detection = processed_bench.best_detection
            if best_detection:
                best_confidence = best_detection.max_confidence
                detection_type = best_detection.source

                if best_detection.detection_items:
                    has_segmentation = any(
                        item.polygon is not None
                        for item in best_detection.detection_items
                    )

                if best_detection.source == DetectionSource.ROBOFLOW:
                    roboflow_confidence = best_detection.max_confidence
                elif best_detection.source == DetectionSource.ULTRALYTICS:
                    ultralytics_confidence = best_detection.max_confidence
                elif best_detection.source == DetectionSource.MAPILLARY:
                    mapillary_confidence = best_detection.max_confidence

            detection_items = None
            if include_detection_data:
                detection_items = get_detection_items_for_bench(
                    session, bench_candidate.id
                )

            best_bbox = None
            if best_detection and best_detection.detection_items:
                sorted_items = sorted(
                    best_detection.detection_items,
                    key=lambda item: item.confidence,
                    reverse=True,
                )
                if sorted_items:
                    best_item = sorted_items[0]
                    if best_item.bbox:
                        if isinstance(best_item.bbox, dict):
                            from bench_finder.models.unified_models import BoundingBox

                            best_bbox = BoundingBox(**best_item.bbox)
                        else:
                            best_bbox = best_item.bbox

            reverse_geocode = None
            if bench_candidate.reverse_geocode:
                rg = bench_candidate.reverse_geocode
                reverse_geocode = StructuredAddress(
                    formatted_address=rg.formatted_address,
                    street_number=rg.street_number,
                    street_name=rg.street_name,
                    city=rg.city,
                    state=rg.state,
                    postal_code=rg.postal_code,
                    country=rg.country,
                )

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
                best_bbox=best_bbox,
                distance_meters=0,
                distance_km=0.0,
                reverse_geocode=reverse_geocode,
                detection_items=detection_items,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get bench {bench_id}: {e!s}",
        ) from e
