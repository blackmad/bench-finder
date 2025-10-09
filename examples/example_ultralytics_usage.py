#!/usr/bin/env python3
"""
Example usage of the Ultralytics inference backend for bench detection.
This script demonstrates how to use the UltralyticsClient and store results in the database.
"""

import json
import logging
import os
import sys
from pathlib import Path


# Add the current directory to Python path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent))

from config import validate_config
from database import BenchDatabase
from ultralytics_client import UltralyticsClient


# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def demonstrate_ultralytics_detection(image_path: str):
    """
    Demonstrate bench detection using the Ultralytics backend.

    Args:
        image_path: Path to the image file to analyze
    """
    try:
        # Validate configuration
        validate_config()
        logger.info("Configuration validated successfully")

        # Initialize the Ultralytics client
        client = UltralyticsClient()
        logger.info("Ultralytics client initialized")

        # Print model info
        model_info = client.get_model_info()
        if model_info:
            logger.info(f"Model info: {json.dumps(model_info, indent=2)}")

        # Validate the image file
        if not client.validate_image_file(image_path):
            logger.error(f"Invalid image file: {image_path}")
            return

        # Run bench detection
        logger.info(f"Analyzing image: {image_path}")
        result = client.detect_benches_in_image(image_path)

        # Print results summary
        if result["success"]:
            logger.info("Detection successful!")
            logger.info(f"Benches found: {result['has_bench']}")
            logger.info(f"Bench count: {result['bench_count']}")
            logger.info(f"Max confidence: {result['max_confidence']:.3f}")

            if result.get("inference_time"):
                logger.info(f"Inference time: {result['inference_time']} ms")

            # Print detailed detection results
            if result["bench_detections"]:
                logger.info("Bench detections:")
                for i, detection in enumerate(result["bench_detections"], 1):
                    logger.info(f"  Detection {i}:")
                    logger.info(f"    Class: {detection['class']}")
                    logger.info(f"    Confidence: {detection['confidence']:.3f}")

                    # Print bounding box info
                    if detection.get("box"):
                        box = detection["box"]
                        logger.info(
                            f"    Bounding box: ({box.get('x1', 'N/A')}, {box.get('y1', 'N/A')}) to ({box.get('x2', 'N/A')}, {box.get('y2', 'N/A')})"
                        )

                    # Print segmentation info
                    if (
                        detection.get("segments")
                        and detection["segments"].get("x")
                        and detection["segments"].get("y")
                    ):
                        segments = detection["segments"]
                        num_points = len(segments["x"])
                        logger.info(f"    Segmentation: {num_points} coordinate points")
                        # Print first few coordinates as example
                        if num_points > 0:
                            logger.info(
                                f"    First point: ({segments['x'][0]:.1f}, {segments['y'][0]:.1f})"
                            )
                            if num_points > 1:
                                logger.info(
                                    f"    Last point: ({segments['x'][-1]:.1f}, {segments['y'][-1]:.1f})"
                                )

            # Show full response structure (abbreviated)
            logger.info("Full response structure:")
            full_response = result["full_response"]
            if "images" in full_response:
                num_images = len(full_response["images"])
                logger.info(f"  Images processed: {num_images}")

                if num_images > 0:
                    first_image = full_response["images"][0]
                    if "results" in first_image:
                        logger.info(
                            f"  Total detections (all classes): {len(first_image['results'])}"
                        )
                    if "shape" in first_image:
                        logger.info(f"  Image shape: {first_image['shape']}")
                    if "speed" in first_image:
                        speed = first_image["speed"]
                        logger.info(
                            f"  Processing times - Inference: {speed.get('inference', 'N/A')}ms, "
                            f"Preprocess: {speed.get('preprocess', 'N/A')}ms, "
                            f"Postprocess: {speed.get('postprocess', 'N/A')}ms"
                        )

        else:
            logger.error(f"Detection failed: {result.get('error', 'Unknown error')}")
            return

        # Demonstrate database storage
        logger.info("Storing results in database...")
        db = BenchDatabase()

        # Create a dummy search and bench for demonstration
        search_id = db.create_search("ultralytics_demo", 0.0, 0.0, 100)
        bench_data = {
            "osm_id": 999999,
            "osm_type": "node",
            "lat": 0.0,
            "lng": 0.0,
            "tags": {"amenity": "bench", "demo": "true"},
        }
        bench_id = db.add_bench(search_id, bench_data)

        # Add image record
        image_data = {
            "heading": 0,
            "filepath": image_path,
            "filename": os.path.basename(image_path),
            "file_size": os.path.getsize(image_path)
            if os.path.exists(image_path)
            else 0,
            "success": True,
        }
        image_id = db.add_image(bench_id, image_data)

        # Store the Ultralytics detection result
        detection_id = db.add_ultralytics_detection(image_id, result)
        logger.info(f"Stored detection result with ID: {detection_id}")

        return result

    except Exception:
        logger.exception("Error in demonstration")
        raise


def demonstrate_batch_processing(image_paths: list):
    """
    Demonstrate batch processing of multiple images.

    Args:
        image_paths: List of paths to image files
    """
    try:
        client = UltralyticsClient()
        logger.info(f"Starting batch processing of {len(image_paths)} images")

        results = client.batch_detect_benches(image_paths)

        # Summary statistics
        successful_count = sum(1 for r in results if r["success"])
        bench_images = sum(1 for r in results if r["has_bench"])
        total_benches = sum(r["bench_count"] for r in results)

        logger.info("Batch processing complete:")
        logger.info(f"  Successful detections: {successful_count}/{len(image_paths)}")
        logger.info(f"  Images with benches: {bench_images}")
        logger.info(f"  Total bench instances: {total_benches}")

        # Show results for each image
        for i, (image_path, result) in enumerate(zip(image_paths, results), 1):
            logger.info(
                f"Image {i} ({os.path.basename(image_path)}): "
                f"{'✓' if result['success'] else '✗'} "
                f"{'🪑' if result['has_bench'] else '❌'} "
                f"({result['bench_count']} benches, "
                f"max conf: {result['max_confidence']:.3f})"
            )

        return results

    except Exception:
        logger.exception("Error in batch demonstration")
        raise


if __name__ == "__main__":
    # Example usage
    if len(sys.argv) < 2:
        print(
            "Usage: python example_ultralytics_usage.py <image_path> [additional_image_paths...]"
        )
        print("Example: python example_ultralytics_usage.py path/to/image.jpg")
        sys.exit(1)

    image_paths = sys.argv[1:]

    if len(image_paths) == 1:
        # Single image demonstration
        demonstrate_ultralytics_detection(image_paths[0])
    else:
        # Batch processing demonstration
        demonstrate_batch_processing(image_paths)
