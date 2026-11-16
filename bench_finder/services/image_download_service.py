"""
Image download and caching service for bench candidates.

This service handles only the image capture and database storage
for bench candidates without any detection logic.
"""

import asyncio
import logging
from collections.abc import Callable

import aiohttp

from bench_finder.core.streetview import StreetViewClient
from bench_finder.generators.bench_generator import CandidateResult
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

DEFAULT_CONCURRENCY = 4


class ImageDownloadService:
    """Service for downloading and caching images for bench candidates."""

    def __init__(
        self,
        cached_only: bool = False,
        force: bool = False,
        concurrency: int = DEFAULT_CONCURRENCY,
    ):
        """
        Initialize the image download service.

        Args:
            cached_only: If True, only process candidates that already have images
                        in the database, skipping any new downloads.
            force: If True, force re-processing even if candidate already has images
                   or is in a "done" status.
            concurrency: How many benches are fetched at the same time.
        """
        self.concurrency = max(1, concurrency)
        self.cached_only = cached_only
        self.force = force
        self.streetview_client = StreetViewClient()
        self.database = BenchDatabase()

        mode_str = "cached-only mode" if cached_only else "download mode"
        force_str = " (force mode)" if force else ""
        logger.info(
            f"ImageDownloadService initialized for image downloading and caching ({mode_str}{force_str})"
        )

    def process_candidates(
        self,
        items: list[tuple[int, CandidateResult]],
        on_done: Callable[[int], None] | None = None,
    ) -> list[BenchProcessingResult | None]:
        """
        Fetch aimed views for many candidates in a single event loop.

        This is the one place that starts an event loop for a batch: candidates are
        processed concurrently (bounded by ``self.concurrency``) and nothing in the
        path blocks the loop with ``time.sleep``.

        Args:
            items: (search_id, candidate) pairs
            on_done: Optional callback invoked with the item index as each finishes

        Returns:
            One BenchProcessingResult per item, in order (None if that item raised)
        """
        warm_up = getattr(self.streetview_client, "warm_up", None)
        if warm_up is not None:
            warm_up()
        return asyncio.run(self.process_candidates_async(items, on_done))

    async def process_candidates_async(
        self,
        items: list[tuple[int, CandidateResult]],
        on_done: Callable[[int], None] | None = None,
    ) -> list[BenchProcessingResult | None]:
        semaphore = asyncio.Semaphore(self.concurrency)
        timeout = aiohttp.ClientTimeout(total=120, connect=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:

            async def worker(index: int, search_id: int, bench: CandidateResult):
                async with semaphore:
                    try:
                        return await self._process_bench_async(
                            search_id, bench, session
                        )
                    except Exception:
                        logger.exception(f"Failed to process bench {bench.provider_id}")
                        return None
                    finally:
                        if on_done is not None:
                            on_done(index)

            return list(
                await asyncio.gather(
                    *[worker(i, sid, bench) for i, (sid, bench) in enumerate(items)]
                )
            )

    def _summarize(
        self, results: list[BenchProcessingResult | None]
    ) -> ProcessingStats:
        stats = ProcessingStats(
            benches_processed=0,
            benches_added=0,
            images_captured=0,
            images_successful=0,
            detections_performed=0,
            benches_detected=0,
            best_confidence=0.0,
        )
        for result in results:
            if result is None:
                continue
            stats.benches_processed += 1
            if result.bench_added:
                stats.benches_added += 1
            stats.images_captured += result.images_captured
            stats.images_successful += result.images_successful
        logger.info(
            f"Image download complete - {stats.benches_added}/{stats.benches_processed} "
            f"benches processed with {stats.images_successful}/{stats.images_captured} images captured"
        )
        return stats

    def process_benches(
        self, search_id: int, benches: list[CandidateResult]
    ) -> ProcessingStats:
        """Process benches for one search: capture aimed views and store them."""
        progress = ProgressTracker(len(benches), "Downloading images")
        results = self.process_candidates(
            [(search_id, b) for b in benches], on_done=lambda _i: progress.update()
        )
        progress.finish()
        return self._summarize(results)

    def process_benches_with_progress(
        self, search_id: int, benches: list[CandidateResult], progress, task
    ) -> ProcessingStats:
        """Like :meth:`process_benches`, advancing a Rich progress bar."""
        results = self.process_candidates(
            [(search_id, b) for b in benches],
            on_done=lambda _i: progress.update(task, advance=1),
        )
        return self._summarize(results)

    async def _process_bench_async(
        self,
        search_id: int,
        bench: CandidateResult,
        http_session: aiohttp.ClientSession,
    ) -> BenchProcessingResult:
        """
        Process a single bench: add to DB and capture aimed views.

        Args:
            search_id: Database search ID
            bench: Bench candidate from any source (OSM, Mapillary, etc.)
            http_session: Shared aiohttp session

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
                        BenchCandidate,
                        Image,
                    )

                    # Find the bench candidate in the database
                    db_candidate = (
                        session.query(BenchCandidate)
                        .filter(
                            BenchCandidate.provider_id == bench.provider_id,
                            BenchCandidate.search_id == search_id,
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
                image_results = await self.streetview_client.capture_bench_views_async(
                    lat, lng, bench_identifier, session=http_session
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
                        image_base_from_capture(image_capture),
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


def image_base_from_capture(image_capture) -> ImageBase:
    """The ``images`` row for one capture (success or error)."""
    from bench_finder.models.enums import ImageSource

    image_source = None
    if image_capture.image_source:
        try:
            image_source = ImageSource(image_capture.image_source)
        except ValueError:
            logger.warning(f"Unknown image_source: {image_capture.image_source}")
    return ImageBase(
        heading=image_capture.heading,
        filepath=image_capture.filepath,
        filename=image_capture.filename,
        file_size=image_capture.file_size,
        capture_success=image_capture.success,
        capture_error=image_capture.error,
        image_source=image_source,
        panorama_lat=image_capture.panorama_lat,
        panorama_lng=image_capture.panorama_lng,
        panorama_metadata=(
            image_capture.panorama_metadata.model_dump(mode="json", exclude_none=True)
            if image_capture.panorama_metadata
            else None
        ),
        panorama_heading=image_capture.panorama_heading,
        pano_id=image_capture.pano_id,
        pano_date=image_capture.pano_date,
        camera_bearing_deg=image_capture.camera_bearing_deg,
        camera_distance_m=image_capture.camera_distance_m,
        fov_deg=image_capture.fov_deg,
        pitch_deg=image_capture.pitch_deg,
        kind=image_capture.kind,
    )
