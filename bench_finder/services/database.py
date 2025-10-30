"""
SQLAlchemy ORM operations for storing bench data, images, and detection results.
"""

import logging
import os
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.api_models import (
    BenchWithDetections,
    DetectionResponse,
    ImageWithDetections,
    SearchResponse,
    SearchResults,
)
from bench_finder.config import DATABASE_PATH
from bench_finder.models.enums import DataSource
from bench_finder.models.unified_models import (
    Bench,
    BenchBase,
    BenchCandidate,
    BenchCandidateStatus,
    DetectedBench,
    Detection,
    DetectionBase,
    DetectionItem,
    Image,
    ImageBase,
    Search,
    SearchBase,
    SearchStatus,
    create_database_session,
    init_database,
)


logger = logging.getLogger(__name__)


class BenchDatabase:
    """SQLAlchemy ORM database manager for bench finder application."""

    def __init__(self, db_path: str | None = None):
        """
        Initialize database connection and create tables if needed.

        Args:
            db_path: Path to SQLite database file (defaults to config DATABASE_PATH)
        """
        self.db_path = db_path or DATABASE_PATH

        # Ensure the data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Initialize database
        self.engine = init_database(self.db_path)

        logger.info(f"Database initialized at {self.db_path}")

    def get_session(self) -> Session:
        """Get a database session."""
        return create_database_session(self.engine)

    # Database initialization is now handled in __init__ using SQLAlchemy

    def create_search(self, search_data: SearchBase) -> int:
        """
        Create a new search record.

        Args:
            search_data: SearchBase schema with search parameters

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

    def add_bench(self, bench_data: BenchBase, search_id: int | None = None) -> int:
        """
        Add a bench record to the database.

        Args:
            bench_data: BenchBase schema with bench data from OSM
            search_id: Optional search ID to associate with the bench

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
                    search_id=search_id,
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

    def add_image(self, image_data: ImageBase, bench_id: int) -> int:
        """
        Add an image record to the database.

        Args:
            image_data: ImageBase schema with image capture results
            bench_id: ID of the bench this image belongs to

        Returns:
            The ID of the created image record
        """
        try:
            with self.get_session() as session:
                image = Image(
                    bench_id=bench_id,
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

    def add_detection(self, detection_data: DetectionBase, image_id: int) -> int:
        """
        Add a detection record to the database.

        Args:
            detection_data: DetectionBase schema with detection results
            image_id: ID of the image this detection belongs to

        Returns:
            The ID of the created detection record
        """
        try:
            with self.get_session() as session:
                detection = Detection(
                    image_id=image_id,
                    has_bench=detection_data.has_bench,
                    bench_count=detection_data.bench_count,
                    max_confidence=detection_data.max_confidence,
                    detection_success=detection_data.detection_success,
                    detection_error=detection_data.detection_error,
                    model_id=detection_data.model_id,
                    confidence_threshold=detection_data.confidence_threshold,
                    source=detection_data.source,
                    external_detection_id=detection_data.external_detection_id,
                    # Ultralytics-specific fields
                    # full_response=detection_data.full_response,
                    # bench_detections=detection_data.bench_detections,
                    model_url=detection_data.model_url,
                    iou_threshold=detection_data.iou_threshold,
                    image_size=detection_data.image_size,
                    inference_time=detection_data.inference_time,
                    preprocess_time=detection_data.preprocess_time,
                    postprocess_time=detection_data.postprocess_time,
                )
                session.add(detection)
                session.commit()
                session.refresh(detection)

                # Add detection items if they exist
                if hasattr(detection_data, "detection_items"):
                    for item_data in detection_data.detection_items:
                        detection_item = DetectionItem(
                            detection_id=detection.id,
                            image_id=detection.image_id,
                            confidence=item_data.confidence,
                            bbox=item_data.bbox,
                            class_name=item_data.class_name,
                            polygon=item_data.polygon,
                        )
                        session.add(detection_item)

                session.commit()

                logger.debug(
                    f"Added detection record {detection.id} for image {detection_data.image_id} with {len(detection_data.detection_items)} detection items"
                )
                return detection.id

        except Exception:
            logger.exception("Error adding detection record")
            raise

    def update_search_status(
        self,
        search_id: int,
        status: SearchStatus,
        completed_at: datetime | None = None,
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

    def get_search_results(self, search_id: int) -> SearchResults | None:
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
                                DetectionResponse(
                                    id=d.id,
                                    image_id=d.image_id,
                                    has_bench=d.has_bench,
                                    bench_count=d.bench_count,
                                    max_confidence=d.max_confidence,
                                    detection_success=d.detection_success,
                                    detection_error=d.detection_error,
                                    model_id=d.model_id,
                                    confidence_threshold=d.confidence_threshold,
                                    source=d.source,
                                    external_detection_id=d.external_detection_id,
                                    model_url=d.model_url,
                                    iou_threshold=d.iou_threshold,
                                    image_size=d.image_size,
                                    inference_time=d.inference_time,
                                    preprocess_time=d.preprocess_time,
                                    postprocess_time=d.postprocess_time,
                                    created_at=d.created_at,
                                    detection_items=d.detection_items,
                                )
                                for d in image.detections
                            ],
                        )
                        for image in bench.images
                    ]

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
        source: DataSource,
        external_id: str | None = None,
        confidence: float | None = None,
    ) -> int | None:
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
                candidate = (
                    session.query(BenchCandidate)
                    .filter(BenchCandidate.id == candidate_id)
                    .first()
                )

                if candidate:
                    candidate.status = status
                    session.commit()
                    logger.debug(f"Updated candidate {candidate_id} status to {status}")
                    return True
                else:
                    logger.warning(f"Candidate {candidate_id} not found")
                    return False

        except Exception:
            logger.exception(
                f"Error updating candidate {candidate_id} status to {status}"
            )
            return False

    def get_bench_candidates_by_status(
        self,
        status: BenchCandidateStatus,
        search_id: int | None = None,
    ) -> list[BenchCandidate]:
        """
        Get bench candidates for a search filtered by status.

        Args:
            search_id: ID of the search
            status: Status to filter by ('pending', 'image_download_done', 'detection_done')

        Returns:
            List of BenchCandidate objects with the specified status
        """

        with self.get_session() as session:
            query = session.query(BenchCandidate)
            if search_id:
                query = query.filter(BenchCandidate.search_id == search_id)
            query = query.filter(BenchCandidate.status == status)
            candidates = query.all()
            return candidates

    def get_latest_search_id(self) -> int | None:
        """
        Get the ID of the most recently created search.

        Returns:
            The latest search ID, or None if no searches exist
        """
        try:
            with self.get_session() as session:
                latest_search = session.query(Search).order_by(Search.id.desc()).first()
                return latest_search.id if latest_search else None

        except Exception:
            logger.exception("Error getting latest search ID")
            return None

    def clear_detections_table(self) -> int:
        """
        Clear all records from the detections table.

        Returns:
            Number of detections that were deleted
        """
        try:
            with self.get_session() as session:
                # Count detections before deletion
                count = session.query(Detection).count()

                # Delete all detections
                session.query(Detection).delete()
                session.commit()

                logger.info(f"Cleared {count} detections from database")
                return count

        except Exception:
            logger.exception("Error clearing detections table")
            return 0

    def upsert_detected_bench(
        self, bench_id: int, image_id: int, confidence: float
    ) -> int:
        """
        Create or update the best detected image for a bench.

        Ensures at most one row per bench in detected_benches.

        Returns the DetectedBench.id
        """
        try:
            with self.get_session() as session:
                existing = (
                    session.query(DetectedBench)
                    .filter(DetectedBench.bench_id == bench_id)
                    .first()
                )

                if existing:
                    existing.image_id = image_id
                    existing.confidence = confidence
                    session.commit()
                    session.refresh(existing)
                    logger.debug(
                        f"Updated DetectedBench for bench {bench_id} -> image {image_id} (confidence {confidence:.2f})"
                    )
                    return existing.id or 0

                row = DetectedBench(
                    bench_id=bench_id,
                    image_id=image_id,
                    confidence=confidence,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                logger.debug(
                    f"Inserted DetectedBench for bench {bench_id} -> image {image_id} (confidence {confidence:.2f})"
                )
                return row.id or 0
        except Exception:
            logger.exception("Error upserting DetectedBench record")
            raise

    def reset_bench_candidate_detection_status(self) -> int:
        """
        Reset bench candidate status from DETECTION_DONE to IMAGE_DOWNLOAD_DONE.

        Returns:
            Number of candidates that were reset
        """
        try:
            with self.get_session() as session:
                # Find all candidates with DETECTION_DONE status
                candidates_to_reset = (
                    session.query(BenchCandidate)
                    .filter(
                        BenchCandidate.status == BenchCandidateStatus.DETECTION_DONE
                    )
                    .all()
                )

                count = len(candidates_to_reset)

                # Update their status to IMAGE_DOWNLOAD_DONE
                for candidate in candidates_to_reset:
                    candidate.status = BenchCandidateStatus.IMAGE_DOWNLOAD_DONE

                session.commit()

                logger.info(
                    f"Reset {count} bench candidates from DETECTION_DONE to IMAGE_DOWNLOAD_DONE"
                )
                return count

        except Exception:
            logger.exception("Error resetting bench candidate detection status")
            return 0

    def get_random_streetview_image(self) -> Image | None:
        """
        Get a random streetview image that was successfully captured.

        Returns:
            Random Image object with successful capture, or None if no images found
        """
        try:
            with self.get_session() as session:
                # Get a random image that was successfully captured
                random_image = (
                    session.query(Image)
                    .filter(Image.capture_success)
                    .filter(Image.filepath.isnot(None))
                    .order_by(func.random())
                    .first()
                )

                if random_image:
                    logger.debug(f"Selected random image: {random_image.filename}")
                    return random_image
                else:
                    logger.warning("No successful streetview images found in database")
                    return None

        except Exception:
            logger.exception("Error getting random streetview image")
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
