"""
Unified SQLModel models for bench finder application.
This file combines database models, detection models, and API schemas using SQLModel.
"""

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, Optional

from pydantic_core import to_jsonable_python


if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

    from bench_finder.models.overpass_models import OSMBench
from sqlalchemy import JSON, String, UniqueConstraint
from sqlmodel import Column, Field, Relationship, Session, SQLModel, create_engine

from .enums import (
    BenchCandidateStatus,
    BenchReportStatus,
    BenchReportType,
    BenchUserStatus,
    DataSource,
    DetectionSource,
    ImageKind,
    ImageSource,
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

    def __init__(self, **data: Any) -> None:
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
    detection_id: int = Field(foreign_key="detections.id", nullable=False, index=True)
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
    is_target: bool | None = Field(
        default=None,
        description="True if this is the detection of the bench the view was aimed at",
    )
    center_offset_deg: float | None = Field(
        default=None,
        description="Angular offset of the box centre from the image centre, in degrees",
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
        description="Source of the detection (roboflow, ultralytics)",
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
    source: DataSource = Field(description="Data source (currently only 'osm')")
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
    image_id: str | None = Field(default=None, description="External image ID")
    detection_id: str | None = Field(default=None, description="External detection ID")

    @classmethod
    def from_osm_bench(cls, osm_bench: "OSMBench") -> "UnifiedBench":
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


class UnifiedSearchResult(SQLModel):
    """Common model for search results from any source."""

    benches: list[UnifiedBench] = Field(
        default_factory=list, description="List of found benches"
    )
    search_center_lat: float = Field(description="Search center latitude")
    search_center_lng: float = Field(description="Search center longitude")
    search_radius_meters: int = Field(description="Search radius in meters")
    total_count: int = Field(description="Total number of benches found")
    source: DataSource = Field(description="Data source (currently only 'osm')")
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
    bench_candidates: list["BenchCandidate"] = Relationship(
        back_populates="search", cascade_delete=True
    )

    def __repr__(self) -> str:
        return f"<Search(id={self.id}, query='{self.query}', status='{self.status}')>"


# Bench class removed - replaced by ProcessedBench (one per BenchCandidate)


class Image(SQLModel, table=True):
    """Model for street view image metadata."""

    __tablename__ = "images"
    # NULL pano_id (legacy rows) never collides: NULLs are distinct in a unique index.
    __table_args__ = (
        UniqueConstraint(
            "bench_candidate_id",
            "pano_id",
            "kind",
            name="uq_images_candidate_pano_kind",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    bench_candidate_id: int = Field(foreign_key="bench_candidates.id", nullable=False)
    heading: int = Field(nullable=False)
    filepath: str | None = Field(default=None)
    filename: str | None = Field(default=None)
    file_size: int | None = Field(default=None)
    firebase_url: str | None = Field(
        default=None, description="Firebase Storage URL for cloud-hosted images"
    )
    capture_success: bool = Field(nullable=False)
    capture_error: str | None = Field(default=None)
    # Image provenance tracking
    image_source: ImageSource | None = Field(
        default=None,
        description="Source of the image: streetview_api, streetview_streetlevel, or apple_streetlevel",
    )
    # Panorama location (for streetlevel sources - may differ from bench location)
    panorama_lat: float | None = Field(
        default=None, description="Latitude of the actual panorama location"
    )
    panorama_lng: float | None = Field(
        default=None, description="Longitude of the actual panorama location"
    )
    # Panorama metadata (pano_id, date, etc.)
    panorama_metadata: dict[str, Any] | None = Field(
        default=None,
        description="Additional panorama metadata (pano_id, date, etc.)",
        sa_column=Column(JSON),
    )
    # Panorama heading (from streetlevel/lookaround API)
    panorama_heading: float | None = Field(
        default=None,
        description="Heading/orientation of the panorama itself (from streetlevel/lookaround API)",
    )
    # Aimed-view geometry (see docs/RESURRECTION_PLAN.md, Schema additions)
    pano_id: str | None = Field(default=None, description="Source panorama id")
    pano_date: str | None = Field(
        default=None, description="Panorama capture date, e.g. 2023-05"
    )
    camera_bearing_deg: float | None = Field(
        default=None, description="Bearing from the camera to the bench, degrees"
    )
    camera_distance_m: float | None = Field(
        default=None, description="Distance from the camera to the bench, metres"
    )
    fov_deg: float | None = Field(default=None, description="Horizontal field of view")
    pitch_deg: float | None = Field(default=None, description="Camera pitch")
    kind: str = Field(
        default=ImageKind.LEGACY.value,
        description="aimed (view aimed at the bench), pano (raw panorama) or legacy",
    )
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    bench_candidate: "BenchCandidate" = Relationship(
        back_populates="images",
        sa_relationship_kwargs={"foreign_keys": "[Image.bench_candidate_id]"},
    )
    detections: list["Detection"] = Relationship(
        back_populates="image", cascade_delete=True
    )

    def __repr__(self) -> str:
        return f"<Image(id={self.id}, bench_candidate_id={self.bench_candidate_id}, heading={self.heading})>"


class Detection(SQLModel, table=True):
    """Model for detection results from various sources."""

    __tablename__ = "detections"

    id: int | None = Field(default=None, primary_key=True)
    image_id: int = Field(foreign_key="images.id", nullable=False)
    has_bench: bool = Field(nullable=False)
    bench_count: int = Field(default=0)
    max_confidence: float = Field(default=0.0)
    # Every box of an aimed-view run ([{"conf", "xyxy"}], bench_finder.detect_aimed).
    # Added by hand to the Amsterdam db; here so a fresh db has it too.
    detections: list | None = Field(default=None, sa_column=Column(JSON))
    detection_success: bool = Field(nullable=False)
    detection_error: str | None = Field(default=None)
    model_id: str = Field(nullable=False)
    confidence_threshold: float = Field(nullable=False)
    source: DetectionSource = Field(
        default=DetectionSource.ROBOFLOW
    )  # 'roboflow', 'ultralytics'
    external_detection_id: str | None = Field(
        default=None
    )  # For external detection IDs

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

    def __repr__(self) -> str:
        return f"<Detection(id={self.id}, image_id={self.image_id}, confidence={self.max_confidence})>"


# DetectedBench removed - this functionality is now part of ProcessedBench
# The best_image_id and best_detection_id in ProcessedBench serve the same purpose


class BenchReport(SQLModel, table=True):
    """Model for user reports of bad bench detections."""

    __tablename__ = "bench_reports"

    id: int | None = Field(default=None, primary_key=True)
    bench_candidate_id: int = Field(
        foreign_key="bench_candidates.id", nullable=False, index=True
    )
    image_id: int | None = Field(
        default=None, foreign_key="images.id", index=True
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
    bench_candidate: "BenchCandidate" = Relationship()
    image: Optional["Image"] = Relationship()

    def __repr__(self) -> str:
        return f"<BenchReport(id={self.id}, bench_candidate_id={self.bench_candidate_id}, type='{self.report_type}', status='{self.status}')>"


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

    def __repr__(self) -> str:
        return f"<MissingBenchReport(id={self.id}, location=({self.lat}, {self.lng}), status='{self.status}')>"


class ReverseGeocode(SQLModel, table=True):
    """Model for storing reverse geocoding results for bench candidates."""

    __tablename__ = "reverse_geocodes"

    id: int | None = Field(default=None, primary_key=True)
    bench_candidate_id: int = Field(
        foreign_key="bench_candidates.id", nullable=False, unique=True
    )
    formatted_address: str = Field(
        nullable=False, description="Formatted address from reverse geocoding"
    )
    # Structured address components
    street_number: str | None = Field(default=None, description="Street number")
    street_name: str | None = Field(default=None, description="Street name/route")
    city: str | None = Field(default=None, description="City/locality")
    state: str | None = Field(
        default=None, description="State/administrative area level 1"
    )
    postal_code: str | None = Field(default=None, description="Postal/ZIP code")
    country: str | None = Field(default=None, description="Country")
    raw_response: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column(JSON),
        description="Raw API response for future reference",
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = Field(default=None)

    # Relationships
    bench_candidate: "BenchCandidate" = Relationship(back_populates="reverse_geocode")

    def __repr__(self) -> str:
        return f"<ReverseGeocode(id={self.id}, bench_candidate_id={self.bench_candidate_id}, address='{self.formatted_address[:50]}...')>"


class BenchCandidate(SQLModel, table=True):
    """Model for storing bench candidates found during the search phase."""

    __tablename__ = "bench_candidates"

    id: int | None = Field(default=None, primary_key=True)
    search_id: int = Field(foreign_key="searches.id", nullable=False)
    provider_id: str | None = Field(
        default=None, unique=True, index=True
    )  # Unified ID from OSM; unique across all candidates
    lat: float = Field(nullable=False)
    lng: float = Field(nullable=False)
    tags: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON)
    )  # JSON column for OSM tags or other metadata
    source: DataSource = Field(default=DataSource.OSM)  # Currently only 'osm'
    external_id: str | None = Field(default=None)  # For external IDs
    confidence: float | None = Field(
        default=None
    )  # Confidence score if available from source
    status: BenchCandidateStatus = Field(
        default=BenchCandidateStatus.PENDING
    )  # Processing status: pending, image_download_done, detection_done
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    search: "Search" = Relationship(back_populates="bench_candidates")
    processed_bench: Optional["ProcessedBench"] = Relationship(
        back_populates="bench_candidate", sa_relationship_kwargs={"uselist": False}
    )
    images: list["Image"] = Relationship(
        back_populates="bench_candidate",
        cascade_delete=True,
        sa_relationship_kwargs={"foreign_keys": "Image.bench_candidate_id"},
    )
    reverse_geocode: Optional["ReverseGeocode"] = Relationship(
        back_populates="bench_candidate", sa_relationship_kwargs={"uselist": False}
    )

    def __repr__(self) -> str:
        return f"<BenchCandidate(id={self.id}, provider_id='{self.provider_id}', source='{self.source}')>"


class ProcessedBench(SQLModel, table=True):
    """
    Processed bench - one per BenchCandidate.

    This is a discriminated union at the type level (BenchDetected | NoBenchDetected),
    represented by the detection_status field which can be "detected" or "no_bench".

    When detection_status="detected", best_image_id and best_detection_id must be set.
    When detection_status="no_bench", these fields are None.
    """

    __tablename__ = "processed_benches"

    id: int | None = Field(default=None, primary_key=True)
    bench_candidate_id: int = Field(
        foreign_key="bench_candidates.id", nullable=False, unique=True
    )
    detection_status: Literal["detected", "no_bench"] = Field(
        ...,
        description="Discriminator: 'detected' if bench found, 'no_bench' otherwise",
        sa_column=Column(String, nullable=False),
    )
    # These fields are required when detection_status="detected", None when "no_bench"
    best_image_id: int | None = Field(
        default=None, foreign_key="images.id", index=True, nullable=True
    )
    best_detection_id: int | None = Field(
        default=None, foreign_key="detections.id", index=True, nullable=True
    )
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    bench_candidate: "BenchCandidate" = Relationship(back_populates="processed_bench")
    best_image: Optional["Image"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[ProcessedBench.best_image_id]"}
    )
    best_detection: Optional["Detection"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[ProcessedBench.best_detection_id]"}
    )

    def __repr__(self) -> str:
        return f"<ProcessedBench(id={self.id}, bench_candidate_id={self.bench_candidate_id}, status='{self.detection_status}')>"


class BenchRating(SQLModel, table=True):
    """Model for storing user ratings of benches."""

    __tablename__ = "bench_ratings"

    id: int | None = Field(default=None, primary_key=True)
    bench_candidate_id: int = Field(
        foreign_key="bench_candidates.id", nullable=False, index=True
    )
    user_id: str = Field(
        nullable=False, index=True, description="Supabase user ID (UUID)"
    )
    rating: int = Field(ge=1, le=5, nullable=False, description="Rating from 1 to 5")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    bench_candidate: "BenchCandidate" = Relationship()

    def __repr__(self) -> str:
        return f"<BenchRating(id={self.id}, bench_candidate_id={self.bench_candidate_id}, user_id='{self.user_id}', rating={self.rating})>"


class BenchUserStatusRecord(SQLModel, table=True):
    """Model for storing user status markers for benches (been, want_to_go, favorite)."""

    __tablename__ = "bench_user_status"

    id: int | None = Field(default=None, primary_key=True)
    bench_candidate_id: int = Field(
        foreign_key="bench_candidates.id", nullable=False, index=True
    )
    user_id: str = Field(
        nullable=False, index=True, description="Supabase user ID (UUID)"
    )
    status: BenchUserStatus = Field(
        nullable=False, description="Status: been, want_to_go, or favorite"
    )
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    bench_candidate: "BenchCandidate" = Relationship()

    def __repr__(self) -> str:
        return f"<BenchUserStatusRecord(id={self.id}, bench_candidate_id={self.bench_candidate_id}, user_id='{self.user_id}', status='{self.status}')>"


class BenchComment(SQLModel, table=True):
    """Model for storing user comments on benches."""

    __tablename__ = "bench_comments"

    id: int | None = Field(default=None, primary_key=True)
    bench_candidate_id: int = Field(
        foreign_key="bench_candidates.id", nullable=False, index=True
    )
    user_id: str = Field(
        nullable=False, index=True, description="Supabase user ID (UUID)"
    )
    comment: str = Field(nullable=False, description="Comment text")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    bench_candidate: "BenchCandidate" = Relationship()

    def __repr__(self) -> str:
        return f"<BenchComment(id={self.id}, bench_candidate_id={self.bench_candidate_id}, user_id='{self.user_id}')>"


# Type aliases for the discriminated union (for type checking/documentation)
BenchDetected = ProcessedBench  # When detection_status="detected"
NoBenchDetected = ProcessedBench  # When detection_status="no_bench"


class ImageAnnotation(SQLModel, table=True):
    """A label attached to an image by a model or a human; both live side by side."""

    __tablename__ = "image_annotations"

    id: int | None = Field(default=None, primary_key=True)
    image_id: int = Field(foreign_key="images.id", nullable=False, index=True)
    annotator: str = Field(nullable=False, description="Model id or human:<uid>")
    label_type: str = Field(nullable=False)
    value: Any = Field(default=None, sa_column=Column(JSON))
    confidence: float | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)


class BenchAttributes(SQLModel, table=True):
    """Derived per-bench attributes (facing, type, hero image); one row per candidate."""

    __tablename__ = "bench_attributes"

    id: int | None = Field(default=None, primary_key=True)
    bench_candidate_id: int = Field(
        foreign_key="bench_candidates.id", nullable=False, unique=True
    )
    facing_deg: float | None = Field(default=None)
    facing_confidence: float | None = Field(default=None)
    facing_method: str | None = Field(
        default=None, description="osm_tag, vlm, geometry or human"
    )
    axis_only: bool = Field(
        default=False, description="Backless bench: axis, not facing"
    )
    bench_type: str | None = Field(default=None)
    backrest: bool | None = Field(default=None)
    faces_category: str | None = Field(default=None)
    faces_text: str | None = Field(default=None)
    hero_image_id: int | None = Field(default=None, foreign_key="images.id", index=True)
    hero_reason: str | None = Field(default=None)
    embed_pano_id: str | None = Field(default=None)
    embed_heading_deg: float | None = Field(default=None)
    updated_at: datetime = Field(default_factory=datetime.now)


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
    external_id: str | None = None  # For external IDs


class ImageBase(SQLModel):
    """Base schema for image data."""

    pano_id: str | None = None
    pano_date: str | None = None
    camera_bearing_deg: float | None = None
    camera_distance_m: float | None = None
    fov_deg: float | None = None
    pitch_deg: float | None = None
    kind: str = ImageKind.LEGACY.value
    heading: int
    filepath: str | None = None
    filename: str | None = None
    file_size: int | None = None
    capture_success: bool
    capture_error: str | None = None
    image_source: ImageSource | None = None
    panorama_lat: float | None = None
    panorama_lng: float | None = None
    panorama_metadata: dict[str, Any] | None = None
    panorama_heading: float | None = None


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
    source: DetectionSource = DetectionSource.ROBOFLOW  # 'roboflow', 'ultralytics'
    external_detection_id: str | None = None  # For external detection IDs

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


# ============================================================================
# Database Configuration Functions
# ============================================================================


def json_serializer(obj: Any) -> str:
    return json.dumps(to_jsonable_python(obj))


def create_database_engine(
    database_url: str | None = None, database_path: str | None = None
) -> "Engine":
    """
    Create SQLModel engine for the database.

    Supports both SQLite (via path) and PostgreSQL (via connection URL).
    If database_url is provided, it will be used directly.
    If database_path is provided, it will create a SQLite connection string.

    Args:
        database_url: Full database connection URL (e.g., postgresql://... or sqlite:///...)
                     Automatically converts postgres:// to postgresql:// for SQLAlchemy compatibility
        database_path: Path to SQLite database file (only used if database_url is None)

    Returns:
        SQLAlchemy engine
    """
    if database_url:
        # Normalize postgres:// to postgresql:// (SQLAlchemy requirement)
        connection_string = database_url.replace("postgres://", "postgresql://", 1)
    elif database_path:
        # Create SQLite connection string
        connection_string = f"sqlite:///{database_path}"
    else:
        raise ValueError("Either database_url or database_path must be provided")

    # Configure engine based on database type
    if connection_string.startswith("postgresql"):
        # PostgreSQL connection - use connection pooling for serverless
        engine = create_engine(
            connection_string,
            echo=False,
            json_serializer=json_serializer,
            pool_pre_ping=True,  # Verify connections before using
            pool_size=5,
            max_overflow=10,
        )
    else:
        # SQLite connection
        engine = create_engine(
            connection_string,
            echo=False,
            json_serializer=json_serializer,
            # Wait out other jobs' locks (a long read, another writer) instead
            # of failing after SQLite's default 5 s.
            connect_args={"check_same_thread": False, "timeout": 120}
            if "sqlite" in connection_string
            else {},
        )

    return engine


def create_database_session(engine: "Engine") -> Session:
    """Create SQLModel session."""
    return Session(engine)


def init_database(
    database_url: str | None = None, database_path: str | None = None
) -> "Engine":
    """
    Initialize database with all tables.

    Args:
        database_url: Full database connection URL (e.g., postgresql://... or sqlite:///...)
        database_path: Path to SQLite database file (only used if database_url is None)

    Returns:
        SQLAlchemy engine
    """
    engine = create_database_engine(
        database_url=database_url, database_path=database_path
    )
    SQLModel.metadata.create_all(engine)
    return engine
