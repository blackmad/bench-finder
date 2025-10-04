"""
Pydantic schemas for API request and response validation.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict


class SearchBase(BaseModel):
    """Base schema for search operations."""
    query: str
    start_lat: float
    start_lng: float
    search_radius: int


class SearchCreate(SearchBase):
    """Schema for creating a new search."""
    pass


class SearchResponse(SearchBase):
    """Schema for search response."""
    id: int
    created_at: datetime
    completed_at: Optional[datetime] = None
    status: str = 'pending'
    
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
    tags: Dict[str, Any] = {}
    source: str = 'osm'  # 'osm' or 'mapillary'
    external_id: Optional[str] = None  # For Mapillary image IDs


class BenchCreate(BenchBase):
    """Schema for creating a new bench."""
    search_id: Optional[int] = None  # Nullable for Mapillary benches


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
    detections: List[Dict[str, Any]] = []
    detection_success: bool
    detection_error: Optional[str] = None
    model_id: str
    confidence_threshold: float
    source: str = 'roboflow'  # 'roboflow', 'ultralytics', 'mapillary'
    external_detection_id: Optional[str] = None  # For Mapillary detection IDs


class DetectionCreate(DetectionBase):
    """Schema for creating a new detection."""
    image_id: int


class DetectionResponse(DetectionBase):
    """Schema for detection response."""
    id: int
    image_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class UltralyticsDetectionBase(BaseModel):
    """Base schema for Ultralytics detection data."""
    has_bench: bool
    bench_count: int = 0
    max_confidence: float = 0.0
    full_response: Dict[str, Any] = {}
    bench_detections: List[Dict[str, Any]] = []
    detection_success: bool
    detection_error: Optional[str] = None
    model_url: Optional[str]= "unknown"
    confidence_threshold: float
    iou_threshold: float
    image_size: int
    inference_time: Optional[float] = None
    preprocess_time: Optional[float] = None
    postprocess_time: Optional[float] = None


class UltralyticsDetectionCreate(UltralyticsDetectionBase):
    """Schema for creating a new Ultralytics detection."""
    image_id: int


class UltralyticsDetectionResponse(UltralyticsDetectionBase):
    """Schema for Ultralytics detection response."""
    id: int
    image_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class BenchWithImages(BenchResponse):
    """Schema for bench with its images."""
    images: List[ImageResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


class ImageWithDetections(ImageResponse):
    """Schema for image with its detections."""
    detections: List[DetectionResponse] = []
    ultralytics_detections: List[UltralyticsDetectionResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


class BenchWithDetections(BenchResponse):
    """Schema for bench with all related data."""
    images: List[ImageWithDetections] = []
    
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
    tags: Dict[str, Any] = {}
    source: str  # 'osm' or 'mapillary'
    external_id: Optional[str] = None
    best_confidence: float
    roboflow_confidence: float = 0.0
    ultralytics_confidence: float = 0.0
    mapillary_confidence: float = 0.0
    detection_type: str
    has_segmentation: bool
    image_count: int
    image_filenames: List[str]
    image_ids: List[int]
    distance_meters: int
    distance_km: float


class PaginationInfo(BaseModel):
    """Schema for pagination metadata."""
    page: int
    page_size: int
    total_count: int
    total_pages: int
    has_next: bool


class BenchListResponse(BaseModel):
    """Schema for paginated bench list response."""
    benches: List[WebBenchData]
    pagination: PaginationInfo


class SegmentationData(BaseModel):
    """Schema for segmentation data response."""
    filename: str
    bench_detections: List[Dict[str, Any]]
    image_shape: Optional[List[int]] = None
    segmentation_available: bool


class ImageListResponse(BaseModel):
    """Schema for image list response."""
    images: List[ImageResponse]


class ConfigResponse(BaseModel):
    """Schema for configuration response."""
    default_start_lat: float
    default_start_lng: float
    default_min_confidence: float
    page_size: int


class SearchListResponse(BaseModel):
    """Schema for search list response."""
    searches: List[SearchSummary]


# Source-specific request schemas
class SourceSearchRequest(BaseModel):
    """Schema for source-specific search request."""
    center_lat: float
    center_lng: float
    radius_meters: int = 1000
    limit: int = 1000
    source: str  # 'osm', 'mapillary'


class SourceStatistics(BaseModel):
    """Schema for source-specific statistics."""
    source: str
    total_benches: int
    total_detections: int
    avg_detections_per_bench: float
    unique_locations: int
    coverage_area_km2: float
