"""
API-only SQLModel models for bench finder application.
These models are used for API requests/responses and don't have database tables.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from sqlmodel import Field, SQLModel

from bench_finder.models.enums import (
    BenchReportType,
    DataSource,
    DetectionSource,
    LocationMethod,
    SearchStatus,
)
from bench_finder.models.unified_models import (
    BenchBase,
    BenchCandidateBase,
    BoundingBox,
    DetectionBase,
    DetectionItem,
    ImageBase,
    Polygon,
    SearchBase,
)


# ============================================================================
# Enums
# ============================================================================


class BenchMode(str, Enum):
    """Enum for bench search modes."""

    BENCHES = "benches"  # Only return candidates with detected benches
    NO_BENCH = "no_bench"  # Only return candidates without detected benches
    BOTH = "both"  # Return both types of candidates


# ============================================================================
# Base Models for API Requests/Responses
# ============================================================================


# API-specific DetectionItem that allows optional bbox (unlike the database model)
class ApiDetectionItem(SQLModel):
    """API-specific detection item with optional bbox for responses."""

    detection_id: int
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score between 0 and 1"
    )
    bbox: BoundingBox | None = Field(default=None, description="Optional bounding box")
    class_name: str = Field(
        default="bench", description="Class name of the detected object"
    )
    polygon: Polygon | None = Field(
        default=None, description="Optional polygon for segmentation"
    )


# SearchBase now imported from unified_models


class SearchResponse(SearchBase):
    """Schema for search response."""

    id: int
    created_at: datetime
    completed_at: datetime | None = None
    status: SearchStatus = SearchStatus.PENDING


class SearchSummary(SQLModel):
    """Schema for search summary with statistics."""

    id: int
    query: str
    start_lat: float
    start_lng: float
    search_radius: int
    bench_count: int
    created_at: datetime


# BenchBase now imported from unified_models


class BenchResponseModel(BenchBase):
    """Schema for bench response."""

    id: int
    search_id: int | None = None
    created_at: datetime


# ImageBase now imported from unified_models


class ImageResponse(ImageBase):
    """Schema for image response."""

    id: int
    bench_id: int
    created_at: datetime


# DetectionBase now imported from unified_models


class DetectionResponse(DetectionBase):
    """Schema for detection response."""

    id: int
    image_id: int | None = None
    created_at: datetime
    detection_items: list[DetectionItem] = Field(
        default_factory=list, description="List of detection items"
    )


# ============================================================================
# Composite Response Models
# ============================================================================


class ImageWithDetections(ImageResponse):
    """Schema for image with its detections."""

    detections: list[DetectionResponse]


class BenchWithDetections(BenchResponseModel):
    """Schema for bench with all related data."""

    images: list[ImageWithDetections]


class SearchResults(SQLModel):
    """Schema for comprehensive search results."""

    search: SearchResponse
    bench_count: int
    total_images: int
    successful_images: int
    total_detections: int
    images_with_benches: int
    best_confidence: float = 0.0


# ============================================================================
# Web UI Models
# ============================================================================


class StructuredAddress(SQLModel):
    """Schema for structured address components."""

    formatted_address: str
    street_number: str | None = None
    street_name: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None


class WebBenchData(SQLModel):
    """Schema for web UI bench data."""

    id: int
    provider_id: str | None = None  # Unified ID from OSM or Mapillary
    lat: float
    lng: float
    tags: dict[str, Any] = {}
    source: DataSource  # Currently only 'osm'
    external_id: str | None = None
    bench_found: bool = True  # Whether a bench was actually detected
    best_confidence: float
    roboflow_confidence: float = 0.0
    ultralytics_confidence: float = 0.0
    detection_type: DetectionSource
    has_segmentation: bool
    image_count: int
    image_filenames: list[str]
    image_ids: list[int]
    image_urls: list[str] | None = Field(
        default=None,
        description="Full URLs to images (Firebase Hosting URLs when available, otherwise /images/{filename} format)",
    )
    best_image_id: int | None = None  # ID of the best image used for detection
    best_detection_id: int | None = None  # ID of the best detection
    best_bbox: BoundingBox | None = Field(
        default=None, description="Bounding box of the best detection item"
    )
    distance_meters: int
    distance_km: float
    reverse_geocode: StructuredAddress | None = (
        None  # Structured address from reverse geocodingg
    )
    # Optional detection data (only included when requested)
    detection_items: list[ApiDetectionItem] | None = None


# ============================================================================
# Pagination and List Models
# ============================================================================


class PaginationInfo(SQLModel):
    """Schema for pagination metadata."""

    page: int
    page_size: int
    total_count: int
    total_pages: int
    has_next: bool


class BenchListResponse(SQLModel):
    """Schema for paginated bench list response."""

    benches: list[WebBenchData]
    pagination: PaginationInfo


class ImageListResponse(SQLModel):
    """Schema for image list response."""

    images: list[ImageResponse]


class SearchListResponse(SQLModel):
    """Schema for search list response."""

    searches: list[SearchSummary]


# ============================================================================
# Specialized API Models
# ============================================================================


class SegmentationData(SQLModel):
    """Schema for detection visualization data response (both segmentation and bounding boxes)."""

    filename: str
    detection_type: str  # 'segmentation' or 'bounding_box' or 'both'

    # Detection items with proper bbox and polygon data
    detection_items: list[ApiDetectionItem] = Field(
        default_factory=list,
        description="List of detection items with bbox and polygon data",
    )
    image_shape: list[int] | None = None
    segmentation_available: bool = False
    bounding_box_available: bool = False

    # Common metadata
    confidence_score: float = 0.0
    source: DetectionSource = DetectionSource.ROBOFLOW  # 'roboflow', 'ultralytics'


class ImageWithDetectionData(SQLModel):
    """Schema for image data with detection items."""

    image_id: int
    filename: str
    heading: float
    capture_success: bool
    detection_items: list[ApiDetectionItem] = Field(
        default_factory=list,
        description="List of detection items for this image",
    )


class BenchDetectionData(SQLModel):
    """Schema for comprehensive bench detection data including all images and detections."""

    bench_id: int
    bench_lat: float
    bench_lng: float
    total_images: int
    images_with_detections: int
    best_confidence: float
    detection_sources: list[DetectionSource]

    # Images with their detection data
    images: list[ImageWithDetectionData] = Field(
        default_factory=list,
        description="List of images with their detection items",
    )


class ConfigResponse(SQLModel):
    """Schema for configuration response."""

    default_start_lat: float
    default_start_lng: float
    default_min_confidence: float
    page_size: int


# ============================================================================
# Source-specific Models
# ============================================================================


# Source-specific models removed - using unified approach


# ============================================================================
# Detection and Processing Models
# ============================================================================


class ModelCacheInfo(SQLModel):
    """Schema for model cache information."""

    cached_models: list[str]
    cache_size: int


# ============================================================================
# Processing and Pipeline Models
# ============================================================================


class CacheStatus(SQLModel):
    """Schema for cache status information."""

    use_local_inference: bool
    model_id: str | None
    model_cached: bool
    cache_key: str | None
    total_cached_models: int
    all_cached_models: list[str]


class BenchProcessingResult(SQLModel):
    """Schema for bench processing results."""

    bench_added: bool
    images_captured: int
    images_successful: int
    detections_performed: int
    bench_detected: bool
    best_confidence: float


class ProcessingStats(SQLModel):
    """Schema for overall processing statistics."""

    benches_processed: int
    benches_added: int
    images_captured: int
    images_successful: int
    detections_performed: int
    benches_detected: int
    best_confidence: float


class PipelineResult(SQLModel):
    """Schema for pipeline execution results."""

    success: bool
    search_id: int | None = None
    message: str
    stats: ProcessingStats | None = None
    error: str | None = None


# ============================================================================
# API Response Models
# ============================================================================


class HealthResponse(SQLModel):
    """Schema for health check response."""

    status: str
    database: str


class ApiInfoResponse(SQLModel):
    """Schema for API information response."""

    name: str
    version: str
    description: str
    supported_sources: list[DataSource]
    supported_detection_models: list[DetectionSource]
    features: list[str]
    endpoints: dict[str, str]
    limits: dict[str, Any]


# MapillaryConfigResponse removed - using unified approach


class ReportResponse(SQLModel):
    """Schema for bench report response."""

    success: bool
    report_id: int
    message: str
    bench_id: int
    report_type: BenchReportType
    created_at: datetime


class MissingBenchReportResponse(SQLModel):
    """Schema for missing bench report response."""

    success: bool
    report_id: int
    message: str
    location: dict[str, float]
    location_method: LocationMethod
    has_image: bool
    created_at: datetime


class ErrorResponse(SQLModel):
    """Schema for error response."""

    error: str
    detail: str | None = None


# ============================================================================
# Bench Candidate Models
# ============================================================================


# BenchCandidateBase now imported from unified_models


class BenchCandidateResponse(BenchCandidateBase):
    """Schema for bench candidate response."""

    id: int
    search_id: int
    created_at: datetime


class BenchCandidateListResponse(SQLModel):
    """Schema for list of bench candidates response."""

    candidates: list[BenchCandidateResponse]
    total_count: int
    search_id: int
    search_query: str


# ============================================================================
# User Interaction Models
# ============================================================================


class RatingRequest(SQLModel):
    """Schema for rating a bench."""

    rating: int = Field(ge=1, le=5, description="Rating from 1 to 5")


class RatingResponse(SQLModel):
    """Schema for rating response."""

    id: int
    bench_candidate_id: int
    user_id: str
    rating: int
    created_at: datetime
    updated_at: datetime


class BenchUserStatusRequest(SQLModel):
    """Schema for setting bench user status."""

    status: str = Field(description="Status: 'been', 'want_to_go', or 'favorite'")


class BenchUserStatusResponse(SQLModel):
    """Schema for bench user status response."""

    id: int
    bench_candidate_id: int
    user_id: str
    status: str
    created_at: datetime
    updated_at: datetime


class CommentRequest(SQLModel):
    """Schema for adding a comment."""

    comment: str = Field(min_length=1, max_length=5000, description="Comment text")


class CommentResponse(SQLModel):
    """Schema for comment response."""

    id: int
    bench_candidate_id: int
    user_id: str
    comment: str
    created_at: datetime
    updated_at: datetime


class BenchUserDataResponse(SQLModel):
    """Schema for bench user data (ratings, status, comments)."""

    bench_candidate_id: int
    user_rating: RatingResponse | None = None
    user_statuses: list[BenchUserStatusResponse] = []
    user_comments: list[CommentResponse] = []
    average_rating: float | None = None
    total_ratings: int = 0
    total_comments: int = 0
