"""
Display and visualization utilities for bench finder results.
"""

import logging
from typing import Optional

from PIL import Image as PILImage
from term_image.image import AutoImage

from bench_finder.clients.base_detection_client import DetectionResult
from bench_finder.models.streetview_models import StreetViewImageCapture
from tools.roboflow_detector import render_detections


logger = logging.getLogger(__name__)


def create_combined_image_display(
    image_results: list[dict], target_width: int = 400
) -> Optional[PILImage.Image]:
    """
    Create a combined PIL Image from multiple image results.

    Args:
        image_results: List of image result dictionaries with 'filepath' keys
        target_width: Target width for each image in the combined display

    Returns:
        Combined PIL Image or None if no valid images
    """
    if not image_results:
        return None

    valid_images = []
    for img_result in image_results:
        if img_result.get("filepath"):
            try:
                img = PILImage.open(img_result["filepath"])
                # Resize to target width while maintaining aspect ratio
                aspect_ratio = img.height / img.width
                target_height = int(target_width * aspect_ratio)
                img_resized = img.resize(
                    (target_width, target_height), PILImage.Resampling.LANCZOS
                )
                valid_images.append(img_resized)
            except Exception as e:
                logger.warning(
                    f"Failed to load image {img_result.get('filepath', 'unknown')}: {e}"
                )
                continue

    if not valid_images:
        return None

    # Calculate combined image dimensions
    total_width = target_width * len(valid_images)
    max_height = max(img.height for img in valid_images)

    # Create combined image
    combined = PILImage.new("RGB", (total_width, max_height), color="white")

    # Paste images side by side
    x_offset = 0
    for valid_image in valid_images:
        y_offset = (max_height - valid_image.height) // 2  # Center vertically
        combined.paste(valid_image, (x_offset, y_offset))
        x_offset += target_width

    return combined


def display_bench_detection_results(
    bench_identifier: str,
    image_results: list[StreetViewImageCapture],
    bench_detections: list[DetectionResult],
    representative_detection: Optional[DetectionResult],
    copy_bench_images: bool = True,
) -> None:
    """
    Display bench detection results with images and annotations.

    Args:
        bench_identifier: Identifier for the bench being processed
        image_results: List of image capture results
        bench_detections: List of detection results for images with benches
        representative_detection: The representative detection result
        copy_bench_images: Whether to copy images with detected benches
    """
    if not bench_detections:
        logger.info(f"No benches detected for {bench_identifier}")
        return

    # Display detection summary
    logger.info(
        f"\n📊 Detection Summary ({len(bench_detections)} images with benches):"
    )
    for i, detection_info in enumerate(
        sorted(bench_detections, key=lambda x: x.area, reverse=True)
    ):
        image_path = detection_info.image_path
        streetview_image = next(
            (img for img in image_results if img.filepath == image_path), None
        )
        if not streetview_image:
            logger.warning(f"No streetview image found for {image_path}")
            continue
        heading = streetview_image.heading
        max_confidence = detection_info.max_confidence
        pixel_coverage = detection_info.area / (
            streetview_image.width * streetview_image.height
        )
        is_representative = detection_info == representative_detection
        marker = "🏆" if is_representative else f"{i+1}."
        print(
            f"  {marker} Heading {heading:3d}°: {max_confidence:.2f} confidence, "
            f"{pixel_coverage:.1f}% pixels{'  (REPRESENTATIVE)' if is_representative else ''}"
        )

    # Display representative image with annotations
    if representative_detection:
        image_path = representative_detection.image_path
        streetview_image = next(
            (img for img in image_results if img.filepath == image_path), None
        )
        if not streetview_image:
            logger.warning(f"No streetview image found for {image_path}")
            return
        heading = streetview_image.heading
        max_confidence = representative_detection.max_confidence
        pixel_coverage = representative_detection.area / (streetview_image.area)
        winning_model = representative_detection.model_name

        # Copy image if enabled
        copied_path = None
        if copy_bench_images:
            copied_path = _copy_bench_image(bench_identifier, image_path, winning_model)

        copy_info = f" (copied to {copied_path})" if copied_path else ""

        print(
            f"🏆 Representative bench image: {image_path} "
            f"(heading {heading}°) with {pixel_coverage:.1f}% pixel coverage "
            f"and confidence {max_confidence:.2f} using {winning_model}{copy_info}"
        )

        # Pass StandardDetectionResult object directly to render_detections
        print(
            AutoImage(
                render_detections(image_path, representative_detection, winning_model)
            )
        )


def _copy_bench_image(
    bench_identifier: str, source_path: str, model_name: str
) -> Optional[str]:
    """
    Copy a bench image to the bench_images directory.

    Args:
        bench_identifier: Identifier for the bench
        image_result: Image result dictionary
        model_name: Name of the model that detected the bench

    Returns:
        Path to the copied image or None if copy failed
    """
    try:
        import os
        import shutil
        from pathlib import Path

        if not source_path or not os.path.exists(source_path):
            return None

        # Create destination directory
        dest_dir = Path("bench_images") / model_name
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Generate destination filename
        source_filename = os.path.basename(source_path)
        dest_filename = f"{bench_identifier}_{source_filename}"
        dest_path = dest_dir / dest_filename

        # Copy the file
        shutil.copy2(source_path, dest_path)
        return str(dest_path)

    except Exception as e:
        logger.warning(f"Failed to copy bench image: {e}")
        return None


def display_no_bench_detected(image_results: list[dict]) -> None:
    """
    Display information when no benches are detected.

    Args:
        image_results: List of image capture results
    """
    logger.info("\n[DEBUG] No bench detected for this location.")
    logger.info("Captured image filepaths for manual inspection:")
    for img_result in image_results:
        if img_result.get("filepath"):
            logger.info(
                f"  • {img_result['filepath']} (heading {img_result.get('heading', 'unknown')}°)"
            )
