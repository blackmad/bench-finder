"""
SQLAlchemy models for bench finder database schema.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.sql import func

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


class Base(DeclarativeBase):
    """Base class for all database models."""


class Search(Base):
    """Model for search queries."""

    __tablename__ = "searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    query: Mapped[str] = mapped_column(String, nullable=False)
    start_lat: Mapped[float] = mapped_column(Float, nullable=False)
    start_lng: Mapped[float] = mapped_column(Float, nullable=False)
    search_radius: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[SearchStatus] = mapped_column(
        SAEnum(SearchStatus, name="search_status"), default=SearchStatus.PENDING
    )

    # Relationships
    benches: Mapped[list["Bench"]] = relationship(
        "Bench", back_populates="search", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Search(id={self.id}, query='{self.query}', status='{self.status}')>"


class Bench(Base):
    """Model for bench data from various sources."""

    __tablename__ = "benches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    search_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("searches.id"), nullable=True
    )  # Nullable for Mapillary benches
    provider_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # Unified ID from OSM or Mapillary
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    tags: Mapped[Optional[dict]] = mapped_column(
        JSON
    )  # JSON column for OSM tags or Mapillary metadata
    source: Mapped[DataSource] = mapped_column(
        SAEnum(DataSource, name="bench_source"), nullable=False, default=DataSource.OSM
    )  # 'osm' or 'mapillary'
    external_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # For Mapillary image IDs or other external IDs
    representative_image_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("images.id"), nullable=True
    )  # Best representative image
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    search: Mapped[Optional["Search"]] = relationship(
        "Search", back_populates="benches"
    )
    images: Mapped[list["Image"]] = relationship(
        "Image",
        back_populates="bench",
        cascade="all, delete-orphan",
        foreign_keys="Image.bench_id",
    )
    representative_image: Mapped[Optional["Image"]] = relationship(
        "Image", foreign_keys=[representative_image_id]
    )

    # Indexes
    __table_args__ = (
        Index("idx_benches_search_id", "search_id"),
        Index("idx_benches_provider_id", "provider_id"),
        Index("idx_benches_location", "lat", "lng"),
        Index("idx_benches_source", "source"),
        Index("idx_benches_external_id", "external_id"),
        Index("idx_benches_representative_image_id", "representative_image_id"),
    )

    def __repr__(self):
        return f"<Bench(id={self.id}, provider_id='{self.provider_id}', source='{self.source}')>"


class Image(Base):
    """Model for street view image metadata."""

    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bench_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("benches.id"), nullable=False
    )
    heading: Mapped[int] = mapped_column(Integer, nullable=False)
    filepath: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    filename: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    capture_success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    capture_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    bench: Mapped["Bench"] = relationship(
        "Bench", back_populates="images", foreign_keys=[bench_id]
    )
    detections: Mapped[list["Detection"]] = relationship(
        "Detection", back_populates="image", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("idx_images_bench_id", "bench_id"),
        Index("idx_images_success", "capture_success"),
    )

    def __repr__(self):
        return (
            f"<Image(id={self.id}, bench_id={self.bench_id}, heading={self.heading})>"
        )


class Detection(Base):
    """Model for detection results from various sources."""

    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("images.id"), nullable=False
    )
    has_bench: Mapped[bool] = mapped_column(Boolean, nullable=False)
    bench_count: Mapped[int] = mapped_column(Integer, default=0)
    max_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    detections: Mapped[Optional[dict]] = mapped_column(
        JSON
    )  # JSON column for detection details
    detection_success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    detection_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    confidence_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[DetectionSource] = mapped_column(
        SAEnum(DetectionSource, name="detection_source"),
        nullable=False,
        default=DetectionSource.ROBOFLOW,
    )  # 'roboflow', 'ultralytics', 'mapillary'
    external_detection_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # For Mapillary detection IDs

    # Ultralytics-specific fields (optional for backward compatibility)
    full_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    bench_detections: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    model_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    iou_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    image_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inference_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    preprocess_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    postprocess_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    image: Mapped["Image"] = relationship("Image", back_populates="detections")

    # Indexes
    __table_args__ = (
        Index("idx_detections_image_id", "image_id"),
        Index("idx_detections_has_bench", "has_bench"),
        Index("idx_detections_confidence", "max_confidence"),
        Index("idx_detections_source", "source"),
        Index("idx_detections_external_id", "external_detection_id"),
    )

    def __repr__(self):
        return f"<Detection(id={self.id}, image_id={self.image_id}, confidence={self.max_confidence})>"


class BenchReport(Base):
    """Model for user reports of bad bench detections."""

    __tablename__ = "bench_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bench_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("benches.id"), nullable=False
    )
    image_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("images.id"), nullable=True
    )  # The specific image being reported
    report_type: Mapped[BenchReportType] = mapped_column(
        SAEnum(BenchReportType, name="bench_report_type"),
        nullable=False,
        default=BenchReportType.BAD_DETECTION,
    )  # 'bad_detection', 'incorrect_location', etc.
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Optional user description
    user_agent: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # Browser/app info for debugging
    ip_address: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # For potential spam prevention
    user_location_lat: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # User's location when reporting
    user_location_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reported_image_filename: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # Copy of the image being reported
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # Additional metadata (device info, etc.)
    status: Mapped[BenchReportStatus] = mapped_column(
        SAEnum(BenchReportStatus, name="bench_report_status"),
        default=BenchReportStatus.PENDING,
    )  # 'pending', 'reviewed', 'resolved', 'dismissed'
    admin_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Admin notes for review
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    bench: Mapped["Bench"] = relationship("Bench")
    image: Mapped[Optional["Image"]] = relationship("Image")

    # Indexes
    __table_args__ = (
        Index("idx_bench_reports_bench_id", "bench_id"),
        Index("idx_bench_reports_image_id", "image_id"),
        Index("idx_bench_reports_status", "status"),
        Index("idx_bench_reports_created_at", "created_at"),
        Index("idx_bench_reports_type", "report_type"),
    )

    def __repr__(self):
        return f"<BenchReport(id={self.id}, bench_id={self.bench_id}, type='{self.report_type}', status='{self.status}')>"


class MissingBenchReport(Base):
    """Model for user reports of missing benches."""

    __tablename__ = "missing_bench_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)  # Reported bench location
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # User description of the bench
    user_agent: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # Browser/app info
    ip_address: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # For potential spam prevention
    user_location_lat: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # User's GPS location when reporting
    user_location_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    location_method: Mapped[LocationMethod] = mapped_column(
        SAEnum(LocationMethod, name="location_method"),
        nullable=False,
        default=LocationMethod.GPS,
    )  # 'gps', 'map_click'
    uploaded_image_filename: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # User-uploaded photo of the bench
    accuracy_meters: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # GPS accuracy if available
    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )  # Additional metadata (device info, etc.)
    status: Mapped[MissingBenchReportStatus] = mapped_column(
        SAEnum(MissingBenchReportStatus, name="missing_bench_report_status"),
        default=MissingBenchReportStatus.PENDING,
    )  # 'pending', 'verified', 'added', 'dismissed'
    admin_notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # Admin notes for review
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_missing_bench_reports_location", "lat", "lng"),
        Index("idx_missing_bench_reports_status", "status"),
        Index("idx_missing_bench_reports_created_at", "created_at"),
        Index("idx_missing_bench_reports_method", "location_method"),
    )

    def __repr__(self):
        return f"<MissingBenchReport(id={self.id}, location=({self.lat}, {self.lng}), status='{self.status}')>"


class BenchCandidate(Base):
    """Model for storing bench candidates found during the search phase."""

    __tablename__ = "bench_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    search_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("searches.id"), nullable=False
    )
    provider_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # Unified ID from OSM or Mapillary
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    tags: Mapped[Optional[dict]] = mapped_column(
        JSON
    )  # JSON column for OSM tags or Mapillary metadata
    source: Mapped[DataSource] = mapped_column(
        SAEnum(DataSource, name="bench_candidate_source"),
        nullable=False,
        default=DataSource.OSM,
    )  # 'osm' or 'mapillary'
    external_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # For Mapillary image IDs or other external IDs
    confidence: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # Confidence score if available from source
    status: Mapped[BenchCandidateStatus] = mapped_column(
        SAEnum(BenchCandidateStatus, name="bench_candidate_status"),
        nullable=False,
        default=BenchCandidateStatus.PENDING,
    )  # Processing status: pending, image_download_done, detection_done
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    search: Mapped["Search"] = relationship("Search")

    # Indexes
    __table_args__ = (
        Index("idx_bench_candidates_search_id", "search_id"),
        Index("idx_bench_candidates_provider_id", "provider_id"),
        Index("idx_bench_candidates_location", "lat", "lng"),
        Index("idx_bench_candidates_source", "source"),
        Index("idx_bench_candidates_external_id", "external_id"),
        Index("idx_bench_candidates_status", "status"),
    )

    def __repr__(self):
        return f"<BenchCandidate(id={self.id}, provider_id='{self.provider_id}', source='{self.source}')>"


# Database configuration
def create_database_engine(database_path: str):
    """Create SQLAlchemy engine for the database."""
    engine = create_engine(f"sqlite:///{database_path}", echo=False)
    return engine


def create_database_session(engine):
    """Create SQLAlchemy session."""
    Session = sessionmaker(bind=engine)
    return Session()


def init_database(database_path: str):
    """Initialize database with all tables."""
    engine = create_database_engine(database_path)
    Base.metadata.create_all(engine)
    return engine
