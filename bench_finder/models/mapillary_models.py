"""
Pydantic models for Mapillary API responses.
"""

import base64
import logging
from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, Field


logger = logging.getLogger(__name__)


class MapillaryGeometry(BaseModel):
    """Mapillary geometry coordinates."""

    coordinates: Union[list[float], str] = Field(
        ..., description="Coordinates as [lng, lat] or encoded string"
    )


class MapillaryImageInfo(BaseModel):
    """Basic Mapillary image information."""

    id: str = Field(..., description="Mapillary image ID")
    geometry: Optional[MapillaryGeometry] = None

    @property
    def coordinates(self) -> tuple[float, float]:
        """Get coordinates as (lng, lat) tuple."""
        if (
            self.geometry
            and isinstance(self.geometry.coordinates, list)
            and len(self.geometry.coordinates) >= 2
        ):
            return (self.geometry.coordinates[0], self.geometry.coordinates[1])
        return (0.0, 0.0)


class MapillaryImagesData(BaseModel):
    """Container for Mapillary images data."""

    data: list[MapillaryImageInfo] = Field(default_factory=list)


class MapillaryDetection(BaseModel):
    """Represents a bench detection from Mapillary."""

    detection_id: str = Field(..., description="Unique detection ID")
    image_id: str = Field(..., description="Associated image ID")
    image_coordinates: tuple[float, float] = Field(
        ..., description="Image coordinates as (lng, lat)"
    )
    value: str = Field(default="object--bench", description="Detection object value")
    geometry_encoded: str = Field(default="", description="Base64 encoded geometry")
    geometry_decoded: Optional[list[list[float]]] = Field(
        None, description="Decoded geometry coordinates"
    )
    confidence: float = Field(
        default=1.0, description="Detection confidence (Mapillary assumes high)"
    )
    created_at: Optional[datetime] = None

    def decode_geometry(self) -> Optional[list[list[float]]]:
        """Decode base64 encoded geometry."""
        if not self.geometry_encoded:
            return None

        try:
            base64.b64decode(self.geometry_encoded)
            # Note: This is a simplified implementation
            # The actual Mapillary geometry format may require protobuf decoding
            logger.debug(
                f"Geometry decoding not fully implemented for: {self.geometry_encoded[:50]}..."
            )
            return None
        except Exception:
            logger.warning(f"Failed to decode geometry: {e}")
            return None


class MapillaryMapFeature(BaseModel):
    """Mapillary map feature with bench detection."""

    id: str = Field(..., description="Feature ID")
    object_value: str = Field(..., description="Object type (e.g., 'object--bench')")
    geometry: Optional[MapillaryGeometry] = None
    images: Optional[MapillaryImagesData] = None

    def to_detections(self) -> list[MapillaryDetection]:
        """Convert this feature to MapillaryDetection objects."""
        detections: list[MapillaryDetection] = []

        if not self.images or not self.images.data:
            return detections

        for image_info in self.images.data:
            # Convert geometry coordinates to the expected format
            geometry_decoded = None
            if (
                self.geometry
                and isinstance(self.geometry.coordinates, list)
                and len(self.geometry.coordinates) >= 2
            ):
                # Wrap the coordinates in a list to match List[List[float]] format
                geometry_decoded = [self.geometry.coordinates]

            detection = MapillaryDetection(
                detection_id=self.id,
                image_id=image_info.id,
                image_coordinates=image_info.coordinates,
                value=self.object_value,
                geometry_encoded=str(self.geometry.coordinates)
                if self.geometry
                else "",
                geometry_decoded=geometry_decoded,
                confidence=1.0,  # Mapillary doesn't provide confidence scores
            )
            detections.append(detection)

        return detections


class MapillaryMapFeaturesResponse(BaseModel):
    """Response from Mapillary map_features endpoint."""

    data: list[MapillaryMapFeature] = Field(default_factory=list)

    def get_all_detections(self) -> list[MapillaryDetection]:
        """Get all bench detections from all features."""
        all_detections = []
        for feature in self.data:
            if feature.object_value == "object--bench":
                all_detections.extend(feature.to_detections())
        return all_detections


class MapillaryImage(BaseModel):
    """Represents a Mapillary image with detections."""

    image_id: str = Field(..., description="Mapillary image ID")
    coordinates: tuple[float, float] = Field(
        ..., description="Image coordinates as (lng, lat)"
    )
    detections: list[MapillaryDetection] = Field(
        default_factory=list, description="Bench detections in this image"
    )

    @property
    def has_bench_detections(self) -> bool:
        """Check if this image has any bench detections."""
        return len(self.detections) > 0

    @property
    def detection_count(self) -> int:
        """Get the number of bench detections."""
        return len(self.detections)


class MapillaryImageMetadata(BaseModel):
    """Mapillary image metadata from API."""

    id: str = Field(..., description="Image ID")
    geometry: Optional[MapillaryGeometry] = None
    thumb_256_url: Optional[str] = None
    thumb_1024_url: Optional[str] = None
    thumb_2048_url: Optional[str] = None

    def get_thumb_url(self, preferred_size: int = 2048) -> Optional[str]:
        """Get the best available thumbnail URL for the requested size."""
        if preferred_size >= 2048 and self.thumb_2048_url:
            return self.thumb_2048_url
        elif preferred_size >= 1024 and self.thumb_1024_url:
            return self.thumb_1024_url
        elif self.thumb_256_url:
            return self.thumb_256_url
        return None


class MapillaryImageDownloadResult(BaseModel):
    """Result of a Mapillary image download operation."""

    success: bool = Field(..., description="Whether the download was successful")
    image_id: str = Field(..., description="Mapillary image ID")
    filepath: Optional[str] = Field(None, description="Local file path")
    filename: Optional[str] = Field(None, description="Local filename")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    downloaded: bool = Field(
        False,
        description="Whether file was actually downloaded (False if already existed)",
    )
    thumb_url: Optional[str] = Field(None, description="Source thumbnail URL")
    error: Optional[str] = Field(None, description="Error message if failed")


class MapillarySearchResult(BaseModel):
    """Result of a Mapillary search operation."""

    images: list[MapillaryImage] = Field(
        default_factory=list, description="Images with bench detections"
    )
    search_center_lat: float = Field(..., description="Search center latitude")
    search_center_lng: float = Field(..., description="Search center longitude")
    search_radius_meters: int = Field(..., description="Search radius in meters")
    total_images: int = Field(..., description="Total number of images found")
    total_detections: int = Field(..., description="Total number of detections found")

    @property
    def has_detections(self) -> bool:
        """Check if any detections were found."""
        return self.total_detections > 0

    @classmethod
    def from_api_response(
        cls,
        api_response: MapillaryMapFeaturesResponse,
        center_lat: float,
        center_lng: float,
        radius_meters: int,
    ) -> "MapillarySearchResult":
        """Create search result from API response."""
        # Group detections by image ID
        images_dict: dict[str, MapillaryImage] = {}

        for detection in api_response.get_all_detections():
            image_id = detection.image_id

            if image_id not in images_dict:
                images_dict[image_id] = MapillaryImage(
                    image_id=image_id,
                    coordinates=detection.image_coordinates,
                    detections=[],
                )

            images_dict[image_id].detections.append(detection)

        images = list(images_dict.values())
        total_detections = sum(len(img.detections) for img in images)

        return cls(
            images=images,
            search_center_lat=center_lat,
            search_center_lng=center_lng,
            search_radius_meters=radius_meters,
            total_images=len(images),
            total_detections=total_detections,
        )


class MapillaryDetectionStatistics(BaseModel):
    """Statistics about Mapillary bench detections."""

    total_images: int = Field(..., description="Total number of images")
    total_detections: int = Field(..., description="Total number of detections")
    avg_detections_per_image: float = Field(
        ..., description="Average detections per image"
    )
    unique_locations: int = Field(..., description="Number of unique location buckets")
    max_detections_at_location: int = Field(
        ..., description="Maximum detections at a single location"
    )

    @classmethod
    def from_images(
        cls, images: list[MapillaryImage]
    ) -> "MapillaryDetectionStatistics":
        """Calculate statistics from a list of images."""
        total_images = len(images)
        total_detections = sum(len(img.detections) for img in images)

        # Group by location for density analysis
        location_counts: dict[tuple[float, float], int] = {}
        for image in images:
            # Round coordinates to create location buckets (~100m precision)
            lat_bucket = round(image.coordinates[1], 3)
            lng_bucket = round(image.coordinates[0], 3)
            key = (lat_bucket, lng_bucket)
            location_counts[key] = location_counts.get(key, 0) + len(image.detections)

        return cls(
            total_images=total_images,
            total_detections=total_detections,
            avg_detections_per_image=total_detections / max(total_images, 1),
            unique_locations=len(location_counts),
            max_detections_at_location=max(location_counts.values())
            if location_counts
            else 0,
        )
