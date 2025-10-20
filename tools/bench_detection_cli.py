#!/usr/bin/env python3
"""
Comprehensive Bench Detection CLI Tool
Tests all detection configurations and displays results using term_image.
Supports Roboflow (local/remote), Ultralytics (local/remote), and Multi-model detection.
"""

import argparse
import os
import sys
import tempfile
from typing import Optional

import cv2
from PIL import Image, ImageDraw, ImageFont
from term_image.image import ITerm2Image, from_file
from term_image.utils import get_terminal_name_version

# # Add the project root to the Python path
# project_root = Path(__file__).parent.parent
# sys.path.insert(0, str(project_root))
# Import our detection clients
from clients.base_detection_client import (
    DetectionResult,
)
from clients.multi_model_client import UnifiedMultiModelDetectionClient
from clients.roboflow_client import RoboflowClient
from clients.ultralytics_client import UltralyticsClient


# Force iTerm2 image support for warp
if get_terminal_name_version()[0] == "warp":
    ITerm2Image.is_supported = lambda *_: True

def render_detections(
    image_path: str, result: DetectionResult, model_name: str = "Model"
) -> Image.Image:
    """Draw bounding boxes and polygons on the image based on DetectionResult."""
    # Load the original image
    image = cv2.imread(image_path)

    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(image)
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
        print(f"  Inference time: {result.inference_time:.3f}s")

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


def display_image_in_terminal(image_path: str, model_name: str = "Model") -> None:
    """Display the image directly in the terminal using term-image."""
    try:
        img = from_file(image_path)
        print("\n" + "=" * 80)
        print(f"DETECTION RESULTS - {model_name}")
        print("=" * 80)
        print(img)
        print("=" * 80)
    except Exception as e:
        print(f"Error displaying image in terminal: {e}")
        print(f"Annotated image available at: {image_path}")


def test_roboflow_local(image_path: str, output_dir: str) -> Optional[str]:
    """Test Roboflow local inference."""
    print("\n🔧 Testing Roboflow Local Inference...")
    try:
        # Check if local inference is available
        import importlib.util

        supervision_spec = importlib.util.find_spec("supervision")
        inference_spec = importlib.util.find_spec("inference")

        if supervision_spec is None or inference_spec is None:
            print("  ⚠️  Local inference not available: missing modules.")
            print("  💡 Install with: pip install inference supervision")
            return None

        client = RoboflowClient(use_local_inference=True, model_id="yolov8n-640")
        result = client.detect_benches_in_image(image_path)

        if result.success:
            output_path = os.path.join(output_dir, "roboflow_local.jpg")
            pil_image = render_detections(image_path, result, "Roboflow Local")
            pil_image.save(output_path)
            return output_path
        else:
            print(f"  ❌ Failed: {result.error}")
            return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def test_roboflow_cloud(image_path: str, output_dir: str) -> Optional[str]:
    """Test Roboflow cloud API."""
    print("\n☁️  Testing Roboflow Cloud API...")
    try:
        # Check if API key is available
        from config import ROBOFLOW_API_KEY

        if not ROBOFLOW_API_KEY:
            print("  ⚠️  ROBOFLOW_API_KEY not set")
            print("  💡 Set environment variable: export ROBOFLOW_API_KEY=your_key")
            return None

        client = RoboflowClient(
            use_local_inference=False, model_id="streetview-benches-m4bc5/1"
        )
        result = client.detect_benches_in_image(image_path)

        if result.success:
            output_path = os.path.join(output_dir, "roboflow_cloud.jpg")
            pil_image = render_detections(image_path, result, "Roboflow Cloud")
            pil_image.save(output_path)
            return output_path
        else:
            if "413" in str(result.error):
                print(f"  ⚠️  Image too large for API: {result.error}")
                print("  💡 Try resizing the image or use local inference")
            else:
                print(f"  ❌ Failed: {result.error}")
            return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def test_ultralytics_local(image_path: str, output_dir: str) -> Optional[str]:
    """Test Ultralytics local inference."""
    print("\n🚀 Testing Ultralytics Local Inference...")
    try:
        client = UltralyticsClient(use_local=True)
        result = client.detect_benches_in_image(image_path)

        if result.success:
            output_path = os.path.join(output_dir, "ultralytics_local.jpg")
            pil_image = render_detections(image_path, result, "Ultralytics Local")
            pil_image.save(output_path)
            return output_path
        else:
            print(f"  ❌ Failed: {result.error}")
            return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def test_ultralytics_cloud(image_path: str, output_dir: str) -> Optional[str]:
    """Test Ultralytics cloud API."""
    print("\n☁️  Testing Ultralytics Cloud API...")
    try:
        # Check if API key is available
        from config import ULTRALYTICS_API_KEY

        if not ULTRALYTICS_API_KEY:
            print("  ⚠️  ULTRALYTICS_API_KEY not set")
            print("  💡 Set environment variable: export ULTRALYTICS_API_KEY=your_key")
            return None

        client = UltralyticsClient(use_local=False)
        result = client.detect_benches_in_image(image_path)

        if result.success:
            output_path = os.path.join(output_dir, "ultralytics_cloud.jpg")
            pil_image = render_detections(image_path, result, "Ultralytics Cloud")
            pil_image.save(output_path)
            return output_path
        else:
            print(f"  ❌ Failed: {result.error}")
            return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def test_multi_model(image_path: str, output_dir: str) -> Optional[str]:
    """Test Multi-model detection with fallback."""
    print("\n🔄 Testing Multi-Model Detection...")
    try:
        client = UnifiedMultiModelDetectionClient(
            enable_ultralytics=True, enable_roboflow_fallback=True
        )
        result = client.detect_benches_in_image(image_path)

        if result.success:
            output_path = os.path.join(output_dir, "multi_model.jpg")
            pil_image = render_detections(image_path, result, "Multi-Model")
            pil_image.save(output_path)
            return output_path
        else:
            print(f"  ❌ Failed: {result.error}")
            return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Test all bench detection configurations and display results in terminal"
    )
    parser.add_argument(
        "image_path",
        nargs="?",
        default="test_data/image.png",
        help="Path to the input image (default: test_data/image.png)",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to save annotated images (default: temporary directory)",
    )
    parser.add_argument(
        "--no-display", action="store_true", help="Don't display images in terminal"
    )
    parser.add_argument(
        "--configs",
        nargs="+",
        choices=[
            "roboflow-local",
            "roboflow-cloud",
            "ultralytics-local",
            "ultralytics-cloud",
            "multi-model",
        ],
        default=[
            "roboflow-local",
            "roboflow-cloud",
            "ultralytics-local",
            "ultralytics-cloud",
            "multi-model",
        ],
        help="Which configurations to test (default: all)",
    )

    args = parser.parse_args()

    # Validate input image
    if not os.path.exists(args.image_path):
        print(f"Error: Image file '{args.image_path}' not found.")
        sys.exit(1)

    print(f"🖼️  Loading image: {args.image_path}")

    # Prepare output directory
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        output_dir = args.output_dir
    else:
        output_dir = tempfile.mkdtemp(prefix="bench_detection_")

    print(f"📁 Output directory: {output_dir}")

    # Test configurations
    results = {}

    if "roboflow-local" in args.configs:
        results["roboflow-local"] = test_roboflow_local(args.image_path, output_dir)

    if "roboflow-cloud" in args.configs:
        results["roboflow-cloud"] = test_roboflow_cloud(args.image_path, output_dir)

    if "ultralytics-local" in args.configs:
        results["ultralytics-local"] = test_ultralytics_local(
            args.image_path, output_dir
        )

    if "ultralytics-cloud" in args.configs:
        results["ultralytics-cloud"] = test_ultralytics_cloud(
            args.image_path, output_dir
        )

    if "multi-model" in args.configs:
        results["multi-model"] = test_multi_model(args.image_path, output_dir)

    # Display results
    if not args.no_display:
        print("\n" + "=" * 80)
        print("🎯 DISPLAYING DETECTION RESULTS")
        print("=" * 80)

        for config, output_path in results.items():
            if output_path:
                display_image_in_terminal(output_path, config.replace("-", " ").title())
            else:
                print(f"\n❌ {config.replace('-', ' ').title()}: No results to display")

    # Summary
    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)

    successful_configs = [config for config, path in results.items() if path]
    failed_configs = [config for config, path in results.items() if not path]

    print(f"✅ Successful: {len(successful_configs)}/{len(results)}")
    for config in successful_configs:
        print(f"  - {config.replace('-', ' ').title()}")

    if failed_configs:
        print(f"\n❌ Failed: {len(failed_configs)}")
        for config in failed_configs:
            print(f"  - {config.replace('-', ' ').title()}")

    print(f"\n📁 All annotated images saved to: {output_dir}")

    if successful_configs:
        print(
            "\n💡 Tip: Use --no-display to skip terminal display and just save images"
        )
    else:
        print(
            "\n⚠️  No detections were successful. Check your API keys and model configurations."
        )


if __name__ == "__main__":
    main()
