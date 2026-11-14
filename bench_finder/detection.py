"""
Bench detection service for processing images and running AI detection.

This module contains the BenchDetector class that handles the detection phase
of the bench finding pipeline, focusing on running AI models on captured images.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from rich.progress import (
    Progress,
    TaskID,
)
from term_image.image import AutoImage

from bench_finder.models.enums import BenchCandidateStatus
from bench_finder.models.unified_models import (
    BenchCandidate,
    BenchProcessingResult,
    DetectionResult,
    Image,
    ProcessingStats,
)
from bench_finder.tools.bench_detection_cli import render_detections


# Set environment variables to suppress inference model dependency warnings
os.environ.setdefault("CORE_MODEL_PE_ENABLED", "False")
os.environ.setdefault("PALIGEMMA_ENABLED", "False")
os.environ.setdefault("FLORENCE2_ENABLED", "False")
os.environ.setdefault("QWEN_2_5_ENABLED", "False")
os.environ.setdefault("CORE_MODEL_SAM_ENABLED", "False")
os.environ.setdefault("CORE_MODEL_SAM2_ENABLED", "False")
os.environ.setdefault("CORE_MODEL_CLIP_ENABLED", "False")
os.environ.setdefault("CORE_MODEL_GAZE_ENABLED", "False")
os.environ.setdefault("SMOLVLM2_ENABLED", "False")
os.environ.setdefault("DEPTH_ESTIMATION_ENABLED", "False")
os.environ.setdefault("MOONDREAM2_ENABLED", "False")
os.environ.setdefault("CORE_MODEL_TROCR_ENABLED", "False")
os.environ.setdefault("CORE_MODEL_GROUNDINGDINO_ENABLED", "False")
os.environ.setdefault("CORE_MODEL_YOLO_WORLD_ENABLED", "False")

from PIL import Image as PILImage
from sqlmodel import Field


PILImage.MAX_IMAGE_PIXELS = 300_000_000

from bench_finder.clients.multi_model_client import UnifiedMultiModelDetectionClient
from bench_finder.clients.roboflow_client import RoboflowClient
from bench_finder.clients.ultralytics_client import UltralyticsClient
from bench_finder.config import DETECTION_BACKEND
from bench_finder.display import (
    create_combined_image_display,
    display_bench_detection_results,
    display_no_bench_detected,
)
from bench_finder.generators.bench_generator import CandidateResult
from bench_finder.models.unified_models import (
    DetectionBase,
    DetectionItem,
)
from bench_finder.services.database import BenchDatabase


if TYPE_CHECKING:
    from bench_finder.clients.base_detection_client import DetectionClient


logger = logging.getLogger(__name__)


class _DetectionWithItems(DetectionBase):
    """DetectionBase carrying its items; DetectionBase itself has no such field,
    so assigning ``detection_items`` on it raised a pydantic ValueError."""

    detection_items: list[DetectionItem] = Field(default_factory=list)


class BenchDetector:
    """Service for running AI detection on bench images."""

    def __init__(
        self,
        detection_backend: str | None = None,
        enable_fallback: bool = True,
        copy_bench_images: bool = True,
    ):
        """Initialize the bench detector.

        Args:
            detection_backend: Detection backend to use ('roboflow', 'ultralytics', or 'multi')
                             If None, uses config.DETECTION_BACKEND or defaults to 'multi'
            enable_fallback: Whether to enable multi-model fallback detection (default: True)
            copy_bench_images: Whether to copy images with detected benches to bench_images/{model_name}/ (default: True)
        """
        self.database = BenchDatabase()
        self.detection_backend = detection_backend or DETECTION_BACKEND
        self.enable_fallback = enable_fallback
        self.copy_bench_images = copy_bench_images

        # Default to multi-model detection if fallback is enabled
        if enable_fallback and self.detection_backend != "multi":
            logger.info(
                f"Enabling multi-model detection with fallback (primary: {self.detection_backend})"
            )
            self.detection_backend = "multi"

        self.detection_client: DetectionClient
        if self.detection_backend == "multi":
            logger.info("Initializing multi-model detection client with fallback")
            self.detection_client = UnifiedMultiModelDetectionClient()
        elif self.detection_backend == "ultralytics":
            logger.info("Initializing Ultralytics detection backend (no fallback)")
            self.detection_client = UltralyticsClient()
        elif self.detection_backend == "roboflow":
            logger.info("Initializing Roboflow detection backend (no fallback)")
            self.detection_client = RoboflowClient()
        else:
            raise ValueError(
                f"Unsupported detection backend: {self.detection_backend}. Use 'ultralytics', 'roboflow', or 'multi'"
            )

        logger.info(f"BenchDetector initialized with {self.detection_backend} backend")
        if self.copy_bench_images:
            logger.info(
                "Bench image copying enabled - detected bench images will be copied to bench_images/{model_name}/"
            )
        else:
            logger.info("Bench image copying disabled")

    def _copy_bench_image(
        self, image_path: str, model_name: str, bench_id: str, heading: int
    ) -> str | None:
        """
        Copy an image with detected bench to the bench_images directory.

        Args:
            image_path: Source image file path
            model_name: Name of the model that detected the bench
            bench_id: Bench identifier for organizing files
            heading: Image heading for unique naming

        Returns:
            Path to copied image, or None if copy failed
        """
        if not self.copy_bench_images or not os.path.exists(image_path):
            return None

        try:
            # Create directory structure: bench_images/{model_name}/
            output_dir = os.path.join("bench_images", model_name)
            os.makedirs(output_dir, exist_ok=True)

            # Generate unique filename
            base_filename = os.path.basename(image_path)
            name, ext = os.path.splitext(base_filename)
            new_filename = f"{bench_id}_heading_{heading}_{name}{ext}"
            output_path = os.path.join(output_dir, new_filename)

            # Copy the file
            shutil.copy2(image_path, output_path)
            logger.debug(f"Copied bench image to: {output_path}")
            return output_path

        except Exception as e:
            logger.warning(f"Failed to copy bench image {image_path}: {e}")
            return None

    def _find_best_detection_index(
        self,
        detection_results: list[DetectionResult],
        pixel_coverage_results: list[float],
    ) -> int:
        """Select best detection by pixel coverage, then confidence as tiebreaker."""
        best_index = 0
        for i, (detection_result, pixel_coverage) in enumerate(
            zip(detection_results, pixel_coverage_results, strict=False)
        ):
            current_best_coverage = pixel_coverage_results[best_index]
            current_best_confidence = detection_results[best_index].max_confidence
            if pixel_coverage > current_best_coverage or (
                pixel_coverage == current_best_coverage
                and detection_result.max_confidence > current_best_confidence
            ):
                best_index = i
        return best_index

    def _calculate_pixel_coverage(
        self, detection_result: DetectionResult, image_path: str
    ) -> float:
        """
        Calculate what percentage of pixels the bench occupies in the image.

        Args:
            detection_result: DetectionResult from the ML model
            image_path: Path to the image file for dimensions

        Returns:
            Percentage of pixels covered by bench detections (0.0 to 100.0)
        """
        try:
            if not detection_result.has_bench:
                return 0.0

            # Debug logging
            logger.debug(f"Calculating pixel coverage for {image_path}")
            logger.debug(
                f"Detection result has {len(detection_result.detections)} detections"
            )

            # Get image dimensions
            with PILImage.open(image_path) as img:
                image_width, image_height = img.size
                total_pixels = image_width * image_height

            total_bench_pixels: float = 0

            # Process standardized detections
            for detection_item in detection_result.detections:
                bbox = detection_item.bbox
                logger.debug(
                    f"Using standardized bbox: x1={bbox.x1:.1f}, y1={bbox.y1:.1f}, x2={bbox.x2:.1f}, y2={bbox.y2:.1f}"
                )

                # Use pre-calculated width and height from BoundingBox
                bbox_pixels = bbox.width * bbox.height
                total_bench_pixels += bbox_pixels
                logger.debug(
                    f"Bbox area: {bbox.width:.1f} x {bbox.height:.1f} = {bbox_pixels:.0f} pixels"
                )

            # Calculate percentage
            if total_pixels > 0:
                coverage_percentage = (total_bench_pixels / total_pixels) * 100
                logger.debug(
                    f"Pixel coverage calculation: {total_bench_pixels} bench pixels / {total_pixels} total pixels = {coverage_percentage:.2f}%"
                )
                return float(min(coverage_percentage, 100.0))  # Cap at 100%

            logger.debug("No pixels found - returning 0.0% coverage")
            return 0.0

        except Exception as e:
            logger.debug(f"Failed to calculate pixel coverage for {image_path}: {e}")
            return 0.0

    def process_benches_with_progress(
        self, benches: list[CandidateResult], progress: Progress, task: TaskID
    ) -> ProcessingStats:
        """
        Process each bench: run detection on existing images.

        Args:
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
                result = self._process_single_bench(bench)

                stats.benches_processed += 1
                if result.bench_added:
                    stats.benches_added += 1

                stats.images_captured += result.images_captured
                stats.images_successful += result.images_successful
                stats.detections_performed += result.detections_performed

                if result.bench_detected:
                    stats.benches_detected += 1

                stats.best_confidence = max(
                    stats.best_confidence, result.best_confidence
                )

                progress.update(task, advance=1)

            except Exception:
                bench_id = bench.provider_id
                logger.exception(f"Failed to process bench {bench_id}")
                progress.update(task, advance=1)
                continue

        logger.info(
            f"Detection complete - {stats.benches_detected}/{stats.benches_processed} "
            f"benches detected with best confidence: {stats.best_confidence:.2f}"
        )

        return stats

    def _process_single_bench(
        self, bench: CandidateResult
    ) -> BenchProcessingResult:
        """
        Process a single bench: run detection on existing images.

        Args:
            bench: Bench candidate from any source (OSM, Mapillary, etc.)

        Returns:
            BenchProcessingResult for this bench
        """
        result: BenchProcessingResult = BenchProcessingResult(
            bench_added=False,
            images_captured=0,
            images_successful=0,
            detections_performed=0,
            bench_detected=False,
            best_confidence=0.0,
        )

        images: list[Image] = []
        db_bench_candidate: BenchCandidate | None = None

        # Find the bench candidate in the database to get its images
        try:
            with self.database.get_session() as session:
                # Find the bench candidate by provider_id
                db_bench_candidate = (
                    session.query(BenchCandidate)
                    .filter(
                        BenchCandidate.provider_id == bench.provider_id,
                    )
                    .first()
                )

                if not db_bench_candidate:
                    logger.warning(
                        f"Bench candidate {bench.provider_id} not found in database"
                    )
                    return result

                # Get all images for this bench candidate
                images = (
                    session.query(Image)
                    .where(
                        Image.bench_candidate_id == db_bench_candidate.id,
                        Image.capture_success,
                    )
                    .all()
                )

                if not images:
                    logger.warning(
                        f"No successful images found for bench {bench.provider_id}"
                    )
                    return result

                result.images_captured = len(images)
                result.images_successful = len(images)

        except Exception:
            logger.exception(f"Failed to get images for bench {bench.provider_id}")
            return result

        # Generate unique identifier for image filenames
        if db_bench_candidate is None or db_bench_candidate.id is None:
            logger.error(f"Bench candidate {bench.provider_id} has no ID")
            return result
        bench_identifier = bench.provider_id or f"bench_{db_bench_candidate.id}"

        # Phase 1: Run detection on all successful images and calculate pixel coverage
        detection_results: list[DetectionResult] = []
        pixel_coverage_results: list[float] = []
        successful_images: list[Image] = []

        for image in images:
            try:
                if image.filepath is None:
                    logger.warning(f"Image {image.id} has no filepath")
                    continue
                filepath = Path(__file__).parent.parent / image.filepath
                if not filepath.exists():
                    logger.warning(f"Image file not found: {filepath}")
                    continue

                logger.debug(f"Running detection on {filepath}")
                detection_result = self.detection_client.detect_benches_in_image(
                    str(filepath)
                )

                # Calculate pixel coverage
                pixel_coverage = self._calculate_pixel_coverage(
                    detection_result, str(filepath)
                )

                detection_results.append(detection_result)
                pixel_coverage_results.append(pixel_coverage)
                result.detections_performed += 1
                successful_images.append(image)

                # Update overall results
                if detection_result.has_bench:
                    result.bench_detected = True
                    result.best_confidence = max(
                        result.best_confidence, detection_result.max_confidence
                    )

                logger.debug(
                    f"Image {image.heading}° - Bench: {detection_result.has_bench}, "
                    f"Confidence: {detection_result.max_confidence:.2f}, "
                    f"Pixel coverage: {pixel_coverage:.1f}%"
                )

            except Exception:
                logger.exception(
                    f"Detection failed for bench {bench.provider_id}, image {image.filepath}"
                )

        # Phase 2: Find the representative image (highest pixel coverage with bench detected)
        representative_detection = None
        current_best_coverage = 0.0

        if detection_results:
            best_index = self._find_best_detection_index(
                detection_results, pixel_coverage_results
            )
            representative_detection = detection_results[best_index]

            logger.info(
                f"🎯 Selected representative image: heading {successful_images[best_index].heading}° "
                f"with {pixel_coverage_results[best_index]:.1f}% pixel coverage and "
                f"{detection_results[best_index].max_confidence:.2f} confidence"
            )

        # Phase 3: Save all detection results to database and display representative image
        for i, detection_result in enumerate(detection_results):
            image = successful_images[i]
            image_id = image.id
            if image_id is None:
                logger.error(
                    f"Image {image.filepath} has no ID, skipping detection save"
                )
                continue

            # Store successful detection result using unified DetectionBase
            detection_data = _DetectionWithItems(
                image_id=image_id,
                has_bench=detection_result.has_bench,
                bench_count=detection_result.bench_count,
                max_confidence=detection_result.max_confidence,
                detection_success=detection_result.success,
                detection_error=detection_result.error,
                model_id=detection_result.model_id or "unknown",
                confidence_threshold=self.detection_client.confidence_threshold,
                source=detection_result.source,
                # Ultralytics-specific fields (optional)
                # full_response=detection_result.full_response,
                # bench_detections=detection_result.bench_detections,
                model_url=detection_result.model_url,
                iou_threshold=detection_result.iou_threshold,
                image_size=detection_result.image_size,
                inference_time=detection_result.inference_time,
                preprocess_time=detection_result.preprocess_time,
                postprocess_time=detection_result.postprocess_time,
            )

            # Add detection items as a separate attribute
            detection_data.detection_items = [
                DetectionItem(
                    detection_id=0,  # Will be set when detection is saved
                    image_id=image_id,
                    confidence=item.confidence,
                    bbox=item.bbox,
                    class_name=item.class_name,
                    polygon=item.polygon,
                )
                for item in detection_result.detections
            ]

            self.database.add_detection(detection_data, image_id)

            # Display and copy only the representative image
            if detection_result == representative_detection:
                winning_model = detection_result.backend_name
                pixel_coverage = current_best_coverage

                # Log detection success with model information
                logger.info(
                    f"✅ Representative detection: {winning_model} (backend: {self.detection_backend})"
                )

                # Copy the representative image
                if image.filepath is not None:
                    copied_path = self._copy_bench_image(
                        image.filepath,
                        winning_model,
                        bench_identifier,
                        image.heading,
                    )
                else:
                    copied_path = None
                copy_info = f" (copied to {copied_path})" if copied_path else ""

                image_path_str = image.filepath or "unknown"
                print(
                    f"🏆 Representative bench image: {image_path_str} "
                    f"(heading {image.heading}°) with {pixel_coverage:.1f}% pixel coverage "
                    f"and confidence {detection_result.max_confidence:.2f} using {winning_model}{copy_info}"
                )
                # Pass DetectionResult object directly to render_detections
                if image.filepath is not None:
                    print(
                        AutoImage(
                            render_detections(
                                image.filepath, detection_result, winning_model
                            )
                        )
                    )

        # Use display utilities for consistent output
        display_bench_detection_results(
            bench_identifier,
            successful_images,
            detection_results,
            representative_detection,
            self.copy_bench_images,
        )

        # Persist the single best detected image per bench
        try:
            # Only record a ProcessedBench when a bench was actually detected
            if (
                detection_results
                and representative_detection
                and representative_detection.has_bench
            ):
                best_index = self._find_best_detection_index(
                    detection_results, pixel_coverage_results
                )
                best_image = successful_images[best_index]
                if best_image.id is not None:
                    # upsert single ProcessedBench row
                    self.database.upsert_detected_bench(
                        bench_id=db_bench_candidate.id,
                        image_id=best_image.id,
                        confidence=detection_results[best_index].max_confidence,
                    )
        except Exception:
            logger.exception(
                f"Failed to upsert DetectedBench for bench {bench.provider_id}"
            )

        # If no bench was detected, show debug information
        if not result.bench_detected:
            display_no_bench_detected(
                [
                    {"filepath": img.filepath, "heading": img.heading}
                    for img in successful_images
                ]
            )

            # Create combined image display
            combined_img = create_combined_image_display(
                [{"filepath": img.filepath} for img in successful_images]
            )
            if combined_img:
                print(AutoImage(combined_img))
            else:
                print(
                    "(Combined image display unavailable - check individual files below)"
                )

            # Also print the file paths
            for image in successful_images:
                print(f"  - {image.filepath}")
            print(
                "You can manually review these images to check for benches or detection issues.\n"
            )

        # Update candidate status to detection_done, but only if at least one
        # image was actually analysed successfully; otherwise leave it for retry.
        if not any(r.success for r in detection_results):
            logger.warning(
                f"No successful detections for bench {bench.provider_id}; "
                "leaving candidate status unchanged"
            )
            return result

        try:
            with self.database.get_session() as session:
                candidate = (
                    session.query(BenchCandidate)
                    .filter(
                        BenchCandidate.provider_id == bench.provider_id,
                    )
                    .first()
                )

                if candidate:
                    # Only update status if it's not already detection_done
                    if candidate.status != BenchCandidateStatus.DETECTION_DONE:
                        self.database.update_bench_candidate_status(
                            candidate.id, BenchCandidateStatus.DETECTION_DONE
                        )
                        logger.debug(
                            f"Updated candidate {candidate.id} status to detection_done"
                        )
                    else:
                        logger.debug(
                            f"Candidate {candidate.id} already has status detection_done, skipping update"
                        )
                else:
                    logger.warning(
                        f"Could not find candidate with provider_id {bench.provider_id} to update status"
                    )
        except Exception as e:
            logger.warning(f"Failed to update candidate status: {e}")

        return result
