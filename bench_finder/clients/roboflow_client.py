"""
Roboflow integration for bench detection using computer vision.
Supports both local inference (default) and cloud API as fallback.
"""

import base64
import json
import logging
from typing import Any

import cv2
import requests
from config import ROBOFLOW_API_KEY, ROBOFLOW_CONFIDENCE_THRESHOLD, ROBOFLOW_MODEL_ID

from api.api_models import (
    CacheStatus,
    ModelCacheInfo,
)
from models.unified_models import (
    BoundingBox,
    DetectionItem,
    DetectionResult,
)

from .base_detection_client import DetectionClient


logger = logging.getLogger(__name__)

# Global model cache to avoid reinitializing models
_MODEL_CACHE: dict[str, Any] = {}


def get_cache_info() -> ModelCacheInfo:
    """Get information about the current model cache."""
    return ModelCacheInfo(
        cached_models=list(_MODEL_CACHE.keys()), cache_size=len(_MODEL_CACHE)
    )


def clear_model_cache() -> None:
    """Clear the global model cache to free up memory."""
    cached_count = len(_MODEL_CACHE)
    _MODEL_CACHE.clear()
    logger.info(f"Cleared model cache ({cached_count} models removed)")


class RoboflowClient(DetectionClient):
    """Client for Roboflow inference - supports both local and cloud inference."""

    def __init__(
        self,
        use_local_inference: bool = True,
        model_id: str | None = None,
        confidence_threshold: float | None = None,
    ):
        """Initialize the Roboflow client.

        Args:
            use_local_inference: Whether to use local inference (default: True)
            model_id: Model ID to use (defaults to config value or 'yolov8n-640' for local)
            confidence_threshold: Override confidence threshold (defaults to config value)
        """
        # Initialize base class with confidence threshold
        super().__init__(confidence_threshold or ROBOFLOW_CONFIDENCE_THRESHOLD)

        # Import local inference dependencies
        try:
            from inference import get_model

            LOCAL_INFERENCE_AVAILABLE = True
        except ImportError as e:
            LOCAL_INFERENCE_AVAILABLE = False
            print(f"Local inference not available: {e}. Falling back to cloud API.")

        self.use_local_inference = use_local_inference and LOCAL_INFERENCE_AVAILABLE
        self.local_model = None

        if self.use_local_inference:
            # Setup local inference
            self.model_id = model_id  # or "yolov8n-640"  # Default to YOLOv8n for local
            if not self.model_id:
                raise ValueError("model_id is required for local inference")

            # Check if model is already cached
            cache_key = f"local_{self.model_id}"
            if cache_key in _MODEL_CACHE:
                logger.debug(f"Using cached local model: {self.model_id}")
                self.local_model = _MODEL_CACHE[cache_key]
            else:
                logger.info(f"Loading local inference model: {self.model_id}")
                try:
                    self.local_model = get_model(model_id=self.model_id)
                    # Cache the model for future use
                    _MODEL_CACHE[cache_key] = self.local_model
                    logger.info(
                        f"Local inference model loaded and cached successfully: {self.model_id}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to load local model: {e}. Falling back to cloud API."
                    )
                    self.use_local_inference = False

        if not self.use_local_inference:
            # Setup cloud API
            if not ROBOFLOW_API_KEY:
                raise ValueError("ROBOFLOW_API_KEY is required for cloud inference")

            self.api_key = ROBOFLOW_API_KEY
            self.model_id = model_id or ROBOFLOW_MODEL_ID
            self.base_url = f"https://detect.roboflow.com/{self.model_id}"
            logger.info(f"Using cloud API with model: {self.model_id}")

    def detect_benches_in_image(self, image_path: str) -> DetectionResult:
        """
        Detect benches in an image using local inference or cloud API.

        Args:
            image_path: Path to the image file

        Returns:
            DetectionResult with detection results
        """
        logger.debug(f"Analyzing image for benches: {image_path}")

        if self.use_local_inference:
            return self._detect_benches_local(image_path)
        else:
            return self._detect_benches_cloud(image_path)

    def _detect_benches_local(self, image_path: str) -> DetectionResult:
        """
        Detect benches using local inference.

        Args:
            image_path: Path to the image file

        Returns:
            DetectionResult with detection results
        """
        if not self.local_model:
            raise ValueError("Local model not loaded")

        try:
            # Load image using cv2
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Could not load image: {image_path}")
                return self._create_error_result(image_path, "Could not load image")

            # Run inference
            results = self.local_model.infer(image)

            # Convert to standard format
            if isinstance(results, list) and len(results) > 0:
                result_dict = results[0].dict(by_alias=True, exclude_none=True)
            else:
                result_dict = (
                    results.dict(by_alias=True, exclude_none=True)
                    if hasattr(results, "dict")
                    else {"predictions": []}
                )

            # Process the detection results
            return self._process_detection_result(
                image_path, result_dict, is_local=True
            )

        except FileNotFoundError:
            logger.exception(f"Image file not found: {image_path}")
            return self._create_error_result(image_path, "File not found")
        except Exception as e:
            logger.exception(f"Unexpected error in local inference for {image_path}")
            return self._create_error_result(image_path, f"Local inference error: {e}")

    def _detect_benches_cloud(self, image_path: str) -> DetectionResult:
        """
        Detect benches using cloud API.

        Args:
            image_path: Path to the image file

        Returns:
            DetectionResult with detection results
        """
        try:
            # Read and encode the image
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
                encoded_image = base64.b64encode(image_data).decode("utf-8")

            # Prepare the API request
            url = f"{self.base_url}?api_key={self.api_key}&confidence={self.confidence_threshold}"

            # Make the request
            response = requests.post(
                url,
                data=encoded_image,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )

            if response.status_code != 200:
                logger.error(
                    f"Roboflow API returned status {response.status_code}: {response.text}"
                )
                return self._create_error_result(
                    image_path, f"HTTP {response.status_code}"
                )

            # Parse the response
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                logger.exception("Failed to parse Roboflow response")
                return self._create_error_result(image_path, f"JSON decode error: {e}")

            # Process the detection results
            return self._process_detection_result(image_path, result, is_local=False)

        except FileNotFoundError:
            logger.exception(f"Image file not found: {image_path}")
            return self._create_error_result(image_path, "File not found")
        except requests.exceptions.RequestException as e:
            logger.exception("Network error calling Roboflow API")
            return self._create_error_result(image_path, f"Network error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error in cloud inference for {image_path}")
            return self._create_error_result(image_path, f"Cloud inference error: {e}")

    def _process_detection_result(
        self, image_path: str, api_result: dict, is_local: bool = False
    ) -> DetectionResult:
        """
        Process the raw inference result into a standardized format.

        Args:
            image_path: Path to the analyzed image
            api_result: Raw inference response dictionary
            is_local: Whether this is from local inference

        Returns:
            DetectionResult with processed detection data
        """
        try:
            predictions = api_result.get("predictions", [])

            # Filter predictions to only include benches above confidence threshold
            bench_detections = []
            for prediction in predictions:
                # Check if this is a bench detection with sufficient confidence
                class_name = prediction.get("class", "").lower()
                confidence = prediction.get("confidence", 0)

                # For local inference, look for relevant object classes that might be benches
                # YOLOv8n detects 'person', 'chair', 'couch', etc. - we'll be flexible
                is_bench_like = False
                if is_local:
                    # Accept various furniture/seating objects as potential benches
                    bench_keywords = ["bench", "chair", "couch", "sofa", "seat"]
                    is_bench_like = any(
                        keyword in class_name for keyword in bench_keywords
                    )
                else:
                    # Cloud API should specifically detect benches
                    is_bench_like = "bench" in class_name

                if is_bench_like and confidence >= self.confidence_threshold:
                    # Convert Roboflow format (center coordinates + width/height) to bounding box
                    x_center = prediction.get("x", 0)
                    y_center = prediction.get("y", 0)
                    width = prediction.get("width", 0)
                    height = prediction.get("height", 0)

                    # Convert to corner coordinates
                    x1 = x_center - width / 2
                    y1 = y_center - height / 2
                    x2 = x_center + width / 2
                    y2 = y_center + height / 2

                    bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)

                    detection_item = DetectionItem(
                        confidence=confidence,
                        bbox=bbox,
                        class_name=prediction.get("class", "bench"),
                    )
                    bench_detections.append(detection_item)

            has_bench = len(bench_detections) > 0
            max_confidence = max((d.confidence for d in bench_detections), default=0.0)

            result = DetectionResult(
                image_path=image_path,
                success=True,
                has_bench=has_bench,
                bench_count=len(bench_detections),
                max_confidence=max_confidence,
                detections=bench_detections,
                backend_name="RoboflowClient",
                model_id=self.model_id or "unknown",
                confidence_threshold=self.confidence_threshold,
                source="roboflow",
            )

            if has_bench:
                inference_type = "local" if is_local else "cloud"
                logger.info(
                    f"Bench detected in {image_path} ({inference_type}) - Count: {len(bench_detections)}, Max confidence: {max_confidence:.2f}"
                )
            else:
                logger.debug(f"No bench detected in {image_path}")

            return result

        except Exception as e:
            logger.exception(f"Error processing detection result for {image_path}")
            return self._create_error_result(image_path, f"Processing error: {e}")

    def _create_error_result(self, image_path: str, error: str) -> DetectionResult:
        """Create a standardized error result."""
        return DetectionResult(
            image_path=image_path,
            success=False,
            has_bench=False,
            bench_count=0,
            max_confidence=0.0,
            detections=[],
            backend_name="RoboflowClient",
            model_id=self.model_id,
            confidence_threshold=self.confidence_threshold,
            source="roboflow",
            error=error,
        )

    def batch_detect_benches(self, image_paths: list[str]) -> list[DetectionResult]:
        """
        Detect benches in multiple images.

        Args:
            image_paths: List of image file paths

        Returns:
            List of DetectionResult objects
        """
        logger.info(f"Batch analyzing {len(image_paths)} images for benches")

        results = []
        successful_detections = 0
        benches_found = 0

        for i, image_path in enumerate(image_paths, 1):
            logger.debug(f"Processing image {i}/{len(image_paths)}: {image_path}")

            result = self.detect_benches_in_image(image_path)
            results.append(result)

            if result.success:
                successful_detections += 1
                if result.has_bench:
                    benches_found += 1

        logger.info(
            f"Batch analysis complete - {successful_detections}/{len(image_paths)} successful, "
            f"{benches_found} images with benches detected"
        )

        return results

    def get_model_info(self) -> dict:
        """
        Get information about the Roboflow model.

        Returns:
            Dictionary with model information
        """
        try:
            return {
                "model_id": self.model_id,
                "confidence_threshold": self.confidence_threshold,
                "use_local_inference": self.use_local_inference,
                "classes": ["bench"],  # This model is specifically for bench detection
                "backend": "RoboflowClient",
            }
        except Exception as e:
            logger.exception("Error getting model info")
            return {"error": str(e)}

    def get_cache_status(self) -> CacheStatus:
        """Get cache status information for this client."""
        cache_info = get_cache_info()
        cache_key = f"local_{self.model_id}" if self.use_local_inference else None

        return CacheStatus(
            use_local_inference=self.use_local_inference,
            model_id=self.model_id,
            model_cached=cache_key in _MODEL_CACHE if cache_key else False,
            cache_key=cache_key,
            total_cached_models=cache_info.cache_size,
            all_cached_models=cache_info.cached_models,
        )
