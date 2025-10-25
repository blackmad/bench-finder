"""
Unified SQLModel models for bench finder application.
This file combines database models, detection models, and API schemas using SQLModel.
"""

import json
from datetime import datetime
from typing import Any, Optional

from pydantic_core import to_jsonable_python
from sqlalchemy import JSON
from sqlmodel import Column, Field, Relationship, Session, SQLModel, create_engine

from .enums import (
    BenchCandidateStatus,
    BenchReportStatus,
    BenchReportType,
    DataSource,
    DetectionSource,
    LocationMethod,
    MissingBenchReportStatus,
    SearchStatus,
)


# ============================================================================
# Base Models and Core Detection Models (Non-database)
# ============================================================================


class Polygon(SQLModel):
    """Represents a polygon as a list of coordinate pairs."""

    coordinates: list[list[float]] = Field(
        description="List of [x, y] coordinate pairs forming the polygon"
    )


class BoundingBox(SQLModel):
    """Standardized bounding box format with computed properties."""

    x1: float = Field(description="Left coordinate")
    y1: float = Field(description="Top coordinate")
    x2: float = Field(description="Right coordinate")
    y2: float = Field(description="Bottom coordinate")

    @property
    def width(self) -> float:
        """Computed width of the bounding box."""
        return abs(self.x2 - self.x1)

    @property
    def height(self) -> float:
        """Computed height of the bounding box."""
        return abs(self.y2 - self.y1)

    @property
    def center_x(self) -> float:
        """Center X coordinate."""
        return (self.x1 + self.x2) / 2

    @property
    def center_y(self) -> float:
        """Center Y coordinate."""
        return (self.y1 + self.y2) / 2

    @property
    def area(self) -> float:
        """Area of the bounding box."""
        return self.width * self.height

    def __init__(self, **data):
        """Auto-calculate width and height if not provided."""
        # Auto-calculate width and height if not provided
        if "width" not in data and "x1" in data and "x2" in data:
            data["width"] = abs(data["x2"] - data["x1"])
        if "height" not in data and "y1" in data and "y2" in data:
            data["height"] = abs(data["y2"] - data["y1"])
        super().__init__(**data)


class DetectionItem(SQLModel, table=True):
    """Single detection item with mandatory bbox and optional polygon/segmentation."""

    __tablename__ = "detection_items"

    id: int | None = Field(default=None, primary_key=True)
    detection_id: int = Field(foreign_key="detections.id", nullable=False)
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score between 0 and 1"
    )
    bbox: BoundingBox = Field(
        description="Mandatory bounding box", sa_column=Column(JSON)
    )
    class_name: str = Field(
        default="bench", description="Class name of the detected object"
    )
    # Support both polygon and segmentation for backward compatibility
    polygon: Polygon | None = Field(
        default=None,
        description="Optional polygon for segmentation",
        sa_column=Column(JSON),
    )
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    detection: "Detection" = Relationship(back_populates="detection_items")


class DetectionResult(SQLModel):
    """Unified detection result from any backend."""

    image_path: str = Field(description="Path to the analyzed image")
    success: bool = Field(description="Whether the detection was successful")
    has_bench: bool = Field(description="Whether any benches were detected")
    bench_count: int = Field(ge=0, description="Number of benches detected")
    max_confidence: float = Field(
        ge=0.0, le=1.0, description="Highest confidence score among all detections"
    )
    detections: list[DetectionItem] = Field(
        default_factory=list, description="List of all detections"
    )

    # Backend information
    backend_name: str = Field(description="Name of the detection backend used")
    model_id: str = Field(description="ID of the model used")
    confidence_threshold: float = Field(
        ge=0.0, le=1.0, description="Confidence threshold used"
    )

    # Error information
    error: str | None = Field(
        default=None, description="Error message if detection failed"
    )

    # Additional metadata
    inference_time: float | None = Field(
        default=None, description="Time taken for inference in seconds"
    )
    preprocess_time: float | None = Field(
        default=None, description="Time taken for preprocessing in seconds"
    )
    postprocess_time: float | None = Field(
        default=None, description="Time taken for postprocessing in seconds"
    )

    # Source information
    source: DetectionSource = Field(
        default=DetectionSource.ROBOFLOW,
        description="Source of the detection (roboflow, ultralytics, mapillary)",
    )

    # Ultralytics-specific fields (optional)
    # full_response: Optional[Dict[str, Any]] = Field(
    #     default=None, description="Full response from Ultralytics API"
    # )
    # bench_detections: Optional[list[dict]] = Field(
    #     default=None, description="Bench-specific detections from Ultralytics"
    # )
    model_url: str | None = Field(default=None, description="URL of the model used")
    iou_threshold: float | None = Field(
        default=None, description="IoU threshold used for NMS"
    )
    image_size: int | None = Field(
        default=None, description="Image size used for inference"
    )

    @property
    def area(self) -> float:
        """Calculate the area of the bounding box."""
        return sum([d.bbox.area for d in self.detections])

    @property
    def model_name(self) -> str:
        """Get the name of the model."""
        return f"{self.backend_name} {self.model_id}"


class DetectionAttempt(SQLModel):
    """Represents a single model detection attempt."""

    model_type: str = Field(
        description="Type of model (e.g., 'ultralytics', 'roboflow')"
    )
    model_id: str = Field(description="ID of the specific model")
    success: bool = Field(description="Whether the attempt was successful")
    has_bench: bool = Field(description="Whether a bench was detected")
    confidence: float = Field(ge=0.0, le=1.0, description="Maximum confidence score")
    error: str | None = Field(
        default=None, description="Error message if attempt failed"
    )


class UnifiedBench(SQLModel):
    """Common model that can represent bench data from any source."""

    provider_id: str = Field(description="Unique provider ID")
    source: DataSource = Field(description="Data source ('osm' or 'mapillary')")
    external_id: str = Field(description="External ID from the source")
    lat: float = Field(description="Bench latitude")
    lng: float = Field(description="Bench longitude")
    tags: dict[str, Any] = Field(
        default_factory=dict, description="Source-specific tags"
    )
    confidence: float | None = Field(
        default=None, description="Confidence score if available"
    )
    created_at: datetime | None = Field(default=None, description="Creation timestamp")

    # Source-specific fields
    osm_type: str | None = Field(
        default=None, description="OSM element type (node, way, relation)"
    )
    osm_id: int | None = Field(default=None, description="Original OSM element ID")
    image_id: str | None = Field(default=None, description="Mapillary image ID")
    detection_id: str | None = Field(default=None, description="Mapillary detection ID")

    @classmethod
    def from_osm_bench(cls, osm_bench) -> "UnifiedBench":
        """Create UnifiedBench from OSMBench object."""
        return cls(
            provider_id=osm_bench.provider_id,
            source=DataSource.OSM,
            external_id=osm_bench.external_id,
            lat=osm_bench.lat,
            lng=osm_bench.lng,
            tags=osm_bench.tags.dict()
            if hasattr(osm_bench.tags, "dict")
            else osm_bench.tags,
            osm_type=osm_bench.osm_type,
            osm_id=osm_bench.osm_id,
        )

    @classmethod
    def from_mapillary_detection(
        cls, detection, coordinates: tuple[float, float]
    ) -> "UnifiedBench":
        """Create UnifiedBench from MapillaryDetection object."""
        # coordinates is (lng, lat) from Mapillary
        lng, lat = coordinates
        return cls(
            provider_id=f"mapillary_{detection.detection_id}",
            source=DataSource.MAPILLARY,
            external_id=detection.detection_id,
            lat=lat,
            lng=lng,
            tags={
                "detection_value": detection.value,
                "image_id": detection.image_id,
                "confidence": detection.confidence,
            },
            confidence=detection.confidence,
            image_id=detection.image_id,
            detection_id=detection.detection_id,
        )


class UnifiedSearchResult(SQLModel):
    """Common model for search results from any source."""

    benches: list[UnifiedBench] = Field(
        default_factory=list, description="List of found benches"
    )
    search_center_lat: float = Field(description="Search center latitude")
    search_center_lng: float = Field(description="Search center longitude")
    search_radius_meters: int = Field(description="Search radius in meters")
    total_count: int = Field(description="Total number of benches found")
    source: DataSource = Field(description="Data source ('osm' or 'mapillary')")
    search_timestamp: datetime = Field(
        default_factory=datetime.now, description="Search timestamp"
    )
    processing_time_ms: float | None = Field(
        default=None, description="Processing time in milliseconds"
    )


# ============================================================================
# Database Models (SQLModel with table=True)
# ============================================================================


class Search(SQLModel, table=True):
    """Model for search queries."""

    __tablename__ = "searches"

    id: int | None = Field(default=None, primary_key=True)
    query: str = Field(nullable=False)
    start_lat: float = Field(nullable=False)
    start_lng: float = Field(nullable=False)
    search_radius: int = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = Field(default=None)
    status: SearchStatus = Field(default=SearchStatus.PENDING)

    # Relationships
    benches: list["Bench"] = Relationship(back_populates="search", cascade_delete=True)
    bench_candidates: list["BenchCandidate"] = Relationship(
        back_populates="search", cascade_delete=True
    )

    def __repr__(self):
        return f"<Search(id={self.id}, query='{self.query}', status='{self.status}')>"


class Bench(SQLModel, table=True):
    """Model for bench data from various sources."""

    __tablename__ = "benches"

    id: int | None = Field(default=None, primary_key=True)
    search_id: int | None = Field(default=None, foreign_key="searches.id")
    provider_id: str | None = Field(default=None)  # Unified ID from OSM or Mapillary
    lat: float = Field(nullable=False)
    lng: float = Field(nullable=False)
    tags: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )  # JSON column for OSM tags or Mapillary metadata
    source: DataSource = Field(default=DataSource.OSM)  # 'osm' or 'mapillary'
    external_id: str | None = Field(
        default=None
    )  # For Mapillary image IDs or other external IDs
    representative_image_id: int | None = Field(
        default=None, foreign_key="images.id"
    )  # Best representative image
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    search: Optional["Search"] = Relationship(back_populates="benches")
    images: list["Image"] = Relationship(
        back_populates="bench",
        cascade_delete=True,
        sa_relationship_kwargs={"foreign_keys": "Image.bench_id"},
    )
    representative_image: Optional["Image"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Bench.representative_image_id]"}
    )

    def __repr__(self):
        return f"<Bench(id={self.id}, provider_id='{self.provider_id}', source='{self.source}')>"

    @classmethod
    def from_osm_bench(cls, osm_bench) -> "Bench":
        """Create Bench from OSMBench object."""
        tags = (
            osm_bench.tags.dict() if hasattr(osm_bench.tags, "dict") else osm_bench.tags
        )
        return cls(
            provider_id=osm_bench.provider_id,
            lat=osm_bench.lat,
            lng=osm_bench.lng,
            tags=tags,
            source=DataSource.OSM,
            external_id=osm_bench.external_id,
        )

    @classmethod
    def from_mapillary_detection(
        cls, detection, coordinates: tuple[float, float]
    ) -> "Bench":
        """Create Bench from MapillaryDetection object."""
        # coordinates is (lng, lat) from Mapillary
        lng, lat = coordinates
        return cls(
            provider_id=f"mapillary_{detection.detection_id}",
            lat=lat,
            lng=lng,
            tags={
                "detection_value": detection.value,
                "image_id": detection.image_id,
                "confidence": detection.confidence,
            },
            source=DataSource.MAPILLARY,
            external_id=detection.detection_id,
        )


class Image(SQLModel, table=True):
    """Model for street view image metadata."""

    __tablename__ = "images"

    id: int | None = Field(default=None, primary_key=True)
    bench_id: int = Field(foreign_key="benches.id", nullable=False)
    heading: int = Field(nullable=False)
    filepath: str | None = Field(default=None)
    filename: str | None = Field(default=None)
    file_size: int | None = Field(default=None)
    capture_success: bool = Field(nullable=False)
    capture_error: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    bench: "Bench" = Relationship(
        back_populates="images",
        sa_relationship_kwargs={"foreign_keys": "[Image.bench_id]"},
    )
    detections: list["Detection"] = Relationship(
        back_populates="image", cascade_delete=True
    )

    def __repr__(self):
        return (
            f"<Image(id={self.id}, bench_id={self.bench_id}, heading={self.heading})>"
        )


class Detection(SQLModel, table=True):
    """Model for detection results from various sources."""

    __tablename__ = "detections"

    id: int | None = Field(default=None, primary_key=True)
    image_id: int = Field(foreign_key="images.id", nullable=False)
    has_bench: bool = Field(nullable=False)
    bench_count: int = Field(default=0)
    max_confidence: float = Field(default=0.0)
    detection_success: bool = Field(nullable=False)
    detection_error: str | None = Field(default=None)
    model_id: str = Field(nullable=False)
    confidence_threshold: float = Field(nullable=False)
    source: DetectionSource = Field(
        default=DetectionSource.ROBOFLOW
    )  # 'roboflow', 'ultralytics', 'mapillary'
    external_detection_id: str | None = Field(
        default=None
    )  # For Mapillary detection IDs

    # Ultralytics-specific fields (optional for backward compatibility)
    # full_response: Optional[Dict[str, Any]] = Field(
    #     default=None, sa_column_kwargs={"type_": JSON}
    # )
    # bench_detections: Optional[Dict[str, Any]] = Field(
    #     default=None, sa_column_kwargs={"type_": JSON}
    # )
    model_url: str | None = Field(default=None)
    iou_threshold: float | None = Field(default=None)
    image_size: int | None = Field(default=None)
    inference_time: float | None = Field(default=None)
    preprocess_time: float | None = Field(default=None)
    postprocess_time: float | None = Field(default=None)

    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    image: "Image" = Relationship(back_populates="detections")
    detection_items: list["DetectionItem"] = Relationship(
        back_populates="detection", cascade_delete=True
    )

    def __repr__(self):
        return f"<Detection(id={self.id}, image_id={self.image_id}, confidence={self.max_confidence})>"


class BenchReport(SQLModel, table=True):
    """Model for user reports of bad bench detections."""

    __tablename__ = "bench_reports"

    id: int | None = Field(default=None, primary_key=True)
    bench_id: int = Field(foreign_key="benches.id", nullable=False)
    image_id: int | None = Field(
        default=None, foreign_key="images.id"
    )  # The specific image being reported
    report_type: BenchReportType = Field(
        default=BenchReportType.BAD_DETECTION
    )  # 'bad_detection', 'incorrect_location', etc.
    description: str | None = Field(default=None)  # Optional user description
    user_agent: str | None = Field(default=None)  # Browser/app info for debugging
    ip_address: str | None = Field(default=None)  # For potential spam prevention
    user_location_lat: float | None = Field(
        default=None
    )  # User's location when reporting
    user_location_lng: float | None = Field(default=None)
    reported_image_filename: str | None = Field(
        default=None
    )  # Copy of the image being reported
    extra_metadata: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )  # Additional metadata (device info, etc.)
    status: BenchReportStatus = Field(
        default=BenchReportStatus.PENDING
    )  # 'pending', 'reviewed', 'resolved', 'dismissed'
    admin_notes: str | None = Field(default=None)  # Admin notes for review
    created_at: datetime = Field(default_factory=datetime.now)
    reviewed_at: datetime | None = Field(default=None)

    # Relationships
    bench: "Bench" = Relationship()
    image: Optional["Image"] = Relationship()

    def __repr__(self):
        return f"<BenchReport(id={self.id}, bench_id={self.bench_id}, type='{self.report_type}', status='{self.status}')>"


class MissingBenchReport(SQLModel, table=True):
    """Model for user reports of missing benches."""

    __tablename__ = "missing_bench_reports"

    id: int | None = Field(default=None, primary_key=True)
    lat: float = Field(nullable=False)  # Reported bench location
    lng: float = Field(nullable=False)
    description: str | None = Field(default=None)  # User description of the bench
    user_agent: str | None = Field(default=None)  # Browser/app info
    ip_address: str | None = Field(default=None)  # For potential spam prevention
    user_location_lat: float | None = Field(
        default=None
    )  # User's GPS location when reporting
    user_location_lng: float | None = Field(default=None)
    location_method: LocationMethod = Field(
        default=LocationMethod.GPS
    )  # 'gps', 'map_click'
    uploaded_image_filename: str | None = Field(
        default=None
    )  # User-uploaded photo of the bench
    accuracy_meters: float | None = Field(default=None)  # GPS accuracy if available
    extra_metadata: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )  # Additional metadata (device info, etc.)
    status: MissingBenchReportStatus = Field(
        default=MissingBenchReportStatus.PENDING
    )  # 'pending', 'verified', 'added', 'dismissed'
    admin_notes: str | None = Field(default=None)  # Admin notes for review
    created_at: datetime = Field(default_factory=datetime.now)
    reviewed_at: datetime | None = Field(default=None)

    def __repr__(self):
        return f"<MissingBenchReport(id={self.id}, location=({self.lat}, {self.lng}), status='{self.status}')>"


class BenchCandidate(SQLModel, table=True):
    """Model for storing bench candidates found during the search phase."""

    __tablename__ = "bench_candidates"

    id: int | None = Field(default=None, primary_key=True)
    search_id: int = Field(foreign_key="searches.id", nullable=False)
    provider_id: str | None = Field(default=None)  # Unified ID from OSM or Mapillary
    lat: float = Field(nullable=False)
    lng: float = Field(nullable=False)
    tags: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )  # JSON column for OSM tags or Mapillary metadata
    source: DataSource = Field(default=DataSource.OSM)  # 'osm' or 'mapillary'
    external_id: str | None = Field(
        default=None
    )  # For Mapillary image IDs or other external IDs
    confidence: float | None = Field(
        default=None
    )  # Confidence score if available from source
    status: BenchCandidateStatus = Field(
        default=BenchCandidateStatus.PENDING
    )  # Processing status: pending, image_download_done, detection_done
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    search: "Search" = Relationship(back_populates="bench_candidates")

    def __repr__(self):
        return f"<BenchCandidate(id={self.id}, provider_id='{self.provider_id}', source='{self.source}')>"


# ============================================================================
# API Request/Response Models (SQLModel without table=True)
# ============================================================================


class SearchBase(SQLModel):
    """Base schema for search operations."""

    query: str
    start_lat: float
    start_lng: float
    search_radius: int


class BenchBase(SQLModel):
    """Base schema for bench data."""

    provider_id: str | None = None  # Unified ID from OSM or Mapillary
    lat: float
    lng: float
    tags: dict[str, Any] = {}
    source: DataSource = DataSource.OSM  # 'osm' or 'mapillary'
    external_id: str | None = None  # For Mapillary image IDs


class ImageBase(SQLModel):
    """Base schema for image data."""

    heading: int
    filepath: str | None = None
    filename: str | None = None
    file_size: int | None = None
    capture_success: bool
    capture_error: str | None = None


class DetectionBase(SQLModel):
    """Base schema for detection data."""

    image_id: int | None = None
    has_bench: bool
    bench_count: int = 0
    max_confidence: float = 0.0
    detection_success: bool
    detection_error: str | None = None
    model_id: str
    confidence_threshold: float
    source: DetectionSource = (
        DetectionSource.ROBOFLOW
    )  # 'roboflow', 'ultralytics', 'mapillary'
    external_detection_id: str | None = None  # For Mapillary detection IDs

    # Ultralytics-specific fields (optional for backward compatibility)
    # full_response: Optional[Dict[str, Any]] = None
    # bench_detections: Optional[list[dict[str, Any]]] = None
    model_url: str | None = None
    iou_threshold: float | None = None
    image_size: int | None = None
    inference_time: float | None = None
    preprocess_time: float | None = None
    postprocess_time: float | None = None


class BenchCandidateBase(SQLModel):
    """Base schema for bench candidate data."""

    provider_id: str | None = None
    lat: float
    lng: float
    tags: dict[str, Any] | None = None
    source: DataSource = DataSource.OSM
    external_id: str | None = None
    confidence: float | None = None


# ============================================================================
# Database Configuration Functions
# ============================================================================


def json_serializer(obj: Any) -> str:
    return json.dumps(to_jsonable_python(obj))


def create_database_engine(database_path: str):
    """Create SQLModel engine for the database."""
    engine = create_engine(
        f"sqlite:///{database_path}", echo=False, json_serializer=json_serializer
    )
    return engine


def create_database_session(engine):
    """Create SQLModel session."""
    return Session(engine)


def init_database(database_path: str):
    """Initialize database with all tables."""
    engine = create_database_engine(database_path)
    SQLModel.metadata.create_all(engine)
    return engine
