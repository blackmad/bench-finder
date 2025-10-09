"""
Enhanced Pydantic schemas specifically designed for FastAPI with comprehensive OpenAPI documentation.
These extend the existing schemas.py with FastAPI-specific models and improved documentation.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, validator

# Import existing models from schemas.py
from bench_finder.models.schemas import ConfigResponse, SearchSummary, WebBenchData


class SortByEnum(str, Enum):
    """Enumeration of valid sort criteria."""

    distance = "distance"
    confidence = "confidence"
    images = "images"
    recent = "recent"


class SourceEnum(str, Enum):
    """Enumeration of valid data sources."""

    osm = "osm"
    mapillary = "mapillary"


class DetectionTypeEnum(str, Enum):
    """Enumeration of detection visualization types."""

    segmentation = "segmentation"
    bounding_box = "bounding_box"
    both = "both"


# Query parameter models for FastAPI
class BenchListQuery(BaseModel):
    """Query parameters for bench listing endpoints with comprehensive validation."""

    page: int = Field(
        default=0,
        ge=0,
        le=1000,
        description="Page number (0-based). Maximum 1000 pages.",
        example=0,
    )

    page_size: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Items per page. Limited to 50 for performance.",
        example=20,
    )

    min_confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence score (0.0 - 1.0)",
        example=0.8,
    )

    start_lat: float = Field(
        default=52.3613577,
        ge=-90.0,
        le=90.0,
        description="Starting latitude for distance calculations",
        example=52.3613577,
    )

    start_lng: float = Field(
        default=4.8666322,
        ge=-180.0,
        le=180.0,
        description="Starting longitude for distance calculations",
        example=4.8666322,
    )

    sort_by: SortByEnum = Field(
        default=SortByEnum.distance,
        description="Sort criteria: distance from start point, detection confidence, image count, or most recent",
        example="distance",
    )

    source: Optional[SourceEnum] = Field(
        default=None,
        description="Filter by data source (osm or mapillary)",
        example=None,
    )


class BboxQuery(BaseModel):
    """Query parameters for bounding box searches with geographic validation."""

    north: float = Field(
        ..., ge=-90.0, le=90.0, description="Northern latitude boundary", example=52.4
    )

    south: float = Field(
        ..., ge=-90.0, le=90.0, description="Southern latitude boundary", example=52.3
    )

    east: float = Field(
        ..., ge=-180.0, le=180.0, description="Eastern longitude boundary", example=4.9
    )

    west: float = Field(
        ..., ge=-180.0, le=180.0, description="Western longitude boundary", example=4.8
    )

    min_confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence score",
        example=0.8,
    )

    source: Optional[SourceEnum] = Field(
        default=None, description="Filter by data source", example=None
    )

    sort_by: SortByEnum = Field(
        default=SortByEnum.distance, description="Sort criteria", example="distance"
    )

    limit: int = Field(
        default=200,
        ge=1,
        le=500,
        description="Maximum number of results to return",
        example=200,
    )

    @validator("north")
    def north_must_be_greater_than_south(cls, v, values):
        if "south" in values and v <= values["south"]:
            raise ValueError("North boundary must be greater than south boundary")
        return v

    @validator("east")
    def east_must_be_greater_than_west(cls, v, values):
        if "west" in values and v <= values["west"]:
            raise ValueError("East boundary must be greater than west boundary")
        return v


class RandomBenchQuery(BaseModel):
    """Query parameters for random bench selection."""

    min_confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence score",
        example=0.8,
    )

    source: Optional[SourceEnum] = Field(
        default=None, description="Filter by data source", example=None
    )


class StatisticsQuery(BaseModel):
    """Query parameters for statistics endpoints."""

    center_lat: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="Center latitude for area-specific statistics",
        example=52.3613577,
    )

    center_lng: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="Center longitude for area-specific statistics",
        example=4.8666322,
    )

    radius_meters: Optional[int] = Field(
        default=None,
        ge=100,
        le=50000,
        description="Radius in meters for area-specific statistics",
        example=1000,
    )


# Request models
class MapillarySearchRequest(BaseModel):
    """Request model for Mapillary bench search operations."""

    center_lat: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="Search center latitude coordinate",
        example=52.3613577,
    )

    center_lng: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Search center longitude coordinate",
        example=4.8666322,
    )

    radius_meters: int = Field(
        default=1000,
        ge=10,
        le=10000,
        description="Search radius in meters (10m - 10km)",
        example=1000,
    )

    limit: int = Field(
        default=1000,
        ge=1,
        le=5000,
        description="Maximum number of results to fetch from Mapillary API",
        example=1000,
    )


# Response models
class BboxBenchResponse(BaseModel):
    """Response model for bounding box bench queries with geographic metadata."""

    benches: list[WebBenchData] = Field(
        ..., description="List of benches found within the bounding box"
    )

    total_count: int = Field(
        ...,
        ge=0,
        description="Total number of benches returned (may be limited by query limit)",
    )

    bbox: dict[str, float] = Field(
        ...,
        description="The requested bounding box coordinates",
        example={"north": 52.4, "south": 52.3, "east": 4.9, "west": 4.8},
    )

    query_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional query metadata and performance information",
    )


class RandomBenchResponse(BaseModel):
    """Response model for random bench selection."""

    bench: WebBenchData = Field(
        ..., description="Randomly selected bench matching the specified criteria"
    )

    selection_info: dict[str, Any] = Field(
        default_factory=dict,
        description="Information about the random selection process",
    )


class EnhancedErrorResponse(BaseModel):
    """Enhanced error response with detailed debugging information."""

    error: str = Field(..., description="Human-readable error message")

    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code for programmatic handling",
    )

    detail: Optional[str] = Field(
        default=None, description="Additional error details and context"
    )

    suggestions: Optional[list[str]] = Field(
        default=None, description="Suggested actions to resolve the error"
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When the error occurred"
    )


class HealthCheckResponse(BaseModel):
    """Health check response with system status information."""

    status: str = Field(
        ..., description="Overall system health status", example="healthy"
    )

    database: str = Field(
        ..., description="Database connection status", example="connected"
    )

    mapillary: str = Field(
        ..., description="Mapillary integration status", example="enabled"
    )

    version: str = Field(default="2.0.0", description="API version")

    uptime_seconds: Optional[float] = Field(
        default=None, description="Server uptime in seconds"
    )

    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Health check timestamp"
    )


class APIInfoResponse(BaseModel):
    """API information and capabilities response."""

    name: str = Field(default="Bench Finder API", description="API name")

    version: str = Field(default="2.0.0", description="API version")

    description: str = Field(
        default="A comprehensive API for discovering and analyzing public benches using computer vision",
        description="API description",
    )

    supported_sources: list[str] = Field(
        default=["osm", "mapillary"], description="Supported data sources"
    )

    supported_detection_models: list[str] = Field(
        default=["roboflow", "ultralytics", "mapillary"],
        description="Supported detection models",
    )

    features: list[str] = Field(
        default=[
            "spatial_search",
            "confidence_filtering",
            "multi_source_data",
            "image_analysis",
            "detection_visualization",
            "statistics_analytics",
        ],
        description="Available API features",
    )

    limits: dict[str, int] = Field(
        default={
            "max_page_size": 50,
            "max_bbox_results": 500,
            "max_search_radius": 10000,
            "max_mapillary_limit": 5000,
        },
        description="API usage limits",
    )


# Enhanced versions of existing models with better OpenAPI documentation
class EnhancedSearchSummary(SearchSummary):
    """Enhanced search summary with additional metadata for FastAPI."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "query": "bench",
                "start_lat": 52.3613577,
                "start_lng": 4.8666322,
                "search_radius": 1000,
                "bench_count": 42,
                "created_at": "2023-10-01T10:30:00Z",
            }
        },
    )


class EnhancedWebBenchData(WebBenchData):
    """Enhanced bench data model with additional FastAPI metadata."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 123,
                "provider_id": "osm_456789",
                "lat": 52.3613577,
                "lng": 4.8666322,
                "tags": {"amenity": "bench", "material": "wood"},
                "source": "osm",
                "external_id": None,
                "best_confidence": 0.95,
                "roboflow_confidence": 0.92,
                "ultralytics_confidence": 0.95,
                "mapillary_confidence": 0.0,
                "detection_type": "ultralytics",
                "has_segmentation": True,
                "image_count": 4,
                "image_filenames": ["bench_123_0.jpg", "bench_123_90.jpg"],
                "image_ids": [1001, 1002],
                "distance_meters": 150,
                "distance_km": 0.15,
            }
        },
    )


class EnhancedConfigResponse(ConfigResponse):
    """Enhanced configuration response with FastAPI metadata."""

    api_version: str = Field(default="2.0.0", description="Current API version")

    documentation_url: str = Field(
        default="/docs", description="URL for interactive API documentation"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "default_start_lat": 52.3613577,
                "default_start_lng": 4.8666322,
                "default_min_confidence": 0.8,
                "page_size": 20,
                "api_version": "2.0.0",
                "documentation_url": "/docs",
            }
        }
    )
