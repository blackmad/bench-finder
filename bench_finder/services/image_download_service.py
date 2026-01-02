"""
Image download and caching service for bench candidates.

This service handles only the image capture and database storage
for bench candidates without any detection logic.
"""

import logging

from bench_finder.core.streetview import StreetViewClient
from bench_finder.generators.bench_generator import BenchCandidate
from bench_finder.models.enums import BenchCandidateStatus
from bench_finder.models.unified_models import (
    BenchBase,
    BenchProcessingResult,
    ImageBase,
    ProcessingStats,
)
from bench_finder.services.database import BenchDatabase
from bench_finder.utils import ProgressTracker


logger = logging.getLogger(__name__)


class ImageDownloadService:
    """Service for downloading and caching images for bench candidates."""

    def __init__(self, cached_only: bool = False, force: bool = False):
        """
        Initialize the image download service.

        Args:
            cached_only: If True, only process candidates that already have images
                        in the database, skipping any new downloads.
            force: If True, force re-processing even if candidate already has images
                   or is in a "done" status.
        """
        self.cached_only = cached_only
        self.force = force
        self.streetview_client = StreetViewClient()
        self.database = BenchDatabase()

        mode_str = "cached-only mode" if cached_only else "download mode"
        force_str = " (force mode)" if force else ""
        logger.info(
            f"ImageDownloadService initialized for image downloading and caching ({mode_str}{force_str})"
        )

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

        # In cached-only mode, check if images already exist for this candidate
        if self.cached_only:
            try:
                with self.database.get_session() as session:
                    from bench_finder.models.unified_models import (
                        BenchCandidate as DBBenchCandidate,
                    )
                    from bench_finder.models.unified_models import (
                        Image,
                    )

                    # Find the bench candidate in the database
                    db_candidate = (
                        session.query(DBBenchCandidate)
                        .filter(
                            DBBenchCandidate.provider_id == bench.provider_id,
                            DBBenchCandidate.search_id == search_id,
                        )
                        .first()
                    )

                    if not db_candidate:
                        logger.debug(
                            f"Cached-only mode: Candidate {bench.provider_id} not found in database, skipping"
                        )
                        return result

                    # Check if images already exist for this candidate
                    existing_images = (
                        session.query(Image)
                        .filter(Image.bench_candidate_id == db_candidate.id)
                        .all()
                    )

                    if not existing_images:
                        logger.debug(
                            f"Cached-only mode: No cached images found for candidate {bench.provider_id}, skipping"
                        )
                        return result

                    # Count successful images
                    successful_images = [
                        img for img in existing_images if img.capture_success
                    ]
                    result.images_captured = len(existing_images)
                    result.images_successful = len(successful_images)

                    logger.debug(
                        f"Cached-only mode: Found {result.images_successful}/{result.images_captured} cached images for {bench.provider_id}"
                    )

            except Exception as e:
                logger.warning(
                    f"Error checking cached images for {bench.provider_id}: {e}"
                )
                return result

        else:
            # Normal mode: Add bench to database and capture images
            try:
                bench_data = BenchBase(
                    provider_id=bench.provider_id,
                    lat=lat,  # Use validated coordinates
                    lng=lng,
                    tags=bench.tags,
                    source=bench.source,
                    external_id=bench.external_id,
                )
                bench_id = self.database.add_bench(bench_data, search_id=search_id)
                if bench_id:
                    result.bench_added = True
                    logger.debug(
                        f"Added bench {bench.provider_id} as DB record {bench_id}"
                    )
                else:
                    logger.warning(
                        f"Failed to add bench {bench.provider_id} to database"
                    )
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
                    # Convert image_source string to ImageSource enum if present
                    from bench_finder.models.enums import ImageSource

                    image_source = None
                    if image_capture.image_source:
                        try:
                            image_source = ImageSource(image_capture.image_source)
                        except ValueError:
                            logger.warning(
                                f"Unknown image_source: {image_capture.image_source}"
                            )

                    self.database.add_image(
                        ImageBase(
                            heading=image_capture.heading,
                            filepath=image_capture.filepath,
                            filename=image_capture.filename,
                            file_size=image_capture.file_size,
                            capture_success=image_capture.success,
                            capture_error=image_capture.error,
                            image_source=image_source,
                            panorama_lat=image_capture.panorama_lat,
                            panorama_lng=image_capture.panorama_lng,
                            panorama_metadata=image_capture.panorama_metadata,
                            panorama_heading=image_capture.panorama_heading,
                        ),
                        bench_id=bench_id,
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
                from bench_finder.models.unified_models import BenchCandidate

                candidate = (
                    session.query(BenchCandidate)
                    .filter(
                        BenchCandidate.provider_id == bench.provider_id,
                        BenchCandidate.search_id == search_id,
                    )
                    .first()
                )

                if candidate and candidate.id:
                    # Update status - force mode bypasses status checks
                    if self.force or candidate.status not in [
                        BenchCandidateStatus.IMAGE_DOWNLOAD_DONE,
                        BenchCandidateStatus.DETECTION_DONE,
                    ]:
                        self.database.update_bench_candidate_status(
                            candidate.id, BenchCandidateStatus.IMAGE_DOWNLOAD_DONE
                        )
                        force_msg = " (forced)" if self.force else ""
                        logger.debug(
                            f"Updated candidate {candidate.id} status to image_download_done{force_msg}"
                        )
                    else:
                        logger.debug(
                            f"Candidate {candidate.id} already has status {candidate.status}, skipping update"
                        )
                else:
                    logger.warning(
                        f"Could not find candidate with provider_id {bench.provider_id} to update status"
                    )
        except Exception as e:
            logger.warning(f"Failed to update candidate status: {e}")

        return result
