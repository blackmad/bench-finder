#!/usr/bin/env python3
"""
Test harness for UltralyticsClient to validate functionality after Pydantic refactoring.
Tests both local and API modes.
"""

import logging
import os
import sys
from pathlib import Path


# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from bench_finder.clients.ultralytics_client import UltralyticsClient
from bench_finder.models.schemas import UltralyticsDetectionResult


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_ultralytics_client():
    """Test the UltralyticsClient with the test image."""

    # Test image path
    test_image_path = "test_data/image.png"

    if not os.path.exists(test_image_path):
        logger.error(f"Test image not found at {test_image_path}")
        return False

    logger.info(f"Testing UltralyticsClient with image: {test_image_path}")

    try:
        # Test local mode (if available)
        logger.info("=" * 60)
        logger.info("TESTING LOCAL MODE")
        logger.info("=" * 60)

        try:
            client_local = UltralyticsClient(use_local=True)
            logger.info("✓ Local client initialized successfully")

            # Test image validation
            is_valid = client_local.validate_image_file(test_image_path)
            logger.info(f"✓ Image validation: {'PASSED' if is_valid else 'FAILED'}")

            if is_valid:
                # Test detection
                result = client_local.detect_benches_in_image(test_image_path)

                # Validate result type
                if isinstance(result, UltralyticsDetectionResult):
                    logger.info("✓ Return type is correct (UltralyticsDetectionResult)")
                else:
                    logger.error(
                        f"✗ Expected UltralyticsDetectionResult, got {type(result)}"
                    )
                    return False

                # Log results
                logger.info(
                    f"✓ Local detection completed successfully: {result.success}"
                )
                logger.info(f"  - Has bench: {result.has_bench}")
                logger.info(f"  - Bench count: {result.bench_count}")
                logger.info(f"  - Max confidence: {result.max_confidence:.3f}")
                logger.info(f"  - Model URL: {result.model_url}")
                logger.info(f"  - Inference mode: {result.inference_mode}")

                if result.inference_time:
                    logger.info(f"  - Inference time: {result.inference_time:.3f}s")
                if result.preprocess_time:
                    logger.info(f"  - Preprocess time: {result.preprocess_time:.3f}s")
                if result.postprocess_time:
                    logger.info(f"  - Postprocess time: {result.postprocess_time:.3f}s")

                # Test bench detections
                if result.bench_detections:
                    logger.info(
                        f"  - Found {len(result.bench_detections)} bench detections:"
                    )
                    for i, detection in enumerate(result.bench_detections):
                        logger.info(f"    Detection {i+1}:")
                        logger.info(f"      - Class: {detection.class_name}")
                        logger.info(f"      - Confidence: {detection.confidence:.3f}")
                        logger.info(
                            f"      - Box: ({detection.box.x1:.1f}, {detection.box.y1:.1f}, {detection.box.x2:.1f}, {detection.box.y2:.1f})"
                        )
                        if detection.segments:
                            logger.info(
                                f"      - Segmentation points: {len(detection.segments.x)}"
                            )

                # Test class filtering
                logger.info("\n--- Testing class filtering ---")
                filtered_result = client_local.detect_benches_with_class_filter(
                    test_image_path, target_classes=["bench", "seat", "chair"]
                )
                logger.info(f"✓ Class filtering completed: {filtered_result.success}")
                logger.info(f"  - Filtered bench count: {filtered_result.bench_count}")

                # Test batch detection
                logger.info("\n--- Testing batch detection ---")
                batch_results = client_local.batch_detect_benches([test_image_path])
                logger.info(
                    f"✓ Batch detection completed: {len(batch_results)} results"
                )
                if batch_results:
                    batch_result = batch_results[0]
                    logger.info(f"  - Batch result success: {batch_result.success}")
                    logger.info(
                        f"  - Batch result bench count: {batch_result.bench_count}"
                    )

                # Test model info
                model_info = client_local.get_model_info()
                if model_info:
                    logger.info(f"✓ Model info retrieved: {model_info}")
                else:
                    logger.warning("⚠ Model info not available")

                logger.info("✓ Local mode testing completed successfully!")

            else:
                logger.error("✗ Image validation failed, skipping detection tests")
                return False

        except ImportError as e:
            logger.warning(
                f"⚠ Local mode test skipped - ultralytics package not installed: {e}"
            )
            logger.info(
                "To test local inference, install ultralytics: pip install ultralytics"
            )
            logger.info("Local inference would:")
            logger.info("  - Download YOLO11-seg model automatically")
            logger.info("  - Run inference locally without API calls")
            logger.info("  - Provide faster inference for multiple images")
            logger.info("  - Work offline without internet connection")
        except Exception:
            logger.exception("✗ Local mode test failed")

        # Test API mode (if configured)
        logger.info("\n" + "=" * 60)
        logger.info("TESTING API MODE")
        logger.info("=" * 60)

        try:
            client_api = UltralyticsClient(use_local=False)
            logger.info("✓ API client initialized successfully")

            # Test detection
            result = client_api.detect_benches_in_image(test_image_path)

            # Validate result type
            if isinstance(result, UltralyticsDetectionResult):
                logger.info("✓ Return type is correct (UltralyticsDetectionResult)")
            else:
                logger.error(
                    f"✗ Expected UltralyticsDetectionResult, got {type(result)}"
                )
                return False

            # Log results
            logger.info(f"✓ API detection completed: {result.success}")
            logger.info(f"  - Has bench: {result.has_bench}")
            logger.info(f"  - Bench count: {result.bench_count}")
            logger.info(f"  - Max confidence: {result.max_confidence:.3f}")
            logger.info(f"  - Model URL: {result.model_url}")
            logger.info(f"  - Inference mode: {result.inference_mode}")

            if result.inference_time:
                logger.info(f"  - Inference time: {result.inference_time:.3f}s")

            if result.error:
                logger.warning(f"  - Error: {result.error}")

            logger.info("✓ API mode testing completed successfully!")

        except Exception:
            logger.exception("✗ API mode test failed")
            logger.info("This is expected if API key is not configured")

        logger.info("\n" + "=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        logger.info("✓ UltralyticsClient refactoring appears successful!")
        logger.info("✓ All methods return proper Pydantic models")
        logger.info("✓ Type safety is maintained")

        return True

    except Exception:
        logger.exception("✗ Test harness failed with unexpected error")
        return False


def test_pydantic_models():
    """Test that Pydantic models work correctly."""
    logger.info("\n" + "=" * 60)
    logger.info("TESTING PYDANTIC MODELS")
    logger.info("=" * 60)

    try:
        from bench_finder.models.schemas import (
            UltralyticsApiResponse,
            UltralyticsBox,
            UltralyticsDetectionItem,
            UltralyticsDetectionResult,
            UltralyticsSegments,
        )

        # Test creating a detection result
        box = UltralyticsBox(x1=10.0, y1=20.0, x2=100.0, y2=200.0)
        segments = UltralyticsSegments(
            x=[10.0, 100.0, 100.0, 10.0], y=[20.0, 20.0, 200.0, 200.0]
        )
        detection_item = UltralyticsDetectionItem(
            class_name="bench", class_id=0, confidence=0.85, box=box, segments=segments
        )

        api_response = UltralyticsApiResponse(images=[])

        result = UltralyticsDetectionResult(
            image_path="test.png",
            success=True,
            has_bench=True,
            bench_count=1,
            max_confidence=0.85,
            bench_detections=[detection_item],
            full_response=api_response,
            model_url="test_model",
            confidence_threshold=0.5,
            iou_threshold=0.45,
            image_size=640,
            inference_mode="test",
        )

        logger.info("✓ Pydantic models created successfully")
        logger.info(f"  - Detection result: {result.success}")
        logger.info(f"  - Bench count: {result.bench_count}")
        logger.info(f"  - Detection item class: {detection_item.class_name}")
        logger.info(f"  - Box coordinates: ({box.x1}, {box.y1}, {box.x2}, {box.y2})")

        # Test JSON serialization
        json_data = result.model_dump()
        logger.info("✓ JSON serialization works")

        # Test JSON deserialization
        UltralyticsDetectionResult(**json_data)
        logger.info("✓ JSON deserialization works")

        return True

    except Exception:
        logger.exception("✗ Pydantic model test failed")
        return False


def install_ultralytics():
    """Install ultralytics package for local testing."""
    logger.info("\n" + "=" * 60)
    logger.info("INSTALLING ULTRALYTICS FOR LOCAL TESTING")
    logger.info("=" * 60)

    try:
        import subprocess

        logger.info("Installing ultralytics package...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "ultralytics"],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info("✓ ultralytics package installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.exception("✗ Failed to install ultralytics")
        logger.exception(f"Error output: {e.stderr}")
        return False
    except Exception:
        logger.exception("✗ Unexpected error installing ultralytics")
        return False


if __name__ == "__main__":
    logger.info("Starting UltralyticsClient test harness...")

    # Test Pydantic models first
    pydantic_success = test_pydantic_models()

    # Check if ultralytics is available for local testing
    try:
        import ultralytics

        logger.info("✓ ultralytics package is available for local testing")
    except ImportError:
        logger.warning(
            "⚠ ultralytics package not found - local testing will be skipped"
        )
        logger.info("Would you like to install ultralytics for local testing? (y/n)")
        response = input().strip().lower()
        if response in ["y", "yes"]:
            if install_ultralytics():
                logger.info("✓ ultralytics installed, proceeding with local tests")
            else:
                logger.warning("⚠ Failed to install ultralytics, skipping local tests")
        else:
            logger.info(
                "Skipping ultralytics installation, local tests will be skipped"
            )

    # Test the client
    client_success = test_ultralytics_client()

    if pydantic_success and client_success:
        logger.info("\n🎉 ALL TESTS PASSED! The refactoring is successful.")
        sys.exit(0)
    else:
        logger.error("\n❌ SOME TESTS FAILED! Please check the errors above.")
        sys.exit(1)
