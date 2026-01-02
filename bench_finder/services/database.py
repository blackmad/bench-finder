"""
SQLAlchemy ORM operations for storing bench data, images, and detection results.
"""

import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func
from sqlalchemy.orm import Session


if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

from bench_finder.config import DATABASE_PATH, DATABASE_URL
from bench_finder.models.enums import DataSource
from bench_finder.models.unified_models import (
    BenchBase,
    BenchCandidate,
    BenchCandidateStatus,
    Detection,
    DetectionBase,
    DetectionItem,
    Image,
    ImageBase,
    ProcessedBench,
    ReverseGeocode,
    Search,
    SearchBase,
    SearchStatus,
    create_database_session,
    init_database,
)


logger = logging.getLogger(__name__)


class BenchDatabase:
    """SQLAlchemy ORM database manager for bench finder application."""

    def __init__(
        self,
        db_path: str | None = None,
        db_url: str | None = None,
        engine: "Engine | None" = None,
    ):
        """
        Initialize database connection and create tables if needed.

        Args:
            db_path: Path to SQLite database file (defaults to config DATABASE_PATH)
            db_url: Full database connection URL (e.g., postgresql://... or sqlite:///...)
                    Takes precedence over db_path if provided
            engine: Optional SQLAlchemy engine to reuse (avoids re-initialization)
        """
        # If engine is provided, reuse it (no initialization needed)
        if engine is not None:
            self.engine = engine
            self.db_url = None
            self.db_path = None
            return

        # Use provided db_url, or DATABASE_URL from config, or fall back to db_path/DATABASE_PATH
        if db_url:
            self.db_url = db_url
            self.db_path = None
        elif DATABASE_URL:
            self.db_url = DATABASE_URL
            self.db_path = None
        else:
            self.db_path = db_path or DATABASE_PATH
            self.db_url = None
            # Ensure the data directory exists for SQLite
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Initialize database
        self.engine = init_database(
            database_url=self.db_url, database_path=self.db_path
        )

        db_info = self.db_url if self.db_url else self.db_path
        logger.info(f"Database initialized: {db_info}")

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
                        session.query(BenchCandidate)
                        .filter(
                            BenchCandidate.provider_id == bench_data.provider_id,
                            BenchCandidate.source == bench_data.source,
                        )
                        .first()
                    )

                if existing_bench:
                    logger.debug(
                        f"Bench {bench_data.provider_id} already exists as record {existing_bench.id}"
                    )
                    return existing_bench.id

                bench = BenchCandidate(
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
                    bench_candidate_id=bench_id,
                    heading=image_data.heading,
                    filepath=image_data.filepath,
                    filename=image_data.filename,
                    file_size=image_data.file_size,
                    capture_success=image_data.capture_success,
                    capture_error=image_data.capture_error,
                    image_source=image_data.image_source,
                    panorama_lat=image_data.panorama_lat,
                    panorama_lng=image_data.panorama_lng,
                    panorama_metadata=image_data.panorama_metadata,
                    panorama_heading=image_data.panorama_heading,
                )
                session.add(image)
                session.commit()
                session.refresh(image)

                logger.debug(
                    f"Added image record {image.id} for bench candidate {bench_id}, heading {image_data.heading}, source {image_data.image_source}"
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
    ) -> None:
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
        Create or update the best detected image for a bench candidate.

        Args:
            bench_id: bench_candidate_id (legacy parameter name kept for compatibility)
            image_id: ID of the best image
            confidence: Confidence score

        Returns the ProcessedBench.id
        """
        try:
            with self.get_session() as session:
                # Get the best detection for this image (highest confidence)
                best_detection = (
                    session.query(Detection)
                    .filter(Detection.image_id == image_id)
                    .order_by(Detection.max_confidence.desc())
                    .first()
                )

                existing = (
                    session.query(ProcessedBench)
                    .filter(ProcessedBench.bench_candidate_id == bench_id)
                    .first()
                )

                if existing:
                    existing.best_image_id = image_id
                    existing.best_detection_id = (
                        best_detection.id if best_detection else None
                    )
                    existing.detection_status = "detected"
                    session.commit()
                    session.refresh(existing)
                    logger.debug(
                        f"Updated ProcessedBench for bench candidate {bench_id} -> image {image_id} (confidence {confidence:.2f})"
                    )
                    return existing.id or 0

                row = ProcessedBench(
                    bench_candidate_id=bench_id,
                    best_image_id=image_id,
                    best_detection_id=best_detection.id if best_detection else None,
                    detection_status="detected",
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                logger.debug(
                    f"Inserted ProcessedBench for bench candidate {bench_id} -> image {image_id} (confidence {confidence:.2f})"
                )
                return row.id or 0
        except Exception:
            logger.exception("Error upserting ProcessedBench record")
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

    def reset_bench_candidate_image_status(self) -> int:
        """
        Reset bench candidate status from IMAGE_DOWNLOAD_DONE or DETECTION_DONE to PENDING.
        This allows re-downloading images without deleting existing ones.

        Returns:
            Number of candidates that were reset
        """
        try:
            with self.get_session() as session:
                # Find all candidates with IMAGE_DOWNLOAD_DONE or DETECTION_DONE status
                candidates_to_reset = (
                    session.query(BenchCandidate)
                    .filter(
                        BenchCandidate.status.in_(
                            [
                                BenchCandidateStatus.IMAGE_DOWNLOAD_DONE,
                                BenchCandidateStatus.DETECTION_DONE,
                            ]
                        )
                    )
                    .all()
                )

                count = len(candidates_to_reset)

                # Update their status to PENDING
                for candidate in candidates_to_reset:
                    candidate.status = BenchCandidateStatus.PENDING

                session.commit()

                logger.info(f"Reset {count} bench candidates to PENDING status")
                return count

        except Exception:
            logger.exception("Error resetting bench candidate image status")
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

    def add_or_update_reverse_geocode(
        self,
        bench_candidate_id: int,
        formatted_address: str,
        street_number: str | None = None,
        street_name: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        country: str | None = None,
        raw_response: dict[str, Any] | None = None,
    ) -> int | None:
        """
        Add or update reverse geocode for a bench candidate.

        Args:
            bench_candidate_id: ID of the bench candidate
            formatted_address: Formatted address string from reverse geocoding
            street_number: Street number (optional)
            street_name: Street name/route (optional)
            city: City/locality (optional)
            state: State/administrative area (optional)
            postal_code: Postal/ZIP code (optional)
            country: Country code (optional)
            raw_response: Optional raw API response for future reference

        Returns:
            ID of the created/updated reverse geocode record, or None if failed
        """
        try:
            with self.get_session() as session:
                # Check if reverse geocode already exists
                existing = (
                    session.query(ReverseGeocode)
                    .filter(ReverseGeocode.bench_candidate_id == bench_candidate_id)
                    .first()
                )

                if existing:
                    # Update existing record
                    existing.formatted_address = formatted_address
                    existing.street_number = street_number
                    existing.street_name = street_name
                    existing.city = city
                    existing.state = state
                    existing.postal_code = postal_code
                    existing.country = country
                    existing.raw_response = raw_response
                    existing.updated_at = datetime.now()
                    session.commit()
                    session.refresh(existing)
                    logger.debug(
                        f"Updated reverse geocode for bench candidate {bench_candidate_id}"
                    )
                    return existing.id
                else:
                    # Create new record
                    reverse_geocode = ReverseGeocode(
                        bench_candidate_id=bench_candidate_id,
                        formatted_address=formatted_address,
                        street_number=street_number,
                        street_name=street_name,
                        city=city,
                        state=state,
                        postal_code=postal_code,
                        country=country,
                        raw_response=raw_response,
                    )
                    session.add(reverse_geocode)
                    session.commit()
                    session.refresh(reverse_geocode)
                    logger.debug(
                        f"Added reverse geocode for bench candidate {bench_candidate_id}: {formatted_address[:50]}..."
                    )
                    return reverse_geocode.id

        except Exception:
            logger.exception(
                f"Error adding/updating reverse geocode for bench candidate {bench_candidate_id}"
            )
            return None

    def get_reverse_geocode(self, bench_candidate_id: int) -> ReverseGeocode | None:
        """
        Get reverse geocode for a bench candidate.

        Args:
            bench_candidate_id: ID of the bench candidate

        Returns:
            ReverseGeocode object if found, None otherwise
        """
        try:
            with self.get_session() as session:
                reverse_geocode = (
                    session.query(ReverseGeocode)
                    .filter(ReverseGeocode.bench_candidate_id == bench_candidate_id)
                    .first()
                )
                return reverse_geocode

        except Exception:
            logger.exception(
                f"Error getting reverse geocode for bench candidate {bench_candidate_id}"
            )
            return None

    def get_bench_candidates_without_reverse_geocode(
        self, limit: int | None = None
    ) -> list[BenchCandidate]:
        """
        Get bench candidates that don't have reverse geocode yet.

        Args:
            limit: Optional limit on number of candidates to return

        Returns:
            List of BenchCandidate objects without reverse geocode
        """
        try:
            with self.get_session() as session:
                # Get candidates that don't have a reverse geocode
                query = (
                    session.query(BenchCandidate)
                    .outerjoin(ReverseGeocode)
                    .filter(ReverseGeocode.id.is_(None))
                )

                if limit:
                    query = query.limit(limit)

                candidates = query.all()
                return candidates

        except Exception:
            logger.exception("Error getting bench candidates without reverse geocode")
            return []

    def close(self) -> None:
        """Close database connection if needed."""
        # Using SQLAlchemy sessions with context managers, connections are automatically closed

    # Additional helper methods for web server compatibility
    def _get_connection(self) -> Any:
        """Legacy compatibility method for web server."""
        # For now, return a simple sqlite3 connection for backward compatibility
        # This will be removed once web_server.py is fully updated
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
