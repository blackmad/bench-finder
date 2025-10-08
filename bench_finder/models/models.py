"""
SQLAlchemy models for bench finder database schema.
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey,
    JSON, create_engine, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()


class Search(Base):
    """Model for search queries."""
    __tablename__ = 'searches'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String, nullable=False)
    start_lat = Column(Float, nullable=False)
    start_lng = Column(Float, nullable=False)
    search_radius = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=func.now())
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default='pending')
    
    # Relationships
    benches = relationship("Bench", back_populates="search", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Search(id={self.id}, query='{self.query}', status='{self.status}')>"


class Bench(Base):
    """Model for bench data from various sources."""
    __tablename__ = 'benches'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    search_id = Column(Integer, ForeignKey('searches.id'), nullable=True)  # Nullable for Mapillary benches
    provider_id = Column(String, nullable=True)  # Unified ID from OSM or Mapillary
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    tags = Column(JSON)  # JSON column for OSM tags or Mapillary metadata
    source = Column(String, nullable=False, default='osm')  # 'osm' or 'mapillary'
    external_id = Column(String, nullable=True)  # For Mapillary image IDs or other external IDs
    representative_image_id = Column(Integer, ForeignKey('images.id'), nullable=True)  # Best representative image
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    search = relationship("Search", back_populates="benches")
    images = relationship("Image", back_populates="bench", cascade="all, delete-orphan", foreign_keys="Image.bench_id")
    representative_image = relationship("Image", foreign_keys=[representative_image_id])
    
    # Indexes
    __table_args__ = (
        Index('idx_benches_search_id', 'search_id'),
        Index('idx_benches_provider_id', 'provider_id'),
        Index('idx_benches_location', 'lat', 'lng'),
        Index('idx_benches_source', 'source'),
        Index('idx_benches_external_id', 'external_id'),
        Index('idx_benches_representative_image_id', 'representative_image_id'),
    )
    
    def __repr__(self):
        return f"<Bench(id={self.id}, provider_id='{self.provider_id}', source='{self.source}')>"


class Image(Base):
    """Model for street view image metadata."""
    __tablename__ = 'images'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bench_id = Column(Integer, ForeignKey('benches.id'), nullable=False)
    heading = Column(Integer, nullable=False)
    filepath = Column(String, nullable=True)
    filename = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    capture_success = Column(Boolean, nullable=False)
    capture_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    bench = relationship("Bench", back_populates="images", foreign_keys=[bench_id])
    detections = relationship("Detection", back_populates="image", cascade="all, delete-orphan")
    ultralytics_detections = relationship("UltralyticsDetection", back_populates="image", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_images_bench_id', 'bench_id'),
        Index('idx_images_success', 'capture_success'),
    )
    
    def __repr__(self):
        return f"<Image(id={self.id}, bench_id={self.bench_id}, heading={self.heading})>"


class Detection(Base):
    """Model for detection results from various sources."""
    __tablename__ = 'detections'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    image_id = Column(Integer, ForeignKey('images.id'), nullable=False)
    has_bench = Column(Boolean, nullable=False)
    bench_count = Column(Integer, default=0)
    max_confidence = Column(Float, default=0.0)
    detections = Column(JSON)  # JSON column for detection details
    detection_success = Column(Boolean, nullable=False)
    detection_error = Column(Text, nullable=True)
    model_id = Column(String, nullable=False)
    confidence_threshold = Column(Float, nullable=False)
    source = Column(String, nullable=False, default='roboflow')  # 'roboflow', 'ultralytics', 'mapillary'
    external_detection_id = Column(String, nullable=True)  # For Mapillary detection IDs
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    image = relationship("Image", back_populates="detections")
    
    # Indexes
    __table_args__ = (
        Index('idx_detections_image_id', 'image_id'),
        Index('idx_detections_has_bench', 'has_bench'),
        Index('idx_detections_confidence', 'max_confidence'),
        Index('idx_detections_source', 'source'),
        Index('idx_detections_external_id', 'external_detection_id'),
    )
    
    def __repr__(self):
        return f"<Detection(id={self.id}, image_id={self.image_id}, confidence={self.max_confidence})>"


class UltralyticsDetection(Base):
    """Model for Ultralytics detection results with segmentation."""
    __tablename__ = 'ultralytics_detections'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    image_id = Column(Integer, ForeignKey('images.id'), nullable=False)
    has_bench = Column(Boolean, nullable=False)
    bench_count = Column(Integer, default=0)
    max_confidence = Column(Float, default=0.0)
    full_response = Column(JSON)  # JSON column for complete Ultralytics API response
    bench_detections = Column(JSON)  # JSON column for bench-specific detections with segmentation
    detection_success = Column(Boolean, nullable=False)
    detection_error = Column(Text, nullable=True)
    model_url = Column(String, nullable=True)
    confidence_threshold = Column(Float, nullable=False)
    iou_threshold = Column(Float, nullable=False)
    image_size = Column(Integer, nullable=False)
    inference_time = Column(Float, nullable=True)
    preprocess_time = Column(Float, nullable=True)
    postprocess_time = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    image = relationship("Image", back_populates="ultralytics_detections")
    
    # Indexes
    __table_args__ = (
        Index('idx_ultralytics_detections_image_id', 'image_id'),
        Index('idx_ultralytics_detections_has_bench', 'has_bench'),
        Index('idx_ultralytics_detections_confidence', 'max_confidence'),
    )
    
    def __repr__(self):
        return f"<UltralyticsDetection(id={self.id}, image_id={self.image_id}, confidence={self.max_confidence})>"


class BenchReport(Base):
    """Model for user reports of bad bench detections."""
    __tablename__ = 'bench_reports'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    bench_id = Column(Integer, ForeignKey('benches.id'), nullable=False)
    image_id = Column(Integer, ForeignKey('images.id'), nullable=True)  # The specific image being reported
    report_type = Column(String, nullable=False, default='bad_detection')  # 'bad_detection', 'incorrect_location', etc.
    description = Column(Text, nullable=True)  # Optional user description
    user_agent = Column(String, nullable=True)  # Browser/app info for debugging
    ip_address = Column(String, nullable=True)  # For potential spam prevention
    user_location_lat = Column(Float, nullable=True)  # User's location when reporting
    user_location_lng = Column(Float, nullable=True)
    reported_image_filename = Column(String, nullable=True)  # Copy of the image being reported
    extra_metadata = Column(JSON, nullable=True)  # Additional metadata (device info, etc.)
    status = Column(String, default='pending')  # 'pending', 'reviewed', 'resolved', 'dismissed'
    admin_notes = Column(Text, nullable=True)  # Admin notes for review
    created_at = Column(DateTime, default=func.now())
    reviewed_at = Column(DateTime, nullable=True)
    
    # Relationships
    bench = relationship("Bench")
    image = relationship("Image")
    
    # Indexes
    __table_args__ = (
        Index('idx_bench_reports_bench_id', 'bench_id'),
        Index('idx_bench_reports_image_id', 'image_id'),
        Index('idx_bench_reports_status', 'status'),
        Index('idx_bench_reports_created_at', 'created_at'),
        Index('idx_bench_reports_type', 'report_type'),
    )
    
    def __repr__(self):
        return f"<BenchReport(id={self.id}, bench_id={self.bench_id}, type='{self.report_type}', status='{self.status}')>"


class MissingBenchReport(Base):
    """Model for user reports of missing benches."""
    __tablename__ = 'missing_bench_reports'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lat = Column(Float, nullable=False)  # Reported bench location
    lng = Column(Float, nullable=False)
    description = Column(Text, nullable=True)  # User description of the bench
    user_agent = Column(String, nullable=True)  # Browser/app info
    ip_address = Column(String, nullable=True)  # For potential spam prevention
    user_location_lat = Column(Float, nullable=True)  # User's GPS location when reporting
    user_location_lng = Column(Float, nullable=True)
    location_method = Column(String, nullable=False, default='gps')  # 'gps', 'map_click'
    uploaded_image_filename = Column(String, nullable=True)  # User-uploaded photo of the bench
    accuracy_meters = Column(Float, nullable=True)  # GPS accuracy if available
    extra_metadata = Column(JSON, nullable=True)  # Additional metadata (device info, etc.)
    status = Column(String, default='pending')  # 'pending', 'verified', 'added', 'dismissed'
    admin_notes = Column(Text, nullable=True)  # Admin notes for review
    created_at = Column(DateTime, default=func.now())
    reviewed_at = Column(DateTime, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_missing_bench_reports_location', 'lat', 'lng'),
        Index('idx_missing_bench_reports_status', 'status'),
        Index('idx_missing_bench_reports_created_at', 'created_at'),
        Index('idx_missing_bench_reports_method', 'location_method'),
    )
    
    def __repr__(self):
        return f"<MissingBenchReport(id={self.id}, location=({self.lat}, {self.lng}), status='{self.status}')>"


# Database configuration
def create_database_engine(database_path: str):
    """Create SQLAlchemy engine for the database."""
    engine = create_engine(f'sqlite:///{database_path}', echo=False)
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
