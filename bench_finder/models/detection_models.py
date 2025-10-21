"""
Unified detection models for bench finder application.
These models are used across the entire codebase for consistent type handling.
"""

from typing import Optional

from pydantic import BaseModel, Field


class Polygon(BaseModel):
    """Represents a polygon as a list of coordinate pairs."""

    coordinates: list[list[float]] = Field(
        description="List of [x, y] coordinate pairs forming the polygon"
    )


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

    def __init__(self, **data):
        """Auto-calculate width and height if not provided."""
        # Auto-calculate width and height if not provided
        if "width" not in data and "x1" in data and "x2" in data:
            data["width"] = abs(data["x2"] - data["x1"])
        if "height" not in data and "y1" in data and "y2" in data:
            data["height"] = abs(data["y2"] - data["y1"])
        super().__init__(**data)


class DetectionItem(BaseModel):
    """Single detection item with mandatory bbox and optional polygon/segmentation."""

    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score between 0 and 1"
    )
    bbox: BoundingBox = Field(description="Mandatory bounding box")
    class_name: str = Field(
        default="bench", description="Class name of the detected object"
    )
    # Support both polygon and segmentation for backward compatibility
    polygon: Optional[Polygon] = Field(
        default=None, description="Optional polygon for segmentation"
    )
    segmentation: Optional[list[list[float]]] = Field(
        default=None, description="Polygon coordinates if available (legacy format)"
    )

    class Config:
        """Pydantic configuration."""

        json_encoders = {  # noqa: RUF012
            BoundingBox: lambda v: {
                "x1": v.x1,
                "y1": v.y1,
                "x2": v.x2,
                "y2": v.y2,
                "width": v.width,
                "height": v.height,
                "center_x": v.center_x,
                "center_y": v.center_y,
                "area": v.area,
            }
        }

    def model_post_init(self, __context) -> None:
        """Convert segmentation to polygon if needed for backward compatibility."""
        if self.segmentation and not self.polygon:
            self.polygon = Polygon(coordinates=self.segmentation)
