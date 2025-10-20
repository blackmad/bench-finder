"""
Image download and caching service for bench candidates.

This service handles only the image capture and database storage
for bench candidates without any detection logic.
"""

import logging

from core.streetview import StreetViewClient
from generators.bench_generator import BenchCandidate
from services.database import BenchDatabase
from utils import ProgressTracker

from models.schemas import (
    BenchCreate,
    BenchProcessingResult,
    ImageCreate,
    ProcessingStats,
)

from ..models.enums import BenchCandidateStatus


logger = logging.getLogger(__name__)


class ImageDownloadService:
    """Service for downloading and caching images for bench candidates."""

    def __init__(self):
        """Initialize the image download service."""
        self.streetview_client = StreetViewClient()
        self.database = BenchDatabase()

        logger.info("ImageDownloadService initialized for image downloading and caching")

    def process_benches(
        self, search_id: int, benches: list[BenchCandidate]
    ) -> ProcessingStats:
        """
        Process each bench: capture images and store in database.

        Args:
            search_id: Database search ID
            benches: List of bench candidates from various sources (OSM, Mapillary, etc.)

        Returns:
            ProcessingStats with processing results summary
        """
        progress = ProgressTracker(len(benches), "Downloading images")

        stats = ProcessingStats(
            benches_processed=0,
            benches_added=0,
            images_captured=0,
            images_successful=0,
            detections_performed=0,
            benches_detected=0,
            best_confidence=0.0,
        )

        for bench in benches:
            try:
                result = self._process_single_bench(search_id, bench)

                stats.benches_processed += 1
                if result.bench_added:
                    stats.benches_added += 1

                stats.images_captured += result.images_captured
                stats.images_successful += result.images_successful

                progress.update()

            except Exception:
                bench_id = bench.provider_id
                logger.exception(f"Failed to process bench {bench_id}")
                import traceback

                logger.debug(
                    f"Full traceback for bench {bench_id}:\n{traceback.format_exc()}"
                )
                logger.debug(f"Bench data that caused the error: {bench}")
                progress.update()
                continue

        progress.finish()

        logger.info(
            f"Image download complete - {stats.benches_added}/{stats.benches_processed} "
            f"benches processed with {stats.images_successful}/{stats.images_captured} images captured"
        )

        return stats

    def process_benches_with_progress(
        self, search_id: int, benches: list[BenchCandidate], progress, task
    ) -> ProcessingStats:
        """
        Process each bench: capture images and store in database with progress bar.

        Args:
            search_id: Database search ID
            benches: List of bench candidates from various sources (OSM, Mapillary, etc.)
            progress: Rich Progress object
            task: Rich Progress task ID

        Returns:
            ProcessingStats with processing results summary
        """
        stats = ProcessingStats(
            benches_processed=0,
            benches_added=0,
            images_captured=0,
            images_successful=0,
            detections_performed=0,
            benches_detected=0,
            best_confidence=0.0,
        )

        for bench in benches:
            try:
                result = self._process_single_bench(search_id, bench)

                stats.benches_processed += 1
                if result.bench_added:
                    stats.benches_added += 1

                stats.images_captured += result.images_captured
                stats.images_successful += result.images_successful

                progress.update(task, advance=1)

            except Exception:
                bench_id = bench.provider_id
                logger.exception(f"Failed to process bench {bench_id}")
                import traceback

                logger.debug(
                    f"Full traceback for bench {bench_id}:\n{traceback.format_exc()}"
                )
                logger.debug(f"Bench data that caused the error: {bench}")
                progress.update(task, advance=1)
                continue

        logger.info(
            f"Image download complete - {stats.benches_added}/{stats.benches_processed} "
            f"benches processed with {stats.images_successful}/{stats.images_captured} images captured"
        )

        return stats

    def _process_single_bench(
        self, search_id: int, bench: BenchCandidate
    ) -> BenchProcessingResult:
        """
        Process a single bench: add to DB and capture images.

        Args:
            search_id: Database search ID
            bench: Bench candidate from any source (OSM, Mapillary, etc.)

        Returns:
            BenchProcessingResult for this bench
        """
        result = BenchProcessingResult(
            bench_added=False,
            images_captured=0,
            images_successful=0,
            detections_performed=0,
            bench_detected=False,
            best_confidence=0.0,
        )

        # Validate coordinate types
        try:
            lat = float(bench.lat)
            lng = float(bench.lng)
        except (ValueError, TypeError) as e:
            raise ValueError(
                f"Invalid coordinates in bench data: lat={bench.lat}, lng={bench.lng}. Error: {e}"
            ) from e

        # Add bench to database
        try:
            bench_data = BenchCreate(
                search_id=search_id,
                provider_id=bench.provider_id,
                lat=lat,  # Use validated coordinates
                lng=lng,
                tags=bench.tags,
                source=bench.source,
                external_id=bench.external_id,
            )
            bench_id = self.database.add_bench(bench_data)
            if bench_id:
                result.bench_added = True
                logger.debug(f"Added bench {bench.provider_id} as DB record {bench_id}")
            else:
                logger.warning(f"Failed to add bench {bench.provider_id} to database")
                return result
        except Exception as e:
            raise RuntimeError(
                f"Failed to add bench {bench.provider_id} to database: {e}"
            ) from e

        # Generate unique identifier for image filenames
        bench_identifier = bench.provider_id or f"bench_{bench_id}"

        # Capture street view images
        try:
            image_results = self.streetview_client.capture_bench_images(
                lat,
                lng,
                bench_identifier,  # Use validated coordinates
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to capture images for bench {bench.provider_id}: {e}"
            ) from e

        result.images_captured = len(image_results.captures)
        result.images_successful = sum(
            1 for img in image_results.captures if img.success
        )

        # Add all images to database
        for image_capture in image_results.captures:
            try:
                self.database.add_image(
                    ImageCreate(
                        bench_id=bench_id,
                        heading=image_capture.heading,
                        filepath=image_capture.filepath,
                        filename=image_capture.filename,
                        file_size=image_capture.file_size,
                        capture_success=image_capture.success,
                        capture_error=image_capture.error,
                    )
                )

                logger.debug(
                    f"Added image record for bench {bench.provider_id}, heading {image_capture.heading}"
                )

            except Exception:
                logger.exception(
                    f"Failed to add image record for bench {bench.provider_id}, heading {image_capture.heading}"
                )
                continue

        logger.debug(
            f"Processed bench {bench.provider_id}: {result.images_successful}/{result.images_captured} images captured"
        )

        # Update candidate status to image_download_done (even if no images were captured)
        # We need to find the candidate ID from the database
        try:
            with self.database.get_session() as session:
                from models.models import BenchCandidate
                candidate = session.query(BenchCandidate).filter(
                    BenchCandidate.provider_id == bench.provider_id,
                    BenchCandidate.search_id == search_id
                ).first()

                if candidate:
                    # Only update status if it's not already image_download_done or detection_done
                    if candidate.status not in [BenchCandidateStatus.IMAGE_DOWNLOAD_DONE, BenchCandidateStatus.DETECTION_DONE]:
                        self.database.update_bench_candidate_status(candidate.id, BenchCandidateStatus.IMAGE_DOWNLOAD_DONE)
                        logger.debug(f"Updated candidate {candidate.id} status to image_download_done")
                    else:
                        logger.debug(f"Candidate {candidate.id} already has status {candidate.status}, skipping update")
                else:
                    logger.warning(f"Could not find candidate with provider_id {bench.provider_id} to update status")
        except Exception as e:
            logger.warning(f"Failed to update candidate status: {e}")

        return result
