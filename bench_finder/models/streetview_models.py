"""
Pydantic models for Google Street View Static API responses.
"""

from typing import Any

from pydantic import BaseModel, Field


class StreetViewLocation(BaseModel):
    """Street View location information."""

    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")


class StreetViewImageCapture(BaseModel):
    """Result of a single Street View image capture."""

    bench_id: str = Field(..., description="Unique identifier for the bench")
    lat: float = Field(..., description="Latitude of the capture location")
    lng: float = Field(..., description="Longitude of the capture location")
    heading: int = Field(..., description="Compass heading (0-360 degrees)")
    filepath: str = Field(..., description="Local file path to the image")
    filename: str = Field(..., description="Image filename")
    success: bool = Field(..., description="Whether the capture was successful")
    file_size: int | None = Field(None, description="File size in bytes")
    cached: bool = Field(False, description="Whether the image was already cached")
    error: str | None = Field(None, description="Error message if capture failed")
    width: int = Field(..., description="Width of the image")
    height: int = Field(..., description="Height of the image")
    # Image provenance tracking
    image_source: str | None = Field(
        None,
        description="Source: streetview_api, streetview_streetlevel, or apple_streetlevel",
    )
    panorama_lat: float | None = Field(
        None,
        description="Latitude of the actual panorama location (may differ from bench location)",
    )
    panorama_lng: float | None = Field(
        None,
        description="Longitude of the actual panorama location (may differ from bench location)",
    )
    panorama_metadata: dict[str, Any] | None = Field(
        None, description="Additional panorama metadata (pano_id, date, etc.)"
    )

    @property
    def is_valid(self) -> bool:
        """Check if this is a valid image capture."""
        return self.success and self.filepath is not None and self.filename is not None

    @property
    def area(self) -> float:
        """Calculate the area of the image."""
        return self.width * self.height


class StreetViewBatchCaptureResult(BaseModel):
    """Result of capturing multiple Street View images for a bench."""

    bench_id: str = Field(..., description="Unique identifier for the bench")
    location: StreetViewLocation = Field(..., description="Bench location")
    captures: list[StreetViewImageCapture] = Field(
        default_factory=list, description="Individual image captures"
    )
    total_images: int = Field(..., description="Total number of images attempted")
    successful_images: int = Field(..., description="Number of successful captures")
    failed_images: int = Field(..., description="Number of failed captures")
    cached_images: int = Field(
        ..., description="Number of images that were already cached"
    )
    downloaded_images: int = Field(
        ..., description="Number of images actually downloaded"
    )

    @property
    def success_rate(self) -> float:
        """Calculate the success rate of captures."""
        return self.successful_images / max(self.total_images, 1)

    @property
    def has_successful_captures(self) -> bool:
        """Check if any captures were successful."""
        return self.successful_images > 0

    @property
    def valid_captures(self) -> list[StreetViewImageCapture]:
        """Get only the valid/successful captures."""
        return [capture for capture in self.captures if capture.is_valid]

    @classmethod
    def from_capture_results(
        cls,
        bench_id: str,
        lat: float,
        lng: float,
        capture_results: list[StreetViewImageCapture | None],
    ) -> "StreetViewBatchCaptureResult":
        """Create batch result from raw capture results."""
        captures = []
        successful_count = 0
        cached_count = 0
        downloaded_count = 0

        for capture in capture_results:
            captures.append(capture)

            if capture is not None and capture.success:
                successful_count += 1
                if capture.cached:
                    cached_count += 1
                else:
                    downloaded_count += 1

        return cls(
            bench_id=bench_id,
            location=StreetViewLocation(lat=lat, lng=lng),
            captures=[capture for capture in capture_results if capture is not None],
            total_images=len(capture_results),
            successful_images=successful_count,
            failed_images=len(capture_results) - successful_count,
            cached_images=cached_count,
            downloaded_images=downloaded_count,
        )


class StreetViewMetadata(BaseModel):
    """Street View metadata from the Google API."""

    status: str = Field(..., description="API response status")
    location: StreetViewLocation | None = Field(
        None, description="Actual image location"
    )
    pano_id: str | None = Field(None, description="Panorama ID")
    date: str | None = Field(None, description="Image capture date")
    copyright: str | None = Field(None, description="Copyright information")

    @property
    def is_available(self) -> bool:
        """Check if Street View imagery is available at this location."""
        return self.status == "OK"


class StreetViewMetadataResponse(BaseModel):
    """Response from Street View metadata API."""

    requested_location: StreetViewLocation = Field(
        ..., description="Originally requested location"
    )
    metadata: StreetViewMetadata | None = Field(
        None, description="Metadata if available"
    )

    @property
    def has_street_view(self) -> bool:
        """Check if Street View is available at the requested location."""
        return self.metadata is not None and self.metadata.is_available


class StreetViewCleanupResult(BaseModel):
    """Result of cleaning up Street View image files."""

    filepaths: list[str] = Field(
        ..., description="File paths that were attempted to be cleaned"
    )
    removed_count: int = Field(..., description="Number of files successfully removed")
    failed_count: int = Field(
        ..., description="Number of files that failed to be removed"
    )
    errors: list[str] = Field(
        default_factory=list, description="Any errors encountered during cleanup"
    )
