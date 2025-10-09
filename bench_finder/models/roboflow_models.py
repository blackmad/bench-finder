"""
Pydantic models for Roboflow API responses and detection results.
"""

from typing import Any, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


class RoboflowBoundingBox(BaseModel):
    """Bounding box for a detection."""

    x: float = Field(..., description="Center X coordinate")
    y: float = Field(..., description="Center Y coordinate")
    width: float = Field(..., description="Bounding box width")
    height: float = Field(..., description="Bounding box height")

    @property
    def area(self) -> float:
        """Calculate the area of the bounding box."""
        return self.width * self.height

    @property
    def top_left(self) -> tuple[float, float]:
        """Get top-left corner coordinates."""
        return (self.x - self.width / 2, self.y - self.height / 2)

    @property
    def bottom_right(self) -> tuple[float, float]:
        """Get bottom-right corner coordinates."""
        return (self.x + self.width / 2, self.y + self.height / 2)


class RoboflowPrediction(BaseModel):
    """A single prediction from Roboflow."""

    class_name: str = Field(..., alias="class", description="Detected object class")
    confidence: float = Field(..., description="Detection confidence score (0-1)")
    bounding_box: RoboflowBoundingBox = Field(..., description="Object bounding box")

    # Allow creation from dict with different field names
    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoboflowPrediction":
        """Create prediction from dictionary with flexible field mapping."""
        # Handle different response formats
        bbox = RoboflowBoundingBox(
            x=data.get("x", 0),
            y=data.get("y", 0),
            width=data.get("width", 0),
            height=data.get("height", 0),
        )

        return cls(
            class_name=data.get("class", data.get("class_name", "unknown")),
            confidence=data.get("confidence", 0.0),
            bounding_box=bbox,
        )

    @property
    def is_bench_like(self) -> bool:
        """Check if this prediction is bench-like."""
        bench_keywords = ["bench", "chair", "couch", "sofa", "seat"]
        return any(keyword in self.class_name.lower() for keyword in bench_keywords)


class RoboflowRawResponse(BaseModel):
    """Raw response from Roboflow API."""

    predictions: list[dict[str, Any]] = Field(
        default_factory=list, description="Raw predictions"
    )
    image: Optional[dict[str, Any]] = Field(None, description="Image metadata")
    time: Optional[float] = Field(None, description="Inference time")

    def get_predictions(self) -> list[RoboflowPrediction]:
        """Convert raw predictions to structured format."""
        return [RoboflowPrediction.from_dict(pred) for pred in self.predictions]


class RoboflowDetectionResult(BaseModel):
    """Standardized detection result from Roboflow."""

    image_path: str = Field(..., description="Path to the analyzed image")
    success: bool = Field(..., description="Whether the detection was successful")
    has_bench: bool = Field(..., description="Whether any benches were detected")
    bench_count: int = Field(..., description="Number of bench detections")
    max_confidence: float = Field(
        ..., description="Highest confidence score among detections"
    )
    predictions: list[RoboflowPrediction] = Field(
        default_factory=list, description="All predictions"
    )
    bench_predictions: list[RoboflowPrediction] = Field(
        default_factory=list, description="Only bench-like predictions"
    )
    raw_predictions_count: int = Field(
        ..., description="Total number of raw predictions"
    )
    model_id: str = Field(..., description="Model ID used for inference")
    confidence_threshold: float = Field(..., description="Confidence threshold applied")
    inference_type: str = Field(..., description="Type of inference (local/cloud)")
    inference_time: Optional[float] = Field(
        None, description="Inference time in seconds"
    )
    error: Optional[str] = Field(None, description="Error message if detection failed")

    @classmethod
    def from_raw_response(
        cls,
        image_path: str,
        raw_response: Union[RoboflowRawResponse, dict[str, Any]],
        model_id: str,
        confidence_threshold: float,
        inference_type: str = "cloud",
    ) -> "RoboflowDetectionResult":
        """Create detection result from raw API response."""
        try:
            if isinstance(raw_response, dict):
                raw_response = RoboflowRawResponse(**raw_response)

            # Get all predictions
            all_predictions = raw_response.get_predictions()

            # Filter bench-like predictions above threshold
            bench_predictions = [
                pred
                for pred in all_predictions
                if pred.is_bench_like and pred.confidence >= confidence_threshold
            ]

            # Calculate metrics
            has_bench = len(bench_predictions) > 0
            max_confidence = max(
                (pred.confidence for pred in bench_predictions), default=0.0
            )

            return cls(
                image_path=image_path,
                success=True,
                has_bench=has_bench,
                bench_count=len(bench_predictions),
                max_confidence=max_confidence,
                predictions=all_predictions,
                bench_predictions=bench_predictions,
                raw_predictions_count=len(raw_response.predictions),
                model_id=model_id,
                confidence_threshold=confidence_threshold,
                inference_type=inference_type,
                inference_time=raw_response.time,
            )

        except Exception as e:
            return cls.create_error_result(
                image_path=image_path,
                error=f"Failed to process response: {e!s}",
                model_id=model_id,
                confidence_threshold=confidence_threshold,
                inference_type=inference_type,
            )

    @classmethod
    def create_error_result(
        cls,
        image_path: str,
        error: str,
        model_id: str,
        confidence_threshold: float,
        inference_type: str = "cloud",
    ) -> "RoboflowDetectionResult":
        """Create an error result."""
        return cls(
            image_path=image_path,
            success=False,
            has_bench=False,
            bench_count=0,
            max_confidence=0.0,
            predictions=[],
            bench_predictions=[],
            raw_predictions_count=0,
            model_id=model_id,
            confidence_threshold=confidence_threshold,
            inference_type=inference_type,
            error=error,
        )


class RoboflowBatchResult(BaseModel):
    """Result of batch detection across multiple images."""

    results: list[RoboflowDetectionResult] = Field(
        default_factory=list, description="Individual detection results"
    )
    total_images: int = Field(..., description="Total number of images processed")
    successful_detections: int = Field(
        ..., description="Number of successful detections"
    )
    images_with_benches: int = Field(
        ..., description="Number of images containing benches"
    )
    total_bench_detections: int = Field(
        ..., description="Total number of bench detections across all images"
    )
    avg_confidence: float = Field(
        ..., description="Average confidence across all bench detections"
    )

    @classmethod
    def from_results(
        cls, results: list[RoboflowDetectionResult]
    ) -> "RoboflowBatchResult":
        """Create batch result from individual detection results."""
        successful_detections = sum(1 for r in results if r.success)
        images_with_benches = sum(1 for r in results if r.has_bench)
        total_bench_detections = sum(r.bench_count for r in results)

        # Calculate average confidence
        all_confidences = [
            pred.confidence for result in results for pred in result.bench_predictions
        ]
        avg_confidence = (
            sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        )

        return cls(
            results=results,
            total_images=len(results),
            successful_detections=successful_detections,
            images_with_benches=images_with_benches,
            total_bench_detections=total_bench_detections,
            avg_confidence=avg_confidence,
        )

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of detections."""
        return self.successful_detections / max(self.total_images, 1)

    @property
    def bench_detection_rate(self) -> float:
        """Calculate the rate of images with bench detections."""
        return self.images_with_benches / max(self.total_images, 1)


class RoboflowModelInfo(BaseModel):
    """Information about a Roboflow model."""

    model_id: str = Field(..., description="Model identifier")
    confidence_threshold: float = Field(..., description="Confidence threshold")
    classes: list[str] = Field(
        default_factory=list, description="Supported object classes"
    )
    version: Optional[str] = Field(None, description="Model version")
    description: Optional[str] = Field(None, description="Model description")


class ModelCacheInfo(BaseModel):
    """Information about the model cache."""

    cached_models: list[str] = Field(
        default_factory=list, description="List of cached model keys"
    )
    cache_size: int = Field(..., description="Number of models in cache")


class CacheStatus(BaseModel):
    """Status information about model caching."""

    use_local_inference: bool = Field(
        ..., description="Whether local inference is being used"
    )
    model_id: str = Field(..., description="Current model ID")
    model_cached: bool = Field(..., description="Whether the current model is cached")
    cache_key: Optional[str] = Field(
        None, description="Cache key for the current model"
    )
    total_cached_models: int = Field(..., description="Total number of cached models")
    all_cached_models: list[str] = Field(
        default_factory=list, description="All cached model keys"
    )
