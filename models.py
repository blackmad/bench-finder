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
    """Model for OSM bench data."""
    __tablename__ = 'benches'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    search_id = Column(Integer, ForeignKey('searches.id'), nullable=False)
    osm_id = Column(Integer, nullable=False)
    osm_type = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    tags = Column(JSON)  # JSON column for OSM tags
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    search = relationship("Search", back_populates="benches")
    images = relationship("Image", back_populates="bench", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_benches_search_id', 'search_id'),
        Index('idx_benches_osm', 'osm_id', 'osm_type'),
        Index('idx_benches_location', 'lat', 'lng'),
    )
    
    def __repr__(self):
        return f"<Bench(id={self.id}, osm_id={self.osm_id}, osm_type='{self.osm_type}')>"


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
    bench = relationship("Bench", back_populates="images")
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
    """Model for Roboflow detection results."""
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
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    image = relationship("Image", back_populates="detections")
    
    # Indexes
    __table_args__ = (
        Index('idx_detections_image_id', 'image_id'),
        Index('idx_detections_has_bench', 'has_bench'),
        Index('idx_detections_confidence', 'max_confidence'),
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
    model_url = Column(String, nullable=False)
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