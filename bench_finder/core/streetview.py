"""
Google Street View Static API integration for capturing street view images.
"""

import logging
import os

import requests
from PIL import Image

from bench_finder.config import (
    GOOGLE_MAPS_API_KEY,
    IMAGES_DIR,
    STREETVIEW_FOV,
    STREETVIEW_HEADINGS,
    STREETVIEW_SIZE,
)
from bench_finder.models.streetview_models import (
    StreetViewBatchCaptureResult,
    StreetViewCleanupResult,
    StreetViewImageCapture,
    StreetViewLocation,
    StreetViewMetadata,
    StreetViewMetadataResponse,
)


logger = logging.getLogger(__name__)


class StreetViewClient:
    """Client for Google Street View Static API."""

    def __init__(self):
        """Initialize the Street View client."""
        if not GOOGLE_MAPS_API_KEY:
            raise ValueError("GOOGLE_MAPS_API_KEY is required")

        self.api_key = GOOGLE_MAPS_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api/streetview"

        # Ensure images directory exists
        os.makedirs(IMAGES_DIR, exist_ok=True)

    def capture_bench_images(
        self, lat: float, lng: float, bench_id: str
    ) -> StreetViewBatchCaptureResult:
        """
        Capture street view images from multiple headings for a bench location.

        Args:
            lat: Latitude of the bench
            lng: Longitude of the bench
            bench_id: Unique identifier for the bench

        Returns:
            StreetViewBatchCaptureResult with capture information
        """
        logger.debug(
            f"Capturing street view images for bench {bench_id} at {lat}, {lng}"
        )

        capture_results = []

        for heading in STREETVIEW_HEADINGS:
            try:
                result = self.capture_image(lat, lng, bench_id, heading)
                capture_results.append(result)

                if result and result.success:
                    if result.cached:
                        logger.debug(f"Using cached image at heading {heading}°")
                    else:
                        logger.debug(
                            f"Successfully downloaded image at heading {heading}°"
                        )
                else:
                    logger.warning(f"Failed to capture image at heading {heading}°")

            except Exception:
                logger.exception(f"Error capturing image at heading {heading}°")

        # Create batch result from individual capture results
        batch_result = StreetViewBatchCaptureResult.from_capture_results(
            bench_id, lat, lng, capture_results
        )

        logger.debug(
            f"Bench {bench_id}: {batch_result.successful_images}/{batch_result.total_images} images total "
            f"({batch_result.downloaded_images} downloaded, {batch_result.cached_images} cached, {batch_result.failed_images} failed)"
        )

        return batch_result

    def capture_image(
        self, lat: float, lng: float, bench_id: str, heading: int
    ) -> StreetViewImageCapture | None:
        """
        Capture a single street view image at specified heading.

        Args:
            lat: Latitude
            lng: Longitude
            bench_id: Unique identifier for the bench
            heading: Compass heading (0-360 degrees)

        Returns:
            StreetViewImageCapture with capture results
        """
        try:
            # Generate filename first to check if image already exists
            filename = f"bench_{bench_id}_heading_{heading}.jpg"
            filepath = os.path.join(IMAGES_DIR, filename)

            # Check if image already exists
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                logger.debug(f"Image already exists: {filename}, skipping download")
                return StreetViewImageCapture(
                    bench_id=bench_id,
                    lat=lat,
                    lng=lng,
                    heading=heading,
                    filepath=filepath,
                    filename=filename,
                    success=True,
                    file_size=os.path.getsize(filepath),
                    cached=True,
                    error=None,
                    width=int(STREETVIEW_SIZE.split("x")[0]),
                    height=int(STREETVIEW_SIZE.split("x")[1]),
                )

            # Build the Street View Static API URL
            params = {
                "location": f"{lat},{lng}",
                "size": STREETVIEW_SIZE,
                "heading": heading,
                "fov": STREETVIEW_FOV,
                "key": self.api_key,
            }

            logger.debug(
                f"Requesting street view image: lat={lat}, lng={lng}, heading={heading}"
            )

            # Make the API request
            response = requests.get(self.base_url, params=params, timeout=30)

            # Check if we got a valid response
            if response.status_code != 200:
                logger.error(f"Street View API returned status {response.status_code}")
                return None

            # Check content type to ensure we got an image
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                logger.error(f"Expected image, got content-type: {content_type}")
                return None

            # Save the image
            with open(filepath, "wb") as f:
                f.write(response.content)

            # Verify the image was saved correctly
            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                logger.error(f"Failed to save image to {filepath}")
                return None

            # Optionally verify it's a valid image
            try:
                with Image.open(filepath) as img:
                    width, height = img.size
                    logger.debug(f"Saved image {filename}: {width}x{height}")
            except Exception as e:
                logger.warning(f"Could not verify image {filename}: {e}")

            return StreetViewImageCapture(
                width=width,
                height=height,
                filename=filename,
                bench_id=bench_id,
                lat=lat,
                lng=lng,
                heading=heading,
                filepath=filepath,
                success=True,
                file_size=os.path.getsize(filepath),
                cached=False,
                error=None,
            )

        except requests.exceptions.RequestException:
            logger.exception("Network error capturing street view image")
            return None
        except Exception:
            logger.exception("Unexpected error capturing street view image")
            return None

    def get_street_view_metadata(
        self, lat: float, lng: float
    ) -> StreetViewMetadataResponse:
        """
        Get metadata about street view availability at a location.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            StreetViewMetadataResponse with metadata information
        """
        requested_location = StreetViewLocation(lat=lat, lng=lng)

        try:
            metadata_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
            params = {"location": f"{lat},{lng}", "key": self.api_key}

            response = requests.get(metadata_url, params=params, timeout=10)
            response.raise_for_status()

            metadata_raw = response.json()
            status = metadata_raw.get("status")

            if status == "OK":
                logger.debug(f"Street view available at {lat}, {lng}")

                # Parse location information
                location_info = metadata_raw.get("location", {})
                location = None
                if location_info:
                    location = StreetViewLocation(
                        lat=location_info.get("lat"), lng=location_info.get("lng")
                    )

                metadata = StreetViewMetadata(
                    status=status,
                    location=location,
                    pano_id=metadata_raw.get("pano_id"),
                    date=metadata_raw.get("date"),
                    copyright=metadata_raw.get("copyright"),
                )

                return StreetViewMetadataResponse(
                    requested_location=requested_location, metadata=metadata
                )
            else:
                logger.debug(f"Street view not available at {lat}, {lng}: {status}")

                # Create metadata with error status
                metadata = StreetViewMetadata(
                    status=status,
                    location=None,
                    pano_id=None,
                    date=None,
                    copyright=None,
                )

                return StreetViewMetadataResponse(
                    requested_location=requested_location, metadata=metadata
                )

        except Exception:
            logger.exception("Error getting street view metadata")

            # Return error response
            error_metadata = StreetViewMetadata(
                status="ERROR", location=None, pano_id=None, date=None, copyright=None
            )

            return StreetViewMetadataResponse(
                requested_location=requested_location, metadata=error_metadata
            )

    def cleanup_images(self, filepaths: list[str]) -> StreetViewCleanupResult:
        """
        Clean up image files.

        Args:
            filepaths: List of file paths to delete

        Returns:
            StreetViewCleanupResult with cleanup statistics
        """
        removed_count = 0
        failed_count = 0
        errors = []

        for filepath in filepaths:
            try:
                if filepath and os.path.exists(filepath):
                    os.remove(filepath)
                    removed_count += 1
                    logger.debug(f"Removed image file: {filepath}")
                elif filepath:
                    # File doesn't exist, but this isn't really an error
                    logger.debug(f"File already removed or doesn't exist: {filepath}")
            except Exception as e:
                failed_count += 1
                error_msg = f"Could not remove image file {filepath}: {e}"
                errors.append(error_msg)
                logger.warning(error_msg)

        return StreetViewCleanupResult(
            filepaths=filepaths,
            removed_count=removed_count,
            failed_count=failed_count,
            errors=errors,
        )
