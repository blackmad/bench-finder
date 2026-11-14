"""
Pydantic models for Google Street View Static API responses.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class PanoramaMetadata(BaseModel):
    """
    Cached panorama metadata from streetlevel/lookaround APIs.
    This is a lightweight model that captures essential fields from
    StreetViewPanorama or LookaroundPanorama objects for caching.
    """

    pano_id: str | int | None = Field(None, description="Panorama ID")
    panorama_lat: float = Field(..., description="Latitude of the panorama")
    panorama_lng: float = Field(..., description="Longitude of the panorama")
    panorama_heading: float | None = Field(
        None,
        description="Heading/orientation of the panorama in radians (from API)",
    )
    date: str | None = Field(None, description="Capture date as string")
    source: str | None = Field(
        None, description="Source: streetview_streetlevel or apple_streetlevel"
    )

    # Additional optional fields that may be present
    pitch: float | None = Field(None, description="Pitch offset in radians")
    roll: float | None = Field(None, description="Roll offset in radians")
    elevation: float | None = Field(None, description="Elevation in meters")

    # For Apple Look Around
    build_id: int | None = Field(None, description="Build ID for Apple Look Around")
    coverage_type: str | None = Field(
        None, description="Coverage type (e.g., 'CAR' or 'BACKPACK')"
    )
    face_filenames: list[str] | None = Field(
        None, description="Filenames of cached panorama faces for Apple Look Around"
    )

    @classmethod
    def from_streetview_pano(
        cls, pano: Any, source: str = "streetview_streetlevel"
    ) -> "PanoramaMetadata":
        """
        Create PanoramaMetadata from a StreetViewPanorama object.

        Args:
            pano: StreetViewPanorama object from streetlevel library
            source: Source identifier (default: "streetview_streetlevel")

        Returns:
            PanoramaMetadata instance
        """
        date_str = None
        if hasattr(pano, "date") and pano.date:
            date_str = str(pano.date)

        return cls(
            pano_id=pano.id if hasattr(pano, "id") else None,
            panorama_lat=pano.lat if hasattr(pano, "lat") else 0.0,
            panorama_lng=pano.lon if hasattr(pano, "lon") else 0.0,
            panorama_heading=pano.heading if hasattr(pano, "heading") else None,
            date=date_str,
            source=source,
            pitch=pano.pitch if hasattr(pano, "pitch") else None,
            roll=pano.roll if hasattr(pano, "roll") else None,
            elevation=pano.elevation if hasattr(pano, "elevation") else None,
            build_id=pano.build_id if hasattr(pano, "build_id") else None,
            coverage_type=pano.coverage_type
            if hasattr(pano, "coverage_type")
            else None,
            face_filenames=pano.face_filenames
            if hasattr(pano, "face_filenames")
            else None,
        )

    @classmethod
    def from_lookaround_pano(
        cls,
        pano: Any,
        source: str = "apple_streetlevel",
        face_filenames: list[str] | None = None,
    ) -> "PanoramaMetadata":
        """
        Create PanoramaMetadata from a LookaroundPanorama object.

        Args:
            pano: LookaroundPanorama object from streetlevel library
            source: Source identifier (default: "apple_streetlevel")
            face_filenames: Optional list of face filenames for cached faces

        Returns:
            PanoramaMetadata instance
        """
        date_str = None
        if hasattr(pano, "date") and pano.date:
            if isinstance(pano.date, datetime):
                date_str = pano.date.isoformat()
            else:
                date_str = str(pano.date)

        coverage_type_str = None
        if hasattr(pano, "coverage_type") and pano.coverage_type:
            coverage_type_str = str(pano.coverage_type.name)

        return cls(
            pano_id=pano.id if hasattr(pano, "id") else None,
            panorama_lat=pano.lat if hasattr(pano, "lat") else 0.0,
            panorama_lng=pano.lon if hasattr(pano, "lon") else 0.0,
            panorama_heading=pano.heading if hasattr(pano, "heading") else None,
            date=date_str,
            source=source,
            pitch=pano.pitch if hasattr(pano, "pitch") else None,
            roll=pano.roll if hasattr(pano, "roll") else None,
            elevation=pano.elevation if hasattr(pano, "elevation") else None,
            build_id=pano.build_id if hasattr(pano, "build_id") else None,
            coverage_type=coverage_type_str,
            face_filenames=face_filenames,
        )


class StreetViewLocation(BaseModel):
    """Street View location information."""

    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")


class StreetViewImageCaptureSuccess(BaseModel):
    """Successful Street View image capture."""

    status: Literal["success"] = Field(
        default="success", description="Discriminator field for successful capture"
    )
    bench_id: str = Field(..., description="Unique identifier for the bench")
    lat: float = Field(..., description="Latitude of the capture location")
    lng: float = Field(..., description="Longitude of the capture location")
    heading: int = Field(..., description="Compass heading (0-360 degrees)")
    filepath: str | None = Field(
        ...,
        description="Local file path to the image (None for Apple Look Around cached faces)",
    )
    filename: str = Field(..., description="Image filename")
    file_size: int = Field(..., description="File size in bytes")
    cached: bool = Field(
        default=False, description="Whether the image was already cached"
    )
    width: int = Field(..., description="Width of the image")
    height: int = Field(..., description="Height of the image")
    error: None = Field(default=None, description="Always None for successful captures")
    # Image provenance tracking
    image_source: str = Field(
        ...,
        description="Source: streetview_api, streetview_streetlevel, or apple_streetlevel",
    )
    panorama_lat: float = Field(
        ...,
        description="Latitude of the actual panorama location (may differ from bench location)",
    )
    panorama_lng: float = Field(
        ...,
        description="Longitude of the actual panorama location (may differ from bench location)",
    )
    panorama_metadata: "PanoramaMetadata | None" = Field(
        default=None, description="Additional panorama metadata (pano_id, date, etc.)"
    )
    panorama_heading: float | None = Field(
        default=None,
        description="Heading/orientation of the panorama itself (from streetlevel/lookaround API)",
    )
    # Aimed-view provenance (task 2.1/2.2)
    pano_id: str | None = Field(default=None, description="Source panorama id")
    pano_date: str | None = Field(default=None, description="Panorama capture date")
    camera_bearing_deg: float | None = Field(
        default=None, description="Compass bearing from the camera to the bench"
    )
    camera_distance_m: float | None = Field(
        default=None, description="Distance from the camera to the bench in metres"
    )
    fov_deg: float | None = Field(default=None, description="Horizontal field of view")
    pitch_deg: float | None = Field(default=None, description="View pitch in degrees")
    kind: str = Field(default="aimed", description="images.kind value")

    @property
    def success(self) -> bool:
        """Whether the capture was successful."""
        return True

    @property
    def is_valid(self) -> bool:
        """Check if this is a valid image capture."""
        # For Apple Look Around, filepath can be None if cached=True (faces are cached)
        if self.image_source == "apple_streetlevel" and self.cached:
            return self.filename is not None
        return self.filepath is not None and self.filename is not None

    @property
    def area(self) -> float:
        """Calculate the area of the image."""
        return self.width * self.height


class StreetViewImageCaptureError(BaseModel):
    """Failed Street View image capture with error information."""

    status: Literal["error"] = Field(
        default="error", description="Discriminator field for failed capture"
    )
    bench_id: str = Field(..., description="Unique identifier for the bench")
    lat: float = Field(..., description="Latitude of the capture location")
    lng: float = Field(..., description="Longitude of the capture location")
    heading: int = Field(..., description="Compass heading (0-360 degrees)")
    filename: str = Field(..., description="Image filename that would have been used")
    error: str = Field(..., description="Error message describing the failure")
    # Optional fields for partial data
    image_source: str | None = Field(
        default=None,
        description="Source: streetview_api, streetview_streetlevel, or apple_streetlevel",
    )
    panorama_lat: float | None = Field(
        default=None,
        description="Latitude of the actual panorama location if available before error",
    )
    panorama_lng: float | None = Field(
        default=None,
        description="Longitude of the actual panorama location if available before error",
    )
    panorama_metadata: "PanoramaMetadata | None" = Field(
        default=None,
        description="Additional panorama metadata if available before error",
    )
    panorama_heading: float | None = Field(
        default=None,
        description="Heading/orientation of the panorama if available before error",
    )
    cached: bool = Field(
        default=False, description="Whether this was a cached operation"
    )
    width: int = Field(default=0, description="Width placeholder (always 0 for errors)")
    height: int = Field(
        default=0, description="Height placeholder (always 0 for errors)"
    )
    file_size: int = Field(
        default=0, description="File size placeholder (always 0 for errors)"
    )
    filepath: str | None = Field(
        default=None, description="Filepath placeholder (always None for errors)"
    )
    # Aimed-view provenance (task 2.1/2.2)
    pano_id: str | None = Field(default=None, description="Source panorama id")
    pano_date: str | None = Field(default=None, description="Panorama capture date")
    camera_bearing_deg: float | None = Field(
        default=None, description="Compass bearing from the camera to the bench"
    )
    camera_distance_m: float | None = Field(
        default=None, description="Distance from the camera to the bench in metres"
    )
    fov_deg: float | None = Field(default=None, description="Horizontal field of view")
    pitch_deg: float | None = Field(default=None, description="View pitch in degrees")
    kind: str = Field(default="aimed", description="images.kind value")

    @property
    def success(self) -> bool:
        """Whether the capture was successful."""
        return False

    @property
    def is_valid(self) -> bool:
        """Check if this is a valid image capture."""
        return False  # Error captures are never valid

    @property
    def area(self) -> float:
        """Calculate the area of the image."""
        return 0  # Error captures have no area


# Union type for image capture results
StreetViewImageCapture = StreetViewImageCaptureSuccess | StreetViewImageCaptureError


class PanoramaCaptureResult(BaseModel):
    """Result of capturing a full panorama (not a specific heading view)."""

    bench_id: str = Field(..., description="Unique identifier for the bench")
    lat: float = Field(..., description="Latitude of the capture location")
    lng: float = Field(..., description="Longitude of the capture location")
    image_source: str = Field(
        ...,
        description="Source: streetview_api, streetview_streetlevel, or apple_streetlevel",
    )
    panorama_lat: float = Field(
        ...,
        description="Latitude of the actual panorama location (may differ from bench location)",
    )
    panorama_lng: float = Field(
        ...,
        description="Longitude of the actual panorama location (may differ from bench location)",
    )
    panorama_metadata: PanoramaMetadata | None = Field(
        default=None, description="Additional panorama metadata (pano_id, date, etc.)"
    )
    panorama_heading: float | None = Field(
        default=None,
        description="Heading/orientation of the panorama itself (from streetlevel/lookaround API)",
    )
    panorama_filepath: str | None = Field(
        default=None,
        description="File path to the full panorama image (None for Apple Look Around which uses faces)",
    )
    panorama_image: Any | None = Field(
        default=None,
        description="PIL Image of the panorama (for Google Street View) or None (for Apple Look Around which uses faces)",
    )
    face_filepaths: list[str] | None = Field(
        default=None,
        description="File paths to individual faces (for Apple Look Around) or None",
    )
    cached: bool = Field(
        default=False, description="Whether the panorama was already cached"
    )
    error: str | None = Field(
        default=None, description="Error message if capture failed"
    )

    @property
    def success(self) -> bool:
        """Whether the panorama capture was successful."""
        return self.error is None and (
            self.panorama_image is not None or self.face_filepaths is not None
        )


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
