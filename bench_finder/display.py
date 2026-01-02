"""
Display and visualization utilities for bench finder results.
"""

import logging

import cv2
from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont

PILImage.MAX_IMAGE_PIXELS = 300_000_000

from term_image.image import AutoImage, ITerm2Image

from bench_finder.models.unified_models import DetectionResult, Image


logger = logging.getLogger(__name__)

ITerm2Image.set_render_method("WHOLE")


def render_detections(
    image_path: str, result: DetectionResult, model_name: str = "Model"
) -> PILImage.Image:
    """Draw bounding boxes and polygons on the image based on DetectionResult."""
    # Load the original image
    image = cv2.imread(image_path)

    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = PILImage.fromarray(image)

    draw = ImageDraw.Draw(pil_image)

    # Try to load a font (fallback to default if not available)
    try:
        font = ImageFont.truetype("Arial.ttf", 16)
    except OSError:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 16)
        except OSError:
            font = ImageFont.load_default()

    # Colors for different detections
    colors = [
        (255, 0, 0),
        (0, 255, 0),
        (0, 0, 255),
        (255, 255, 0),
        (255, 0, 255),
        (0, 255, 255),
        (128, 0, 0),
        (0, 128, 0),
    ]

    # Extract detection information
    detections = result.detections
    bench_count = result.bench_count
    max_confidence = result.max_confidence
    backend_name = result.backend_name
    model_id = result.model_id

    print(
        f"\n[{model_name}] Found {bench_count} bench detection(s) using {backend_name} ({model_id}):"
    )
    if bench_count > 0:
        print(f"  Max confidence: {max_confidence:.2f}")
        print(f"  Inference time: {(result.inference_time or 0.0):.3f}s")

    for i, detection in enumerate(detections):
        color = colors[i % len(colors)]

        # Extract detection info from DetectionItem object
        class_name = detection.class_name
        confidence = detection.confidence
        bbox = detection.bbox

        print(f"  {i+1}. {class_name} (confidence: {confidence:.2f})")

        # Draw bounding box
        x1 = int(bbox.x1)
        y1 = int(bbox.y1)
        x2 = int(bbox.x2)
        y2 = int(bbox.y2)

        # Draw bounding box rectangle
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)

        # Draw label
        label = f"{class_name} {confidence:.2f}"
        text_bbox = draw.textbbox((x1, y1 - 25), label, font=font)
        draw.rectangle(
            [text_bbox[0] - 2, text_bbox[1] - 2, text_bbox[2] + 2, text_bbox[3] + 2],
            fill=color,
        )
        draw.text((x1, y1 - 25), label, fill=(255, 255, 255), font=font)

        # Handle segmentation polygons (if available)
        if detection.polygon and detection.polygon.coordinates:
            # Convert polygon coordinates to tuples for PIL
            polygon_points = []
            for coord in detection.polygon.coordinates:
                if len(coord) >= 2:
                    polygon_points.append((int(coord[0]), int(coord[1])))  # noqa: PERF401

            if polygon_points:
                # Draw segmentation polygon
                draw.polygon(polygon_points, outline=color, width=3)

                # Draw label at centroid
                if polygon_points:
                    cx = sum(p[0] for p in polygon_points) / len(polygon_points)
                    cy = sum(p[1] for p in polygon_points) / len(polygon_points)

                    label = f"{class_name} {confidence:.2f}"
                    bbox = draw.textbbox((cx - 50, cy - 10), label, font=font)
                    draw.rectangle(
                        [bbox[0] - 2, bbox[1] - 2, bbox[2] + 2, bbox[3] + 2], fill=color
                    )
                    draw.text(
                        (cx - 50, cy - 10), label, fill=(255, 255, 255), font=font
                    )

    return pil_image


def create_combined_image_display(
    image_results: list[dict], target_width: int = 400
) -> PILImage.Image | None:
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
    image_results: list[Image],
    bench_detections: list[DetectionResult],
    representative_detection: DetectionResult | None,
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
            (
                img
                for img in image_results
                if image_path.endswith(img.filepath or "unk")
            ),
            None,
        )
        if not streetview_image:
            logger.warning(f"No streetview image found for {image_path}")
            continue
        heading = streetview_image.heading
        max_confidence = detection_info.max_confidence
        pixel_coverage = detection_info.area / (640 * 640)
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
            (
                img
                for img in image_results
                if image_path.endswith(img.filepath or "unk")
            ),
            None,
        )
        if not streetview_image:
            logger.warning(f"No streetview image found for {image_path}")
            return
        heading = streetview_image.heading
        max_confidence = representative_detection.max_confidence
        pixel_coverage = representative_detection.area / (640 * 640)
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

        # Pass DetectionResult object directly to render_detections
        print(
            AutoImage(
                render_detections(image_path, representative_detection, winning_model)
            )
        )


def _copy_bench_image(
    bench_identifier: str, source_path: str, model_name: str
) -> str | None:
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
