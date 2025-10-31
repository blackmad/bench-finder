"""
Base detection client with unified interface and common detection result classes.
All detection clients should inherit from this base class.
"""

import logging
from abc import ABC, abstractmethod

from pydantic import Field

from bench_finder.models.unified_models import DetectionAttempt, DetectionResult


logger = logging.getLogger(__name__)


class MultiModelDetectionResult(DetectionResult):
    """Detection result from multi-model client with fallback information."""

    fallback_used: bool = Field(
        default=False, description="Whether fallback models were used"
    )
    total_attempts: int = Field(ge=1, description="Total number of detection attempts")
    detection_attempts: list[DetectionAttempt] = Field(
        default_factory=list, description="All detection attempts made"
    )


class DetectionClient(ABC):
    """Abstract base class for all detection clients."""

    def __init__(self, confidence_threshold: float = 0.5):
        """Initialize the detection client.

        Args:
            confidence_threshold: Minimum confidence threshold for detections
        """
        self.confidence_threshold = confidence_threshold
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def detect_benches_in_image(self, image_path: str) -> DetectionResult:
        """Detect benches in a single image.

        Args:
            image_path: Path to the image file

        Returns:
            DetectionResult with detection information
        """

    @abstractmethod
    def batch_detect_benches(self, image_paths: list[str]) -> list[DetectionResult]:
        """Detect benches in multiple images.

        Args:
            image_paths: List of image file paths

        Returns:
            List of DetectionResult objects
        """

    @abstractmethod
    def get_model_info(self) -> dict:
        """Get information about the model being used.

        Returns:
            Dictionary with model information
        """

    def validate_image_file(self, image_path: str) -> bool:
        """Validate that an image file exists and is readable.

        Args:
            image_path: Path to the image file

        Returns:
            True if valid, False otherwise
        """
        try:
            import os

            from PIL import Image

            if not os.path.exists(image_path):
                self.logger.warning(f"Image file does not exist: {image_path}")
                return False

            if os.path.getsize(image_path) == 0:
                self.logger.warning(f"Image file is empty: {image_path}")
                return False

            # Try to open as image to verify it's valid
            with Image.open(image_path) as img:
                img.verify()

            return True

        except Exception as e:
            self.logger.warning(f"Image validation failed for {image_path}: {e}")
            return False

    def _create_error_result(self, image_path: str, error: str) -> DetectionResult:
        """Create a standardized error result.

        Args:
            image_path: Path to the image that failed
            error: Error message

        Returns:
            DetectionResult with error information
        """
        return DetectionResult(
            image_path=image_path,
            success=False,
            has_bench=False,
            bench_count=0,
            max_confidence=0.0,
            detections=[],
            backend_name=self.__class__.__name__,
            model_id="unknown",
            confidence_threshold=self.confidence_threshold,
            error=error,
        )


class MultiModelDetectionClient(DetectionClient):
    """Base class for multi-model detection clients."""

    def __init__(self, confidence_threshold: float = 0.5):
        """Initialize the multi-model detection client.

        Args:
            confidence_threshold: Minimum confidence threshold for detections
        """
        super().__init__(confidence_threshold)
        self.all_attempts: list[DetectionAttempt] = []

    def get_detection_stats(self) -> dict:
        """Get statistics about detection attempts across all processed images.

        Returns:
            Dictionary with detection statistics
        """
        if not self.all_attempts:
            return {"total_attempts": 0, "no_data": True}

        stats: dict[str, float | int] = {
            "total_attempts": len(self.all_attempts),
            "successful_attempts": len(
                [a for a in self.all_attempts if a.success and a.has_bench]
            ),
            "failed_attempts": len([a for a in self.all_attempts if not a.success]),
            "no_bench_detected": len(
                [a for a in self.all_attempts if a.success and not a.has_bench]
            ),
        }

        # Calculate success rate
        if stats["total_attempts"] > 0:
            stats["success_rate"] = float(stats["successful_attempts"]) / float(
                stats["total_attempts"]
            )

        return stats

    def reset_stats(self) -> None:
        """Reset detection attempt statistics."""
        self.all_attempts = []
