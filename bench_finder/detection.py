"""
Bench detection service for processing images and running AI detection.

This module contains the BenchDetector class that handles the detection phase
of the bench finding pipeline, focusing on running AI models on captured images.
"""

import logging
import os
import shutil
from typing import Optional

from rich.progress import (
    Progress,
)
from term_image.image import AutoImage

from tools.bench_detection_cli import render_detections


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

from generators.bench_generator import BenchCandidate
from PIL import Image as PILImage

from clients.base_detection_client import DetectionClient, DetectionResult
from clients.multi_model_client import UnifiedMultiModelDetectionClient
from clients.roboflow_client import RoboflowClient
from clients.ultralytics_client import UltralyticsClient
from config import DETECTION_BACKEND
from display import (
    create_combined_image_display,
    display_bench_detection_results,
    display_no_bench_detected,
)
from models.schemas import (
    BenchProcessingResult,
    DetectionCreate,
    ProcessingStats,
    UltralyticsDetectionCreate,
)
from services.database import BenchDatabase


logger = logging.getLogger(__name__)


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
    ) -> Optional[str]:
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

    def _calculate_pixel_coverage(
        self, detection_result: DetectionResult, image_path: str
    ) -> float:
        """
        Calculate what percentage of pixels the bench occupies in the image.

        Args:
            detection_result: StandardDetectionResult from the ML model
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
                return min(coverage_percentage, 100.0)  # Cap at 100%

            logger.debug("No pixels found - returning 0.0% coverage")
            return 0.0

        except Exception as e:
            logger.debug(f"Failed to calculate pixel coverage for {image_path}: {e}")
            return 0.0

    def process_benches_with_progress(
        self, search_id: int, benches: list[BenchCandidate], progress: Progress, task
    ) -> ProcessingStats:
        """
        Process each bench: run detection on existing images.

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
        self, search_id: int, bench: BenchCandidate
    ) -> BenchProcessingResult:
        """
        Process a single bench: run detection on existing images.

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

        # Find the bench in the database to get its images
        try:
            with self.database.get_session() as session:
                from models.models import Bench, Image

                # Find the bench by provider_id and search_id
                db_bench = session.query(Bench).filter(
                    Bench.provider_id == bench.provider_id,
                    Bench.search_id == search_id
                ).first()

                if not db_bench:
                    logger.warning(f"Bench {bench.provider_id} not found in database")
                    return result

                # Get all images for this bench
                images = session.query(Image).filter(
                    Image.bench_id == db_bench.id,
                    Image.capture_success is True
                ).all()

                if not images:
                    logger.warning(f"No successful images found for bench {bench.provider_id}")
                    return result

                result.images_captured = len(images)
                result.images_successful = len(images)

        except Exception:
            logger.exception(f"Failed to get images for bench {bench.provider_id}")
            return result

        # Generate unique identifier for image filenames
        bench_identifier = bench.provider_id or f"bench_{db_bench.id}"

        # Phase 1: Run detection on all successful images and calculate pixel coverage
        detection_results: list[DetectionResult] = []
        pixel_coverage_results: list[float] = []
        successful_images = []

        for image in images:
            try:
                if not image.filepath or not os.path.exists(image.filepath):
                    logger.warning(f"Image file not found: {image.filepath}")
                    continue

                logger.debug(f"Running detection on {image.filepath}")
                detection_result = self.detection_client.detect_benches_in_image(
                    image.filepath
                )

                # Calculate pixel coverage
                pixel_coverage = self._calculate_pixel_coverage(
                    detection_result, image.filepath
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

        if detection_results:
            # Find the index with highest pixel coverage, then highest confidence
            best_index = 0
            for i, (detection_result, pixel_coverage) in enumerate(zip(detection_results, pixel_coverage_results)):
                current_best_coverage = pixel_coverage_results[best_index]
                current_best_confidence = detection_results[best_index].max_confidence

                if (pixel_coverage > current_best_coverage or
                    (pixel_coverage == current_best_coverage and detection_result.max_confidence > current_best_confidence)):
                    best_index = i
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


            # Store successful detection result
            if (
                hasattr(detection_result, "bench_detections")
                and hasattr(detection_result, "full_response")
            ) or self.detection_backend == "ultralytics":
                self.database.add_ultralytics_detection(
                    UltralyticsDetectionCreate(
                        image_id=image_id,
                        has_bench=detection_result.has_bench,
                        bench_count=detection_result.bench_count,
                        max_confidence=detection_result.max_confidence,
                        full_response=getattr(detection_result, "full_response", {}),
                        bench_detections=detection_result.detections,
                        detection_success=True,
                        detection_error=None,
                        model_url=detection_result.model_id,
                        confidence_threshold=self.detection_client.confidence_threshold,
                        iou_threshold=0,
                        image_size=640,
                        # Enhanced metadata for multi-model tracking
                        inference_time=detection_result.inference_time,
                        preprocess_time=detection_result.preprocess_time,
                        postprocess_time=detection_result.postprocess_time,
                    )
                )
            else:
                # Roboflow detection format
                model_id = getattr(
                    detection_result,
                    "winning_model_id",
                    getattr(self.detection_client, "model_id", "unknown"),
                )
                self.database.add_detection(
                    DetectionCreate(
                        image_id=image_id,
                        has_bench=detection_result.has_bench,
                        bench_count=detection_result.bench_count,
                        max_confidence=detection_result.max_confidence,
                        detections=getattr(detection_result, "detections", []),
                        detection_success=True,
                        detection_error=None,
                        model_id=model_id,
                        confidence_threshold=getattr(
                            self.detection_client, "confidence_threshold", 0.0
                        ),
                    )
                )

            # Display and copy only the representative image
            if detection_result == representative_detection:
                winning_model = detection_result.backend_name
                pixel_coverage = detection_result.pix

                # Log detection success with model information
                logger.info(
                    f"✅ Representative detection: {winning_model} (backend: {self.detection_backend})"
                )

                # Copy the representative image
                copied_path = self._copy_bench_image(
                    image.filepath,
                    winning_model,
                    bench_identifier,
                    image.heading,
                )
                copy_info = f" (copied to {copied_path})" if copied_path else ""

                print(
                    f"🏆 Representative bench image: {image.filepath} "
                    f"(heading {image.heading}°) with {pixel_coverage:.1f}% pixel coverage "
                    f"and confidence {detection_result.max_confidence:.2f} using {winning_model}{copy_info}"
                )
                # Pass StandardDetectionResult object directly to render_detections
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

        # Update candidate status to detection_done
        try:
            with self.database.get_session() as session:
                from models.models import BenchCandidate
                candidate = session.query(BenchCandidate).filter(
                    BenchCandidate.provider_id == bench.provider_id,
                    BenchCandidate.search_id == search_id
                ).first()

                if candidate:
                    # Only update status if it's not already detection_done
                    if candidate.status != "detection_done":
                        self.database.update_bench_candidate_status(candidate.id, "detection_done")
                        logger.debug(f"Updated candidate {candidate.id} status to detection_done")
                    else:
                        logger.debug(f"Candidate {candidate.id} already has status detection_done, skipping update")
                else:
                    logger.warning(f"Could not find candidate with provider_id {bench.provider_id} to update status")
        except Exception as e:
            logger.warning(f"Failed to update candidate status: {e}")

        return result
