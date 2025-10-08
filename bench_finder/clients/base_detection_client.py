"""
Base detection client with unified interface and common detection result classes.
All detection clients should inherit from this base class.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Protocol
from pathlib import Path
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Polygon(BaseModel):
    """Represents a polygon as a list of coordinate pairs."""
    coordinates: List[List[float]] = Field(description="List of [x, y] coordinate pairs forming the polygon")


class BoundingBox(BaseModel):
    """Standardized bounding box format with computed properties."""
    x1: float = Field(description="Left coordinate")
    y1: float = Field(description="Top coordinate") 
    x2: float = Field(description="Right coordinate")
    y2: float = Field(description="Bottom coordinate")
    
    @property
    def width(self) -> float:
        """Computed width of the bounding box."""
        return abs(self.x2 - self.x1)
    
    @property
    def height(self) -> float:
        """Computed height of the bounding box."""
        return abs(self.y2 - self.y1)
    
    @property
    def center_x(self) -> float:
        """Center X coordinate."""
        return (self.x1 + self.x2) / 2
    
    @property
    def center_y(self) -> float:
        """Center Y coordinate."""
        return (self.y1 + self.y2) / 2
    
    @property
    def area(self) -> float:
        """Area of the bounding box."""
        return self.width * self.height


class DetectionItem(BaseModel):
    """Single detection item with mandatory bbox and optional polygon."""
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score between 0 and 1")
    bbox: BoundingBox = Field(description="Mandatory bounding box")
    class_name: str = Field(default="bench", description="Class name of the detected object")
    polygon: Optional[Polygon] = Field(default=None, description="Optional polygon for segmentation")
    
    class Config:
        """Pydantic configuration."""
        json_encoders = {
            BoundingBox: lambda v: {
                "x1": v.x1, "y1": v.y1, "x2": v.x2, "y2": v.y2,
                "width": v.width, "height": v.height,
                "center_x": v.center_x, "center_y": v.center_y, "area": v.area
            }
        }


class DetectionResult(BaseModel):
    """Unified detection result from any backend."""
    image_path: str = Field(description="Path to the analyzed image")
    success: bool = Field(description="Whether the detection was successful")
    has_bench: bool = Field(description="Whether any benches were detected")
    bench_count: int = Field(ge=0, description="Number of benches detected")
    max_confidence: float = Field(ge=0.0, le=1.0, description="Highest confidence score among all detections")
    detections: List[DetectionItem] = Field(default_factory=list, description="List of all detections")
    
    # Backend information
    backend_name: str = Field(description="Name of the detection backend used")
    model_id: str = Field(description="ID of the model used")
    confidence_threshold: float = Field(ge=0.0, le=1.0, description="Confidence threshold used")
    
    # Error information
    error: Optional[str] = Field(default=None, description="Error message if detection failed")
    
    # Additional metadata
    inference_time: Optional[float] = Field(default=None, description="Time taken for inference in seconds")
    preprocess_time: Optional[float] = Field(default=None, description="Time taken for preprocessing in seconds")
    postprocess_time: Optional[float] = Field(default=None, description="Time taken for postprocessing in seconds")


class DetectionAttempt(BaseModel):
    """Represents a single model detection attempt."""
    model_type: str = Field(description="Type of model (e.g., 'ultralytics', 'roboflow')")
    model_id: str = Field(description="ID of the specific model")
    success: bool = Field(description="Whether the attempt was successful")
    has_bench: bool = Field(description="Whether a bench was detected")
    confidence: float = Field(ge=0.0, le=1.0, description="Maximum confidence score")
    error: Optional[str] = Field(default=None, description="Error message if attempt failed")


class MultiModelDetectionResult(DetectionResult):
    """Detection result from multi-model client with fallback information."""
    fallback_used: bool = Field(default=False, description="Whether fallback models were used")
    total_attempts: int = Field(ge=1, description="Total number of detection attempts")
    detection_attempts: List[DetectionAttempt] = Field(default_factory=list, description="All detection attempts made")


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
        pass
    
    @abstractmethod
    def batch_detect_benches(self, image_paths: List[str]) -> List[DetectionResult]:
        """Detect benches in multiple images.
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            List of DetectionResult objects
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> dict:
        """Get information about the model being used.
        
        Returns:
            Dictionary with model information
        """
        pass
    
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
            error=error
        )


class MultiModelDetectionClient(DetectionClient):
    """Base class for multi-model detection clients."""
    
    def __init__(self, confidence_threshold: float = 0.5):
        """Initialize the multi-model detection client.
        
        Args:
            confidence_threshold: Minimum confidence threshold for detections
        """
        super().__init__(confidence_threshold)
        self.all_attempts: List[DetectionAttempt] = []
    
    def get_detection_stats(self) -> dict:
        """Get statistics about detection attempts across all processed images.
        
        Returns:
            Dictionary with detection statistics
        """
        if not self.all_attempts:
            return {'total_attempts': 0, 'no_data': True}
        
        stats: Dict[str, float | int] = {
            'total_attempts': len(self.all_attempts),
            'successful_attempts': len([a for a in self.all_attempts if a.success and a.has_bench]),
            'failed_attempts': len([a for a in self.all_attempts if not a.success]),
            'no_bench_detected': len([a for a in self.all_attempts if a.success and not a.has_bench])
        }
        
        # Calculate success rate
        if stats['total_attempts'] > 0:
            stats['success_rate'] = float(stats['successful_attempts']) / float(stats['total_attempts'])
        
        return stats
    
    def reset_stats(self) -> None:
        """Reset detection attempt statistics."""
        self.all_attempts = []
