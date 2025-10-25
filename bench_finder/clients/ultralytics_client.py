"""
Ultralytics integration for bench detection using computer vision with segmentation.
Supports both local YOLO11-seg inference and Ultralytics API.
"""

import json
import logging
from pathlib import Path

import requests
from config import (
    ULTRALYTICS_API_KEY,
    ULTRALYTICS_CONFIDENCE_THRESHOLD,
    ULTRALYTICS_IMAGE_SIZE,
    ULTRALYTICS_IOU_THRESHOLD,
    ULTRALYTICS_LOCAL_MODEL,
    ULTRALYTICS_MODEL_URL,
    ULTRALYTICS_MODELS_DIR,
    ULTRALYTICS_USE_LOCAL,
)

from models.enums import DetectionSource
from models.unified_models import (
    BoundingBox,
    DetectionItem,
    DetectionResult,
    Polygon,
)

from .base_detection_client import DetectionClient


logger = logging.getLogger(__name__)


class UltralyticsClient(DetectionClient):
    """Client for Ultralytics inference supporting both local YOLO11-seg and API modes."""

    def __init__(self, use_local=None, confidence_threshold: float | None = None):
        """Initialize the Ultralytics client.

        Args:
            use_local: Override for local mode setting (for testing)
            confidence_threshold: Override confidence threshold (defaults to config value)
        """
        # Initialize base class with confidence threshold
        super().__init__(confidence_threshold or ULTRALYTICS_CONFIDENCE_THRESHOLD)

        # Allow override for testing purposes
        if use_local is not None:
            self.use_local = use_local
        else:
            self.use_local = ULTRALYTICS_USE_LOCAL

        self.iou_threshold = ULTRALYTICS_IOU_THRESHOLD
        self.image_size = ULTRALYTICS_IMAGE_SIZE

        if self.use_local:
            self._init_local_mode()
        else:
            self._init_api_mode()

    def _init_local_mode(self):
        """Initialize local YOLO inference mode."""
        logger.info("Initializing Ultralytics client in local inference mode")

        try:
            from ultralytics import YOLO

            self.YOLO = YOLO
        except ImportError as e:
            raise ImportError(
                "ultralytics package is required for local inference. Install with: pip install ultralytics"
            ) from e

        self.models_dir = Path(ULTRALYTICS_MODELS_DIR)
        self.models_dir.mkdir(exist_ok=True)

        self.local_model_path = self.models_dir / ULTRALYTICS_LOCAL_MODEL
        self.model_url = None
        self.api_key = None
        self.inference_url = None

        # Initialize the model (will download if needed)
        self._ensure_local_model()
        logger.info(f"Local YOLO model ready: {self.local_model_path}")

    def _init_api_mode(self):
        """Initialize API mode."""
        logger.info("Initializing Ultralytics client in API mode")

        if not ULTRALYTICS_API_KEY:
            raise ValueError("ULTRALYTICS_API_KEY is required for API mode")

        self.api_key = ULTRALYTICS_API_KEY
        self.model_url = ULTRALYTICS_MODEL_URL
        self.inference_url = "https://predict.ultralytics.com"
        self.local_model_path = None
        self.YOLO = None

    def _ensure_local_model(self):
        """Ensure the local YOLO model is available, download if necessary."""
        if not self.local_model_path.exists():
            logger.info(
                f"Local model not found at {self.local_model_path}, downloading {ULTRALYTICS_LOCAL_MODEL}..."
            )
            try:
                # Load model - this will automatically download if not present
                model = self.YOLO(ULTRALYTICS_LOCAL_MODEL)
                # Save to our models directory
                model.save(self.local_model_path)
                logger.info(f"Model downloaded and saved to {self.local_model_path}")
            except Exception:
                logger.exception(f"Failed to download model {ULTRALYTICS_LOCAL_MODEL}")
                raise

    def detect_benches_in_image(self, image_path: str) -> DetectionResult:
        """
        Detect benches in an image using either local YOLO11-seg or Ultralytics API.

        Args:
            image_path: Path to the image file

        Returns:
            DetectionResult with detection results including full segmentation data
        """
        if self.use_local:
            return self._detect_benches_local(image_path)
        else:
            return self._detect_benches_api(image_path)

    def _detect_benches_local(self, image_path: str) -> DetectionResult:
        """
        Detect benches using local YOLO11-seg model.

        Args:
            image_path: Path to the image file

        Returns:
            DetectionResult with detection results
        """
        try:
            logger.debug(f"Analyzing image for benches with local YOLO: {image_path}")

            # Load the model
            model = self.YOLO(self.local_model_path)

            # Run inference
            results = model(
                image_path,
                conf=self.confidence_threshold,
                iou=self.iou_threshold,
                imgsz=self.image_size,
                verbose=False,
            )

            # Process the results
            return self._process_local_detection_result(image_path, results)

        except FileNotFoundError:
            logger.exception(f"Image file not found: {image_path}")
            return self._create_error_result(image_path, "File not found")
        except Exception as e:
            logger.exception(f"Unexpected error analyzing image {image_path}")
            return self._create_error_result(image_path, f"Unexpected error: {e}")

    def _detect_benches_api(self, image_path: str) -> DetectionResult:
        """
        Detect benches using Ultralytics API.

        Args:
            image_path: Path to the image file

        Returns:
            DetectionResult with detection results
        """
        try:
            logger.debug(
                f"Analyzing image for benches with Ultralytics API: {image_path}"
            )

            # Prepare the API request headers and data
            headers = {"x-api-key": self.api_key}
            data = {
                "model": self.model_url,
                "imgsz": self.image_size,
                "conf": self.confidence_threshold,
                "iou": self.iou_threshold,
            }

            # Read the image file
            with open(image_path, "rb") as f:
                files = {"file": f}

                # Make the request
                response = requests.post(
                    self.inference_url,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=60,
                )

            if response.status_code != 200:
                logger.error(
                    f"Ultralytics API returned status {response.status_code}: {response.text}"
                )
                return self._create_error_result(
                    image_path, f"HTTP {response.status_code}: {response.text}"
                )

            # Parse the response
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                logger.exception("Failed to parse Ultralytics response")
                return self._create_error_result(image_path, f"JSON decode error: {e}")

            # Process the detection results
            return self._process_api_detection_result(image_path, result)

        except FileNotFoundError:
            logger.exception(f"Image file not found: {image_path}")
            return self._create_error_result(image_path, "File not found")
        except requests.exceptions.RequestException as e:
            logger.exception("Network error calling Ultralytics API")
            return self._create_error_result(image_path, f"Network error: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error analyzing image {image_path}")
            return self._create_error_result(image_path, f"Unexpected error: {e}")

    def _process_local_detection_result(
        self, image_path: str, results
    ) -> DetectionResult:
        """
        Process the local YOLO detection results into a standardized format.

        Args:
            image_path: Path to the analyzed image
            results: YOLO results object from local inference

        Returns:
            DetectionResult with processed detection data
        """
        try:
            # Extract timing information
            timing_info = {}
            if hasattr(results[0], "speed") and results[0].speed is not None:
                speed = results[0].speed
                timing_info = {
                    "inference_time": speed.get("inference", 0),
                    "preprocess_time": speed.get("preprocess", 0),
                    "postprocess_time": speed.get("postprocess", 0),
                }

            # Process detections
            bench_detections = []
            all_results = []

            for result in results:
                # Get the class names
                class_names = result.names if hasattr(result, "names") else {}

                if result.boxes is not None:
                    for i, box in enumerate(result.boxes):
                        # Get class information
                        class_id = int(box.cls.cpu().numpy())
                        class_name = class_names.get(
                            class_id, f"class_{class_id}"
                        ).lower()
                        confidence = float(box.conf.cpu().numpy())

                        # Get bounding box coordinates
                        xyxy = box.xyxy.cpu().numpy()[0]
                        bbox = BoundingBox(
                            x1=float(xyxy[0]),
                            y1=float(xyxy[1]),
                            x2=float(xyxy[2]),
                            y2=float(xyxy[3]),
                        )

                        # Get segmentation data if available
                        polygon = None
                        if result.masks is not None and i < len(result.masks.xy):
                            mask_points = result.masks.xy[i]
                            if len(mask_points) > 0:
                                # Convert to polygon format
                                coordinates = [
                                    [float(x), float(y)] for x, y in mask_points
                                ]
                                polygon = Polygon(coordinates=coordinates)

                        detection_item = DetectionItem(
                            confidence=confidence,
                            bbox=bbox,
                            class_name=class_names.get(class_id, f"class_{class_id}"),
                            polygon=polygon,
                        )

                        all_results.append(detection_item)

                        # Check if this is a bench detection
                        if (
                            "bench" in class_name
                            and confidence >= self.confidence_threshold
                        ):
                            bench_detections.append(detection_item)

            has_bench = len(bench_detections) > 0
            max_confidence = max((d.confidence for d in bench_detections), default=0.0)

            result_data = DetectionResult(
                image_path=image_path,
                success=True,
                has_bench=has_bench,
                bench_count=len(bench_detections),
                max_confidence=max_confidence,
                detections=bench_detections,
                backend_name="UltralyticsClient",
                model_id=str(self.local_model_path)
                if self.local_model_path
                else "local",
                confidence_threshold=self.confidence_threshold,
                source=DetectionSource.ULTRALYTICS,
                inference_time=timing_info.get("inference_time"),
                preprocess_time=timing_info.get("preprocess_time"),
                postprocess_time=timing_info.get("postprocess_time"),
                # Ultralytics-specific fields
                model_url=str(self.local_model_path) if self.local_model_path else None,
                iou_threshold=self.iou_threshold,
                image_size=self.image_size,
            )

            if has_bench:
                logger.info(
                    f"Bench detected in {image_path} - Count: {len(bench_detections)}, Max confidence: {max_confidence:.2f}"
                )
                # Log segmentation info for first bench detection
                if bench_detections and bench_detections[0].polygon:
                    polygon = bench_detections[0].polygon
                    logger.debug(
                        f"Segmentation points: {len(polygon.coordinates)} coordinates"
                    )
            else:
                logger.debug(f"No bench detected in {image_path}")

            return result_data

        except Exception as e:
            logger.exception(
                f"Error processing local detection result for {image_path}"
            )
            return self._create_error_result(image_path, f"Processing error: {e}")

    def _process_api_detection_result(
        self, image_path: str, api_result: dict
    ) -> DetectionResult:
        """
        Process the raw Ultralytics API result into a standardized format.

        Args:
            image_path: Path to the analyzed image
            api_result: Raw API response dictionary

        Returns:
            DetectionResult with processed detection data
        """
        try:
            # Extract timing information if available
            timing_info = {}
            if "images" in api_result and len(api_result["images"]) > 0:
                speed_info = api_result["images"][0].get("speed", {})
                timing_info = {
                    "inference_time": speed_info.get("inference"),
                    "preprocess_time": speed_info.get("preprocess"),
                    "postprocess_time": speed_info.get("postprocess"),
                }

            # Process results from all images (typically just one)
            bench_detections = []
            all_results = []

            for image_result in api_result.get("images", []):
                for result in image_result.get("results", []):
                    # Handle the actual API response format
                    # The API returns 'class' as an integer and 'name' as the class name
                    class_id = result.get("class", 0)
                    class_name = result.get("name", f"class_{class_id}")
                    confidence = result.get("confidence", 0)

                    # Convert API result to DetectionItem
                    box_data = result.get("box", {})
                    bbox = BoundingBox(
                        x1=box_data.get("x1", 0),
                        y1=box_data.get("y1", 0),
                        x2=box_data.get("x2", 0),
                        y2=box_data.get("y2", 0),
                    )

                    polygon = None
                    if result.get("segments"):
                        segments_data = result.get("segments", {})
                        if segments_data.get("x") and segments_data.get("y"):
                            coordinates = [
                                [x, y]
                                for x, y in zip(
                                    segments_data["x"], segments_data["y"], strict=False
                                )
                            ]
                            polygon = Polygon(coordinates=coordinates)

                    detection_item = DetectionItem(
                        confidence=confidence,
                        bbox=bbox,
                        class_name=class_name,
                        polygon=polygon,
                    )

                    all_results.append(detection_item)

                    # Check if this is a bench detection
                    class_name_lower = class_name.lower()

                    # Look for "bench" in the class name and check confidence
                    if (
                        "bench" in class_name_lower
                        and confidence >= self.confidence_threshold
                    ):
                        bench_detections.append(detection_item)

            has_bench = len(bench_detections) > 0
            max_confidence = max((d.confidence for d in bench_detections), default=0.0)

            result_data = DetectionResult(
                image_path=image_path,
                success=True,
                has_bench=has_bench,
                bench_count=len(bench_detections),
                max_confidence=max_confidence,
                detections=bench_detections,
                backend_name="UltralyticsClient",
                model_id=self.model_url or "unknown",
                confidence_threshold=self.confidence_threshold,
                source=DetectionSource.ULTRALYTICS,
                inference_time=timing_info.get("inference_time"),
                preprocess_time=timing_info.get("preprocess_time"),
                postprocess_time=timing_info.get("postprocess_time"),
                # Ultralytics-specific fields
                full_response=api_result,
                bench_detections=[d.dict() for d in bench_detections],
                model_url=self.model_url,
                iou_threshold=self.iou_threshold,
                image_size=self.image_size,
            )

            if has_bench:
                logger.info(
                    f"Bench detected in {image_path} - Count: {len(bench_detections)}, Max confidence: {max_confidence:.2f}"
                )
                # Log segmentation info for first bench detection
                if bench_detections and bench_detections[0].polygon:
                    polygon = bench_detections[0].polygon
                    logger.debug(
                        f"Segmentation points: {len(polygon.coordinates)} coordinates"
                    )
            else:
                logger.debug(f"No bench detected in {image_path}")

            return result_data

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
            backend_name="UltralyticsClient",
            model_id=str(self.local_model_path)
            if self.use_local
            else self.model_url or "unknown",
            confidence_threshold=self.confidence_threshold,
            source=DetectionSource.ULTRALYTICS,
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
        logger.info(
            f"Batch analyzing {len(image_paths)} images for benches with Ultralytics"
        )

        results = []
        successful_detections = 0
        benches_found = 0
        total_bench_count = 0

        for i, image_path in enumerate(image_paths, 1):
            logger.debug(f"Processing image {i}/{len(image_paths)}: {image_path}")

            result = self.detect_benches_in_image(image_path)
            results.append(result)

            if result.success:
                successful_detections += 1
                if result.has_bench:
                    benches_found += 1
                    total_bench_count += result.bench_count

        logger.info(
            f"Batch analysis complete - {successful_detections}/{len(image_paths)} successful, "
            f"{benches_found} images with benches detected, {total_bench_count} total bench instances"
        )

        return results

    def get_model_info(self) -> dict:
        """
        Get information about the Ultralytics model.

        Returns:
            Dictionary with model information
        """
        try:
            return {
                "model_url": str(self.local_model_path)
                if self.use_local
                else self.model_url,
                "confidence_threshold": self.confidence_threshold,
                "iou_threshold": self.iou_threshold,
                "image_size": self.image_size,
                "supports_segmentation": True,
                "mode": "local" if self.use_local else "api",
                "api_endpoint": self.inference_url if not self.use_local else None,
                "backend": "UltralyticsClient",
            }
        except Exception as e:
            logger.exception("Error getting model info")
            return {"error": str(e)}

    def detect_benches_with_class_filter(
        self, image_path: str, target_classes: list[str] | None = None
    ) -> DetectionResult:
        """
        Detect benches in an image with specific class filtering.

        Args:
            image_path: Path to the image file
            target_classes: List of class names to look for (defaults to bench-related terms)

        Returns:
            DetectionResult with filtered detection results
        """
        if target_classes is None:
            target_classes = ["bench", "seat", "chair"]  # Default bench-related classes

        result = self.detect_benches_in_image(image_path)

        if not result.success:
            return result

        # Filter detections to only include target classes
        filtered_detections = []
        for detection in result.detections:
            class_name = detection.class_name.lower()
            if any(target_class in class_name for target_class in target_classes):
                filtered_detections.append(detection)

        # Create new result with filtered detections
        filtered_result = DetectionResult(
            image_path=result.image_path,
            success=result.success,
            has_bench=len(filtered_detections) > 0,
            bench_count=len(filtered_detections),
            max_confidence=max(
                (d.confidence for d in filtered_detections), default=0.0
            ),
            detections=filtered_detections,
            backend_name=result.backend_name,
            model_id=result.model_id,
            confidence_threshold=result.confidence_threshold,
            inference_time=result.inference_time,
            preprocess_time=result.preprocess_time,
            postprocess_time=result.postprocess_time,
            error=result.error,
        )

        return filtered_result
