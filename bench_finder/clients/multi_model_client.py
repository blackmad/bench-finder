"""
Multi-model detection client that implements fallback detection logic.
Tries Ultralytics first, then falls back to multiple Roboflow models.
"""

import logging

from bench_finder.clients.base_detection_client import (
    MultiModelDetectionClient,
    MultiModelDetectionResult,
)
from bench_finder.clients.roboflow_client import RoboflowClient
from bench_finder.clients.ultralytics_client import UltralyticsClient
from bench_finder.config import (
    ROBOFLOW_API_KEY,
    ROBOFLOW_MODELS,
    ULTRALYTICS_API_KEY,
    ULTRALYTICS_USE_LOCAL,
)
from bench_finder.models.enums import DetectionSource
from bench_finder.models.unified_models import (
    DetectionAttempt,
    DetectionResult,
)


logger = logging.getLogger(__name__)


def _convert_ultralytics_to_standard(
    ultralytics_result: DetectionResult,
) -> DetectionResult:
    """Convert Ultralytics result to standard DetectionResult (already in correct format)."""
    return ultralytics_result


def _convert_roboflow_to_standard(roboflow_result: DetectionResult) -> DetectionResult:
    """Convert Roboflow result to standard DetectionResult (already in correct format)."""
    return roboflow_result


class MultiModelRoboflowClient:
    """Enhanced Roboflow client that tries multiple models."""

    def __init__(self, models_config: list[dict]):
        """Initialize with multiple model configurations.

        Args:
            models_config: List of model configuration dictionaries
        """
        if not ROBOFLOW_API_KEY:
            raise ValueError("ROBOFLOW_API_KEY is required for Roboflow models")

        # Sort models by priority (lower number = higher priority)
        self.models_config = sorted(models_config, key=lambda x: x.get("priority", 999))
        self.api_key = ROBOFLOW_API_KEY
        logger.info(
            f"Initialized MultiModelRoboflowClient with {len(self.models_config)} models"
        )

        # Log model order
        for i, model in enumerate(self.models_config, 1):
            logger.info(
                f"  {i}. {model['name']} ({model['id']}) - threshold: {model['confidence_threshold']}"
            )

    def detect_benches_in_image(
        self, image_path: str
    ) -> tuple[DetectionResult, list[DetectionAttempt]]:
        """
        Try detecting benches using multiple Roboflow models until one succeeds.

        Args:
            image_path: Path to the image file

        Returns:
            Tuple of (best_result, all_attempts)
        """
        attempts = []
        best_result = None

        logger.debug(
            f"Trying {len(self.models_config)} Roboflow models for {image_path}"
        )

        for model_config in self.models_config:
            model_id = model_config["id"]
            model_name = model_config["name"]
            confidence_threshold = model_config["confidence_threshold"]

            logger.debug(f"Trying Roboflow model: {model_name} ({model_id})")

            try:
                # Create a temporary RoboflowClient for this specific model
                temp_client = RoboflowClient(model_id=model_id)
                temp_client.confidence_threshold = confidence_threshold

                # Attempt detection
                result = temp_client.detect_benches_in_image(image_path)

                # Record the attempt
                attempt = DetectionAttempt(
                    model_type=DetectionSource.ROBOFLOW,
                    model_id=model_id,
                    success=result.success,
                    has_bench=result.has_bench,
                    confidence=result.max_confidence,
                    error=result.error,
                )
                attempts.append(attempt)

                # If this model detected a bench, use it as the result
                if result.success and result.has_bench:
                    logger.info(
                        f"✅ Bench detected by {model_name}: confidence {result.max_confidence:.2f}"
                    )
                    # Create DetectionResult with metadata
                    best_result = DetectionResult(
                        image_path=result.image_path,
                        success=result.success,
                        has_bench=result.has_bench,
                        bench_count=result.bench_count,
                        max_confidence=result.max_confidence,
                        detections=result.detections,
                        backend_name="roboflow",
                        model_id=model_id,
                        confidence_threshold=confidence_threshold,
                        error=result.error,
                        inference_time=result.inference_time,
                        preprocess_time=result.preprocess_time,
                        postprocess_time=result.postprocess_time,
                        source=DetectionSource.ROBOFLOW,
                        # full_response=result.full_response,
                        # bench_detections=result.bench_detections,
                        model_url=result.model_url,
                        iou_threshold=result.iou_threshold,
                        image_size=result.image_size,
                    )
                    break
                elif result.success:
                    logger.debug(f"❌ No bench detected by {model_name}")
                else:
                    logger.debug(
                        f"❌ {model_name} failed: {result.error or 'Unknown error'}"
                    )

            except Exception as e:
                logger.exception(
                    f"Error with Roboflow model {model_name} - id {model_id}"
                )
                attempt = DetectionAttempt(
                    model_type=DetectionSource.ROBOFLOW,
                    model_id=model_id,
                    success=False,
                    has_bench=False,
                    confidence=0.0,
                    error=str(e),
                )
                attempts.append(attempt)
                continue

        # If no model detected a bench, return the last result or create an error result
        if best_result is None:
            if attempts:
                # Use the last attempt's result, but mark it as the "best" available
                last_attempt = attempts[-1]
                best_result = DetectionResult(
                    image_path=image_path,
                    success=False,
                    has_bench=False,
                    bench_count=0,
                    max_confidence=0.0,
                    detections=[],
                    backend_name="roboflow",
                    model_id=last_attempt.model_id,
                    confidence_threshold=0.0,
                    error=f"No bench detected by any of {len(self.models_config)} Roboflow models",
                    source=DetectionSource.ROBOFLOW,
                )
            else:
                best_result = DetectionResult(
                    image_path=image_path,
                    success=False,
                    has_bench=False,
                    bench_count=0,
                    max_confidence=0.0,
                    detections=[],
                    backend_name="roboflow",
                    model_id=None,
                    confidence_threshold=0.0,
                    error="All Roboflow models failed",
                    source=DetectionSource.ROBOFLOW,
                )

        return best_result, attempts


class UnifiedMultiModelDetectionClient(MultiModelDetectionClient):
    """
    Multi-model detection client that implements fallback logic:
    1. Try Ultralytics first
    2. If no bench detected, try multiple Roboflow models in priority order
    3. Stop as soon as any model detects a bench
    """

    def __init__(
        self,
        enable_ultralytics: bool = True,
        enable_roboflow_fallback: bool = True,
        confidence_threshold: float = 0.5,
    ):
        """
        Initialize the multi-model detection client.

        Args:
            enable_ultralytics: Whether to try Ultralytics first
            enable_roboflow_fallback: Whether to use Roboflow fallback models
            confidence_threshold: Minimum confidence threshold for detections
        """
        super().__init__(confidence_threshold)
        self.enable_ultralytics = enable_ultralytics
        self.enable_roboflow_fallback = enable_roboflow_fallback

        # Initialize Ultralytics client if enabled and API key available
        self.ultralytics_client = None
        if enable_ultralytics:
            try:
                if ULTRALYTICS_API_KEY or ULTRALYTICS_USE_LOCAL:
                    self.ultralytics_client = UltralyticsClient()
                    logger.info("✅ Ultralytics client initialized")
                else:
                    logger.warning(
                        "⚠️  Ultralytics disabled: no API key or local inference not enabled"
                    )
                    self.enable_ultralytics = False
            except Exception:
                logger.exception("❌ Failed to initialize Ultralytics client")
                self.enable_ultralytics = False

        # Initialize Roboflow fallback client if enabled
        self.roboflow_client = None
        if enable_roboflow_fallback:
            try:
                if ROBOFLOW_API_KEY and ROBOFLOW_MODELS:
                    self.roboflow_client = MultiModelRoboflowClient(ROBOFLOW_MODELS)
                    logger.info("✅ Multi-model Roboflow client initialized")
                else:
                    logger.warning(
                        "⚠️  Roboflow fallback disabled: no API key or models configured"
                    )
                    self.enable_roboflow_fallback = False
            except Exception:
                logger.exception("❌ Failed to initialize Roboflow client")
                self.enable_roboflow_fallback = False

        if not self.enable_ultralytics and not self.enable_roboflow_fallback:
            raise ValueError(
                "At least one detection backend must be enabled and properly configured"
            )

        logger.info(
            f"MultiModelDetectionClient ready - Ultralytics: {self.enable_ultralytics}, Roboflow: {self.enable_roboflow_fallback}"
        )

    def detect_benches_in_image(self, image_path: str) -> DetectionResult:
        """
        Detect benches using fallback logic: Ultralytics first, then Roboflow models.

        Args:
            image_path: Path to the image file

        Returns:
            DetectionResult with enhanced metadata
        """
        detection_attempts = []
        final_result = None

        logger.debug(f"🔍 Starting multi-model detection for {image_path}")

        # Step 1: Try Ultralytics first
        if self.enable_ultralytics and self.ultralytics_client:
            logger.debug("🚀 Trying Ultralytics first...")
            try:
                ultralytics_result: DetectionResult = (
                    self.ultralytics_client.detect_benches_in_image(image_path)
                )

                attempt = DetectionAttempt(
                    model_type=DetectionSource.ULTRALYTICS,
                    model_id="ultralytics",
                    success=ultralytics_result.success,
                    has_bench=ultralytics_result.has_bench,
                    confidence=ultralytics_result.max_confidence,
                    error=ultralytics_result.error,
                )
                detection_attempts.append(attempt)

                if ultralytics_result.success and ultralytics_result.has_bench:
                    logger.info(
                        f"✅ Ultralytics detected bench: confidence {ultralytics_result.max_confidence:.2f}"
                    )
                    # Convert to multi-model result format
                    final_result = MultiModelDetectionResult(
                        image_path=ultralytics_result.image_path,
                        success=ultralytics_result.success,
                        has_bench=ultralytics_result.has_bench,
                        bench_count=ultralytics_result.bench_count,
                        max_confidence=ultralytics_result.max_confidence,
                        detections=ultralytics_result.detections,
                        backend_name=ultralytics_result.backend_name,
                        model_id=ultralytics_result.model_id,
                        confidence_threshold=ultralytics_result.confidence_threshold,
                        source=ultralytics_result.source,
                        inference_time=ultralytics_result.inference_time,
                        preprocess_time=ultralytics_result.preprocess_time,
                        postprocess_time=ultralytics_result.postprocess_time,
                        error=ultralytics_result.error,
                        # Ultralytics-specific fields
                        # full_response=ultralytics_result.full_response,
                        # bench_detections=ultralytics_result.bench_detections,
                        model_url=ultralytics_result.model_url,
                        iou_threshold=ultralytics_result.iou_threshold,
                        image_size=ultralytics_result.image_size,
                        fallback_used=False,
                        total_attempts=1,
                        detection_attempts=detection_attempts,
                    )
                elif ultralytics_result.success:
                    logger.debug(
                        "❌ Ultralytics: No bench detected, trying fallback models..."
                    )
                else:
                    logger.debug(
                        f"❌ Ultralytics failed: {ultralytics_result.error or 'Unknown error'}"
                    )
            except Exception as e:
                logger.exception("❌ Ultralytics detection failed")
                attempt = DetectionAttempt(
                    model_type=DetectionSource.ULTRALYTICS,
                    model_id="ultralytics",
                    success=False,
                    has_bench=False,
                    confidence=0.0,
                    error=str(e),
                )
                detection_attempts.append(attempt)

        # Step 2: If Ultralytics didn't detect a bench, try Roboflow fallback models
        if (
            final_result is None
            and self.enable_roboflow_fallback
            and self.roboflow_client
        ):
            logger.debug("🔄 Falling back to Roboflow models...")
            try:
                roboflow_result, roboflow_attempts = (
                    self.roboflow_client.detect_benches_in_image(image_path)
                )
                detection_attempts.extend(roboflow_attempts)

                if roboflow_result.success and roboflow_result.has_bench:
                    logger.info(
                        f"✅ Fallback successful: {roboflow_result.model_id} detected bench"
                    )
                    # Convert DetectionResult to MultiModelDetectionResult
                    final_result = MultiModelDetectionResult(
                        image_path=roboflow_result.image_path,
                        success=roboflow_result.success,
                        has_bench=roboflow_result.has_bench,
                        bench_count=roboflow_result.bench_count,
                        max_confidence=roboflow_result.max_confidence,
                        detections=roboflow_result.detections,
                        backend_name=roboflow_result.backend_name,
                        model_id=roboflow_result.model_id,
                        confidence_threshold=roboflow_result.confidence_threshold,
                        source=roboflow_result.source,
                        inference_time=roboflow_result.inference_time,
                        preprocess_time=roboflow_result.preprocess_time,
                        postprocess_time=roboflow_result.postprocess_time,
                        error=roboflow_result.error,
                        # full_response=roboflow_result.full_response,
                        # bench_detections=roboflow_result.bench_detections,
                        model_url=roboflow_result.model_url,
                        iou_threshold=roboflow_result.iou_threshold,
                        image_size=roboflow_result.image_size,
                        fallback_used=True,
                        total_attempts=len(detection_attempts),
                        detection_attempts=detection_attempts,
                    )
                else:
                    logger.debug("❌ All fallback models failed to detect bench")

            except Exception:
                logger.exception("❌ Roboflow fallback failed")

        # Step 3: If no model detected a bench, create a comprehensive failure result
        if final_result is None:
            logger.debug("❌ All detection models failed")
            final_result = MultiModelDetectionResult(
                image_path=image_path,
                success=False,
                has_bench=False,
                bench_count=0,
                max_confidence=0.0,
                detections=[],
                backend_name="multi_model",
                model_id="unknown",
                confidence_threshold=self.confidence_threshold,
                source=DetectionSource.MULTI_MODEL,
                fallback_used=len(detection_attempts) > 1,
                total_attempts=len(detection_attempts),
                detection_attempts=detection_attempts,
                error=f"No bench detected by any model ({len(detection_attempts)} attempts)",
            )

        # Store attempts for analysis
        self.all_attempts.extend(detection_attempts)

        return final_result

    def batch_detect_benches(self, image_paths: list[str]) -> list[DetectionResult]:
        """
        Detect benches in multiple images.

        Args:
            image_paths: List of image file paths

        Returns:
            List of DetectionResult objects
        """
        results = []
        for image_path in image_paths:
            result = self.detect_benches_in_image(image_path)
            results.append(result)
        return results

    def get_model_info(self) -> dict:
        """
        Get information about the multi-model detection setup.

        Returns:
            Dictionary with model information
        """
        info = {
            "backend": "UnifiedMultiModelDetectionClient",
            "confidence_threshold": self.confidence_threshold,
            "enable_ultralytics": self.enable_ultralytics,
            "enable_roboflow_fallback": self.enable_roboflow_fallback,
        }

        if self.ultralytics_client:
            info["ultralytics_info"] = self.ultralytics_client.get_model_info()

        if self.roboflow_client:
            info["roboflow_models_count"] = len(self.roboflow_client.models_config)

        return info
