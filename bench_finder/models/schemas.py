"""
Pydantic schemas for API request and response validation.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .detection_models import DetectionItem
from .enums import (
    BenchReportType,
    DataSource,
    DetectionSource,
    LocationMethod,
    SearchStatus,
)


class SearchBase(BaseModel):
    """Base schema for search operations."""

    query: str
    start_lat: float
    start_lng: float
    search_radius: int


class SearchCreate(SearchBase):
    """Schema for creating a new search."""


class SearchResponse(SearchBase):
    """Schema for search response."""

    id: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    status: SearchStatus = SearchStatus.PENDING

    model_config = ConfigDict(from_attributes=True)


class SearchSummary(BaseModel):
    """Schema for search summary with statistics."""

    id: int
    query: str
    start_lat: float
    start_lng: float
    search_radius: int
    bench_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BenchBase(BaseModel):
    """Base schema for bench data."""

    provider_id: Optional[str] = None  # Unified ID from OSM or Mapillary
    lat: float
    lng: float
    tags: dict[str, Any] = {}
    source: DataSource = DataSource.OSM  # 'osm' or 'mapillary'
    external_id: Optional[str] = None  # For Mapillary image IDs


class BenchCreate(BenchBase):
    """Schema for creating a new bench."""

    search_id: Optional[int] = None  # Nullable for Mapillary benches
    representative_image_id: Optional[int] = (
        None  # ID of the representative image for this bench
    )


class BenchResponse(BenchBase):
    """Schema for bench response."""

    id: int
    search_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImageBase(BaseModel):
    """Base schema for image data."""

    heading: int
    filepath: Optional[str] = None
    filename: Optional[str] = None
    file_size: Optional[int] = None
    capture_success: bool
    capture_error: Optional[str] = None


class ImageCreate(ImageBase):
    """Schema for creating a new image."""

    bench_id: int


class ImageResponse(ImageBase):
    """Schema for image response."""

    id: int
    bench_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DetectionBase(BaseModel):
    """Base schema for detection data."""

    has_bench: bool
    bench_count: int = 0
    max_confidence: float = 0.0
    detections: list[DetectionItem] = []
    detection_success: bool
    detection_error: Optional[str] = None
    model_id: str
    confidence_threshold: float
    source: DetectionSource = (
        DetectionSource.ROBOFLOW
    )  # 'roboflow', 'ultralytics', 'mapillary'
    external_detection_id: Optional[str] = None  # For Mapillary detection IDs

    # Ultralytics-specific fields (optional for backward compatibility)
    full_response: Optional[dict[str, Any]] = None
    bench_detections: Optional[list[dict[str, Any]]] = None
    model_url: Optional[str] = None
    iou_threshold: Optional[float] = None
    image_size: Optional[int] = None
    inference_time: Optional[float] = None
    preprocess_time: Optional[float] = None
    postprocess_time: Optional[float] = None


class DetectionCreate(DetectionBase):
    """Schema for creating a new detection."""

    image_id: int


class DetectionResponse(DetectionBase):
    """Schema for detection response."""

    id: int
    image_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BenchWithImages(BenchResponse):
    """Schema for bench with its images."""

    images: list[ImageResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ImageWithDetections(ImageResponse):
    """Schema for image with its detections."""

    detections: list[DetectionResponse] = []

    model_config = ConfigDict(from_attributes=True)


class BenchWithDetections(BenchResponse):
    """Schema for bench with all related data."""

    images: list[ImageWithDetections] = []

    model_config = ConfigDict(from_attributes=True)


class SearchResults(BaseModel):
    """Schema for comprehensive search results."""

    search: SearchResponse
    bench_count: int
    total_images: int
    successful_images: int
    total_detections: int
    images_with_benches: int
    best_confidence: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class WebBenchData(BaseModel):
    """Schema for web UI bench data."""

    id: int
    provider_id: Optional[str] = None  # Unified ID from OSM or Mapillary
    lat: float
    lng: float
    tags: dict[str, Any] = {}
    source: DataSource  # 'osm' or 'mapillary'
    external_id: Optional[str] = None
    best_confidence: float
    roboflow_confidence: float = 0.0
    ultralytics_confidence: float = 0.0
    mapillary_confidence: float = 0.0
    detection_type: DetectionSource
    has_segmentation: bool
    image_count: int
    image_filenames: list[str]
    image_ids: list[int]
    distance_meters: int
    distance_km: float
    # Clustering information (optional, only present when serving clustered data)
    cluster_id: Optional[int] = None
    cluster_center_lat: Optional[float] = None
    cluster_center_lng: Optional[float] = None
    cluster_bench_count: Optional[int] = None
    cluster_max_distance_meters: Optional[float] = None
    is_cluster_representative: Optional[bool] = None


class ClusterInfo(BaseModel):
    """Schema for cluster metadata."""

    cluster_id: int
    center_lat: float
    center_lng: float
    bench_count: int
    max_distance_meters: float
    avg_confidence: float
    sources: list[DataSource]  # List of data sources in cluster
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ClusteredBenchData(BaseModel):
    """Schema for clustered bench data showing both cluster and individual bench info."""

    cluster: ClusterInfo
    representative_bench: WebBenchData  # The "best" bench in the cluster
    all_benches: list[WebBenchData]  # All benches in the cluster
    distance_to_cluster_center: float  # Distance from query point to cluster center


class PaginationInfo(BaseModel):
    """Schema for pagination metadata."""

    page: int
    page_size: int
    total_count: int
    total_pages: int
    has_next: bool


class BenchListResponse(BaseModel):
    """Schema for paginated bench list response."""

    benches: list[WebBenchData]
    pagination: PaginationInfo


class ClusteredBenchListResponse(BaseModel):
    """Schema for paginated clustered bench list response."""

    clustered_benches: list[ClusteredBenchData]
    pagination: PaginationInfo
    clustering_info: dict[str, Any] = {}  # Metadata about clustering configuration


class SegmentationData(BaseModel):
    """Schema for detection visualization data response (both segmentation and bounding boxes)."""

    filename: str
    detection_type: str  # 'segmentation' or 'bounding_box' or 'both'

    # Ultralytics segmentation data
    bench_detections: list[dict[str, Any]] = []  # Segmentation polygons
    image_shape: Optional[list[int]] = None
    segmentation_available: bool = False

    # Roboflow bounding box data
    roboflow_detections: list[dict[str, Any]] = []  # Bounding box coordinates
    bounding_box_available: bool = False

    # Common metadata
    confidence_score: float = 0.0
    source: DetectionSource = DetectionSource.ROBOFLOW  # 'roboflow', 'ultralytics'


class ImageListResponse(BaseModel):
    """Schema for image list response."""

    images: list[ImageResponse]


class ConfigResponse(BaseModel):
    """Schema for configuration response."""

    default_start_lat: float
    default_start_lng: float
    default_min_confidence: float
    page_size: int


class SearchListResponse(BaseModel):
    """Schema for search list response."""

    searches: list[SearchSummary]


# Source-specific request schemas
class SourceSearchRequest(BaseModel):
    """Schema for source-specific search request."""

    center_lat: float
    center_lng: float
    radius_meters: int = 1000
    limit: int = 1000
    source: DataSource  # 'osm', 'mapillary'


class SourceStatistics(BaseModel):
    """Schema for source-specific statistics."""

    source: DataSource
    total_benches: int
    total_detections: int
    avg_detections_per_bench: float
    unique_locations: int
    coverage_area_km2: float


# New models for type-safe dictionary replacements
class ModelCacheInfo(BaseModel):
    """Schema for model cache information."""

    cached_models: list[str]
    cache_size: int


class RoboflowDetectionResult(BaseModel):
    """Schema for Roboflow detection results."""

    image_path: str
    success: bool
    has_bench: bool
    bench_count: int
    max_confidence: float
    detections: list[dict[str, Any]]
    raw_predictions: int
    model_id: str
    confidence_threshold: float
    inference_type: Optional[str] = None
    error: Optional[str] = None


class RoboflowModelInfo(BaseModel):
    """Schema for Roboflow model information."""

    model_id: str
    confidence_threshold: float
    classes: list[str]


# BoundingBox and DetectionItem are now imported from detection_models


class StandardDetectionResult(BaseModel):
    """Standardized detection result from any backend."""

    image_path: str
    success: bool
    has_bench: bool
    bench_count: int
    max_confidence: float
    detections: list[DetectionItem]

    # Backend information
    winning_backend: str  # 'ultralytics', 'roboflow', 'none'
    winning_model: str
    fallback_used: bool = False
    total_attempts: int = 1

    # Error information
    error: Optional[str] = None

    # Additional metadata
    detection_attempts: list[dict[str, Any]] = []


# Ultralytics-specific models
class UltralyticsBox(BaseModel):
    """Ultralytics bounding box in xyxy format."""

    x1: float
    y1: float
    x2: float
    y2: float


class UltralyticsSegments(BaseModel):
    """Ultralytics segmentation data."""

    x: list[float]
    y: list[float]


class UltralyticsDetectionItem(BaseModel):
    """Single detection item from Ultralytics."""

    class_name: str = Field(alias="class")
    class_id: int
    confidence: float
    box: UltralyticsBox
    segments: Optional[UltralyticsSegments] = None

    model_config = ConfigDict(populate_by_name=True)


class UltralyticsSpeed(BaseModel):
    """Timing information from Ultralytics."""

    inference: Optional[float] = None
    preprocess: Optional[float] = None
    postprocess: Optional[float] = None


class UltralyticsImageResult(BaseModel):
    """Results for a single image from Ultralytics API."""

    results: list[UltralyticsDetectionItem] = []
    shape: list[int] = []
    speed: Optional[UltralyticsSpeed] = None


class UltralyticsApiResponse(BaseModel):
    """Complete Ultralytics API response."""

    images: list[UltralyticsImageResult] = []


class UltralyticsDetectionResult(BaseModel):
    """Processed Ultralytics detection result."""

    image_path: str
    success: bool
    has_bench: bool
    bench_count: int
    max_confidence: float
    bench_detections: list[UltralyticsDetectionItem]
    full_response: UltralyticsApiResponse
    model_url: str
    confidence_threshold: float
    iou_threshold: float
    image_size: int
    inference_mode: str  # 'local' or 'api'

    # Timing information
    inference_time: Optional[float] = None
    preprocess_time: Optional[float] = None
    postprocess_time: Optional[float] = None

    # Error information
    error: Optional[str] = None


class CacheStatus(BaseModel):
    """Schema for cache status information."""

    use_local_inference: bool
    model_id: str | None
    model_cached: bool
    cache_key: Optional[str]
    total_cached_models: int
    all_cached_models: list[str]


class BenchProcessingResult(BaseModel):
    """Schema for bench processing results."""

    bench_added: bool
    images_captured: int
    images_successful: int
    detections_performed: int
    bench_detected: bool
    best_confidence: float


class ProcessingStats(BaseModel):
    """Schema for overall processing statistics."""

    benches_processed: int
    benches_added: int
    images_captured: int
    images_successful: int
    detections_performed: int
    benches_detected: int
    best_confidence: float


class PipelineResult(BaseModel):
    """Schema for pipeline execution results."""

    success: bool
    search_id: Optional[int] = None
    message: str
    stats: Optional[ProcessingStats] = None
    error: Optional[str] = None


# Additional response models for FastAPI endpoints
class HealthResponse(BaseModel):
    """Schema for health check response."""

    status: str
    database: str
    mapillary: str


class ApiInfoResponse(BaseModel):
    """Schema for API information response."""

    name: str
    version: str
    description: str
    supported_sources: list[DataSource]
    supported_detection_models: list[DetectionSource]
    features: list[str]
    endpoints: dict[str, str]
    limits: dict[str, Any]


class MapillaryConfigResponse(BaseModel):
    """Schema for Mapillary configuration response."""

    mapillary_enabled: bool
    default_radius_meters: int
    default_limit: int
    supported_detection_types: list[DetectionSource]
    max_radius_meters: int
    max_limit: int
    features: dict[str, Any]


class ReportResponse(BaseModel):
    """Schema for bench report response."""

    success: bool
    report_id: int
    message: str
    bench_id: int
    report_type: BenchReportType
    created_at: str


class MissingBenchReportResponse(BaseModel):
    """Schema for missing bench report response."""

    success: bool
    report_id: int
    message: str
    location: dict[str, float]
    location_method: LocationMethod
    has_image: bool
    created_at: str


class SourceStatsResponse(BaseModel):
    """Schema for source statistics response."""

    source: DataSource
    total_benches: int
    total_images: int
    total_detections: int
    avg_confidence: float
    area_filtered: bool
    area_center: Optional[dict[str, float]] = None
    area_radius_meters: Optional[int] = None


class ErrorResponse(BaseModel):
    """Schema for error response."""

    error: str
    detail: Optional[str] = None


class BenchCandidateBase(BaseModel):
    """Base schema for bench candidate data."""

    provider_id: Optional[str] = None
    lat: float
    lng: float
    tags: Optional[dict[str, Any]] = None
    source: DataSource = DataSource.OSM
    external_id: Optional[str] = None
    confidence: Optional[float] = None


class BenchCandidateCreate(BenchCandidateBase):
    """Schema for creating a bench candidate."""

    search_id: int


class BenchCandidateResponse(BenchCandidateBase):
    """Schema for bench candidate response."""

    id: int
    search_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BenchCandidateListResponse(BaseModel):
    """Schema for list of bench candidates response."""

    candidates: list[BenchCandidateResponse]
    total_count: int
    search_id: int
    search_query: str
