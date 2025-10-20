"""
SQLAlchemy ORM operations for storing bench data, images, and detection results.
"""

import logging
import os
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..config import DATABASE_PATH
from ..models.models import (
    Base,
    Bench,
    BenchCandidate,
    Detection,
    Image,
    Search,
    UltralyticsDetection,
    create_database_engine,
    create_database_session,
)
from ..models.schemas import (
    BenchCreate,
    BenchWithDetections,
    DetectionCreate,
    DetectionResponse,
    ImageCreate,
    ImageWithDetections,
    SearchCreate,
    SearchResponse,
    SearchResults,
    UltralyticsDetectionCreate,
    UltralyticsDetectionResponse,
)


logger = logging.getLogger(__name__)


class BenchDatabase:
    """SQLAlchemy ORM database manager for bench finder application."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection and create tables if needed.

        Args:
            db_path: Path to SQLite database file (defaults to config DATABASE_PATH)
        """
        self.db_path = db_path or DATABASE_PATH

        # Ensure the data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Initialize database
        self.engine = create_database_engine(self.db_path)
        Base.metadata.create_all(self.engine)

        logger.info(f"Database initialized at {self.db_path}")

    def get_session(self) -> Session:
        """Get a database session."""
        return create_database_session(self.engine)

    # Database initialization is now handled in __init__ using SQLAlchemy

    def create_search(self, search_data: SearchCreate) -> int:
        """
        Create a new search record.

        Args:
            search_data: SearchCreate schema with search parameters

        Returns:
            The ID of the created search record
        """
        try:
            with self.get_session() as session:
                search = Search(
                    query=search_data.query,
                    start_lat=search_data.start_lat,
                    start_lng=search_data.start_lng,
                    search_radius=search_data.search_radius,
                )
                session.add(search)
                session.commit()
                session.refresh(search)

                logger.info(
                    f"Created search record {search.id} for query: {search_data.query}"
                )
                return search.id

        except Exception:
            logger.exception("Error creating search record")
            raise

    def add_bench(self, bench_data: BenchCreate) -> int:
        """
        Add a bench record to the database.

        Args:
            bench_data: BenchCreate schema with bench data from OSM

        Returns:
            The ID of the created bench record
        """
        try:
            with self.get_session() as session:
                # Check if bench already exists by provider_id
                existing_bench = None
                if bench_data.provider_id:
                    existing_bench = (
                        session.query(Bench)
                        .filter(
                            Bench.provider_id == bench_data.provider_id,
                            Bench.source == bench_data.source,
                        )
                        .first()
                    )

                if existing_bench:
                    logger.debug(
                        f"Bench {bench_data.provider_id} already exists as record {existing_bench.id}"
                    )
                    return existing_bench.id

                bench = Bench(
                    search_id=bench_data.search_id,
                    provider_id=bench_data.provider_id,
                    lat=bench_data.lat,
                    lng=bench_data.lng,
                    tags=bench_data.tags,
                    source=bench_data.source,
                    external_id=bench_data.external_id,
                )
                session.add(bench)
                session.commit()
                session.refresh(bench)

                logger.debug(
                    f"Added bench {bench_data.provider_id} as record {bench.id}"
                )
                return bench.id

        except Exception:
            logger.exception("Error adding bench record")
            raise

    def add_image(self, image_data: ImageCreate) -> int:
        """
        Add an image record to the database.

        Args:
            image_data: ImageCreate schema with image capture results

        Returns:
            The ID of the created image record
        """
        try:
            with self.get_session() as session:
                image = Image(
                    bench_id=image_data.bench_id,
                    heading=image_data.heading,
                    filepath=image_data.filepath,
                    filename=image_data.filename,
                    file_size=image_data.file_size,
                    capture_success=image_data.capture_success,
                    capture_error=image_data.capture_error,
                )
                session.add(image)
                session.commit()
                session.refresh(image)

                logger.debug(
                    f"Added image record {image.id} for bench {image_data.bench_id}, heading {image_data.heading}"
                )
                return image.id

        except Exception:
            logger.exception("Error adding image record")
            raise

    def add_detection(self, detection_data: DetectionCreate) -> int:
        """
        Add a detection record to the database.

        Args:
            detection_data: DetectionCreate schema with detection results

        Returns:
            The ID of the created detection record
        """
        try:
            with self.get_session() as session:
                detection = Detection(
                    image_id=detection_data.image_id,
                    has_bench=detection_data.has_bench,
                    bench_count=detection_data.bench_count,
                    max_confidence=detection_data.max_confidence,
                    detections=detection_data.detections,
                    detection_success=detection_data.detection_success,
                    detection_error=detection_data.detection_error,
                    model_id=detection_data.model_id,
                    confidence_threshold=detection_data.confidence_threshold,
                )
                session.add(detection)
                session.commit()
                session.refresh(detection)

                logger.debug(
                    f"Added detection record {detection.id} for image {detection_data.image_id}"
                )
                return detection.id

        except Exception:
            logger.exception("Error adding detection record")
            raise

    def add_ultralytics_detection(
        self, detection_data: UltralyticsDetectionCreate
    ) -> int:
        """
        Add an Ultralytics detection record to the database.

        Args:
            detection_data: UltralyticsDetectionCreate schema with detection results

        Returns:
            The ID of the created detection record
        """
        try:
            with self.get_session() as session:
                detection = UltralyticsDetection(
                    image_id=detection_data.image_id,
                    has_bench=detection_data.has_bench,
                    bench_count=detection_data.bench_count,
                    max_confidence=detection_data.max_confidence,
                    full_response=detection_data.full_response,
                    bench_detections=detection_data.bench_detections,
                    detection_success=detection_data.detection_success,
                    detection_error=detection_data.detection_error,
                    model_url=detection_data.model_url,
                    confidence_threshold=detection_data.confidence_threshold,
                    iou_threshold=detection_data.iou_threshold,
                    image_size=detection_data.image_size,
                    inference_time=detection_data.inference_time,
                    preprocess_time=detection_data.preprocess_time,
                    postprocess_time=detection_data.postprocess_time,
                )
                session.add(detection)
                session.commit()
                session.refresh(detection)

                logger.debug(
                    f"Added Ultralytics detection record {detection.id} for image {detection_data.image_id}"
                )
                return detection.id

        except Exception:
            logger.exception("Error adding Ultralytics detection record")
            raise

    def update_search_status(
        self, search_id: int, status: str, completed_at: Optional[datetime] = None
    ):
        """
        Update the status of a search record.

        Args:
            search_id: ID of the search record
            status: New status ('pending', 'completed', 'failed')
            completed_at: Completion timestamp (defaults to current time)
        """
        try:
            if completed_at is None:
                completed_at = datetime.now()

            with self.get_session() as session:
                search = session.query(Search).filter(Search.id == search_id).first()
                if search:
                    search.status = status
                    search.completed_at = completed_at
                    session.commit()
                    logger.debug(f"Updated search {search_id} status to {status}")
                else:
                    logger.warning(f"Search {search_id} not found for status update")

        except Exception:
            logger.exception("Error updating search status")
            raise

    def get_search_results(self, search_id: int) -> Optional[SearchResults]:
        """
        Get comprehensive results for a search.

        Args:
            search_id: ID of the search

        Returns:
            SearchResults schema with search results and statistics
        """
        try:
            with self.get_session() as session:
                # Get search info
                search = session.query(Search).filter(Search.id == search_id).first()

                if not search:
                    return None

                # Get bench count
                bench_count = (
                    session.query(Bench).filter(Bench.search_id == search_id).count()
                )

                # Get image stats
                image_stats = (
                    session.query(
                        func.count(Image.id).label("total_images"),
                        func.sum(Image.capture_success).label("successful_images"),
                    )
                    .join(Bench, Image.bench_id == Bench.id)
                    .filter(Bench.search_id == search_id)
                    .first()
                )

                # Get detection stats
                detection_stats = (
                    session.query(
                        func.count(Detection.id).label("total_detections"),
                        func.sum(Detection.has_bench).label("images_with_benches"),
                        func.max(Detection.max_confidence).label("best_confidence"),
                    )
                    .join(Image, Detection.image_id == Image.id)
                    .join(Bench, Image.bench_id == Bench.id)
                    .filter(Bench.search_id == search_id)
                    .first()
                )

                return SearchResults(
                    search=SearchResponse(
                        id=search.id,
                        query=search.query,
                        start_lat=search.start_lat,
                        start_lng=search.start_lng,
                        search_radius=search.search_radius,
                        created_at=search.created_at,
                        completed_at=search.completed_at,
                        status=search.status,
                    ),
                    bench_count=bench_count,
                    total_images=image_stats.total_images if image_stats else 0,
                    successful_images=image_stats.successful_images
                    if image_stats
                    else 0,
                    total_detections=detection_stats.total_detections
                    if detection_stats
                    else 0,
                    images_with_benches=detection_stats.images_with_benches
                    if detection_stats
                    else 0,
                    best_confidence=detection_stats.best_confidence
                    if detection_stats
                    else 0.0,
                )

        except Exception:
            logger.exception("Error getting search results")
            return None

    def get_benches_with_detections(self, search_id: int) -> list[BenchWithDetections]:
        """
        Get all benches with their images and detections for a search.

        Args:
            search_id: ID of the search

        Returns:
            List of BenchWithDetections schemas with nested image and detection data
        """
        try:
            with self.get_session() as session:
                # Get all benches for this search with eagerly loaded relationships
                benches = (
                    session.query(Bench).filter(Bench.search_id == search_id).all()
                )

                result = []
                for bench in benches:
                    # Get images with their detections
                    images_with_detections = [
                            ImageWithDetections(
                                id=image.id,
                                bench_id=image.bench_id,
                                heading=image.heading,
                                filepath=image.filepath,
                                filename=image.filename,
                                file_size=image.file_size,
                                capture_success=image.capture_success,
                                capture_error=image.capture_error,
                                created_at=image.created_at,
                                detections=[
                                    DetectionResponse.model_validate(d)
                                    for d in image.detections
                                ],
                                ultralytics_detections=[
                                    UltralyticsDetectionResponse.model_validate(d)
                                    for d in image.ultralytics_detections
                                ],
                            )
                        for image in bench.images]

                    bench_with_detections = BenchWithDetections(
                        id=bench.id,
                        search_id=bench.search_id,
                        provider_id=bench.provider_id,
                        lat=bench.lat,
                        lng=bench.lng,
                        tags=bench.tags or {},
                        source=bench.source,
                        external_id=bench.external_id,
                        created_at=bench.created_at,
                        images=images_with_detections,
                    )
                    result.append(bench_with_detections)

                return result

        except Exception:
            logger.exception("Error getting benches with detections")
            return []

    def add_bench_candidate(
        self,
        search_id: int,
        provider_id: str,
        lat: float,
        lng: float,
        tags: dict,
        source: str,
        external_id: Optional[str] = None,
        confidence: Optional[float] = None,
    ) -> Optional[int]:
        """
        Add a bench candidate to the database.

        Args:
            search_id: ID of the search this candidate belongs to
            provider_id: Unified ID from OSM or Mapillary
            lat: Latitude
            lng: Longitude
            tags: JSON tags/metadata
            source: Source of the candidate ('osm', 'mapillary', etc.)
            external_id: External ID if applicable
            confidence: Confidence score if available

        Returns:
            ID of the created bench candidate, or None if failed
        """
        try:
            with self.get_session() as session:
                candidate = BenchCandidate(
                    search_id=search_id,
                    provider_id=provider_id,
                    lat=lat,
                    lng=lng,
                    tags=tags,
                    source=source,
                    external_id=external_id,
                    confidence=confidence,
                )
                session.add(candidate)
                session.commit()
                logger.debug(f"Added bench candidate: {provider_id} from {source}")
                return candidate.id

        except Exception:
            logger.exception("Error adding bench candidate")
            return None

    def get_bench_candidates(self, search_id: int) -> list[BenchCandidate]:
        """
        Get all bench candidates for a search.

        Args:
            search_id: ID of the search

        Returns:
            List of BenchCandidate objects
        """
        try:
            with self.get_session() as session:
                candidates = (
                    session.query(BenchCandidate)
                    .filter(BenchCandidate.search_id == search_id)
                    .all()
                )
                return candidates

        except Exception:
            logger.exception("Error getting bench candidates")
            return []

    def get_bench_candidate_count(self, search_id: int) -> int:
        """
        Get count of bench candidates for a search.

        Args:
            search_id: ID of the search

        Returns:
            Number of bench candidates
        """
        try:
            with self.get_session() as session:
                count = (
                    session.query(BenchCandidate)
                    .filter(BenchCandidate.search_id == search_id)
                    .count()
                )
                return count

        except Exception:
            logger.exception("Error getting bench candidate count")
            return 0

    def update_bench_candidate_status(self, candidate_id: int, status: str) -> bool:
        """
        Update the status of a bench candidate.

        Args:
            candidate_id: ID of the bench candidate
            status: New status ('pending', 'image_download_done', 'detection_done')

        Returns:
            True if update was successful, False otherwise
        """
        try:
            with self.get_session() as session:
                candidate = session.query(BenchCandidate).filter(
                    BenchCandidate.id == candidate_id
                ).first()

                if candidate:
                    candidate.status = status
                    session.commit()
                    logger.debug(f"Updated candidate {candidate_id} status to {status}")
                    return True
                else:
                    logger.warning(f"Candidate {candidate_id} not found")
                    return False

        except Exception:
            logger.exception(f"Error updating candidate {candidate_id} status to {status}")
            return False

    def get_bench_candidates_by_status(self, search_id: int, status: str) -> list[BenchCandidate]:
        """
        Get bench candidates for a search filtered by status.

        Args:
            search_id: ID of the search
            status: Status to filter by ('pending', 'image_download_done', 'detection_done')

        Returns:
            List of BenchCandidate objects with the specified status
        """
        try:
            with self.get_session() as session:
                candidates = (
                    session.query(BenchCandidate)
                    .filter(
                        BenchCandidate.search_id == search_id,
                        BenchCandidate.status == status
                    )
                    .all()
                )
                return candidates

        except Exception:
            logger.exception(f"Error getting bench candidates with status {status}")
            return []

    def get_latest_search_id(self) -> Optional[int]:
        """
        Get the ID of the most recently created search.

        Returns:
            The latest search ID, or None if no searches exist
        """
        try:
            with self.get_session() as session:
                latest_search = (
                    session.query(Search)
                    .order_by(Search.id.desc())
                    .first()
                )
                return latest_search.id if latest_search else None

        except Exception:
            logger.exception("Error getting latest search ID")
            return None

    def close(self):
        """Close database connection if needed."""
        # Using SQLAlchemy sessions with context managers, connections are automatically closed

    # Additional helper methods for web server compatibility
    def _get_connection(self):
        """Legacy compatibility method for web server."""
        # For now, return a simple sqlite3 connection for backward compatibility
        # This will be removed once web_server.py is fully updated
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
