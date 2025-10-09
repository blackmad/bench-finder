"""
Mapillary API client for fetching bench detections.
"""

import logging
import os
from typing import Optional

import requests

from bench_finder.clients.base_location_client import (
    BaseLocationClient,
    LocationSearchResult,
)
from bench_finder.models.mapillary_models import (
    MapillaryDetection,
    MapillaryDetectionStatistics,
    MapillaryImage,
    MapillaryImageDownloadResult,
    MapillaryImageMetadata,
    MapillaryMapFeaturesResponse,
    MapillarySearchResult,
)
from bench_finder.models.unified_models import UnifiedBench, UnifiedSearchResult


logger = logging.getLogger(__name__)


class MapillaryBenchDetector(BaseLocationClient):
    """Client for fetching bench detections from Mapillary API."""

    def __init__(self, access_token: str, images_dir: str = "images"):
        """
        Initialize Mapillary client.

        Args:
            access_token: Mapillary API access token
            images_dir: Directory to store downloaded images
        """
        super().__init__("MapillaryBenchDetector")
        self.access_token = access_token
        self.base_url = "https://graph.mapillary.com"
        self.images_dir = images_dir
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"OAuth {access_token}"})

        # Ensure images directory exists
        os.makedirs(self.images_dir, exist_ok=True)

    def search_near_point(
        self, lat: float, lng: float, radius: int = 1000
    ) -> LocationSearchResult:
        """
        Search for benches near a point (implements BaseLocationClient interface).

        Args:
            lat: Latitude of the center point
            lng: Longitude of the center point
            radius: Search radius in meters

        Returns:
            LocationSearchResult with found benches
        """
        result = self.search_benches_by_location(lat, lng, radius)
        return LocationSearchResult(
            search_center_lat=result.search_center_lat,
            search_center_lng=result.search_center_lng,
            search_radius_meters=result.search_radius_meters,
            total_count=result.total_detections,
        )

    def search_near_point_unified(
        self, lat: float, lng: float, radius: int = 1000
    ) -> UnifiedSearchResult:
        """
        Search for benches near a point and return unified results.

        Args:
            lat: Latitude of the center point
            lng: Longitude of the center point
            radius: Search radius in meters

        Returns:
            UnifiedSearchResult with found benches
        """
        result = self.search_benches_by_location(lat, lng, radius)

        # Convert MapillaryImage objects to UnifiedBench objects
        unified_benches = []
        for image in result.images:
            for detection in image.detections:
                unified_bench = UnifiedBench.from_mapillary_detection(
                    detection, image.coordinates
                )
                unified_benches.append(unified_bench)

        return UnifiedSearchResult(
            benches=unified_benches,
            search_center_lat=result.search_center_lat,
            search_center_lng=result.search_center_lng,
            search_radius_meters=result.search_radius_meters,
            total_count=len(unified_benches),
            source="mapillary",
        )

    def get_item_details(self, provider_id: str) -> Optional[dict]:
        """
        Get detailed information about a specific detection (implements BaseLocationClient interface).

        Args:
            provider_id: Provider ID in format "mapillary_detection_id"

        Returns:
            Dictionary with detection details or None if not found
        """
        # For Mapillary, we don't have a direct way to get details by detection ID
        # This would require searching in an area around the detection
        # For now, return None as this is not commonly used for Mapillary
        return None

    def search_images_with_detections(
        self,
        bbox: tuple[float, float, float, float],  # [min_lng, min_lat, max_lng, max_lat]
        limit: int = 1000,
    ) -> MapillarySearchResult:
        """
        Search for map features with bench detections in a bounding box.

        Args:
            bbox: Bounding box as [min_lng, min_lat, max_lng, max_lat]
            limit: Maximum number of images to return

        Returns:
            MapillarySearchResult with found detections
        """
        min_lng, min_lat, max_lng, max_lat = bbox

        # Use map_features endpoint to search for bench objects specifically
        url = f"{self.base_url}/map_features"
        params = {
            "access_token": self.access_token,
            "bbox": f"{min_lng},{min_lat},{max_lng},{max_lat}",
            "object_values": "object--bench",  # Filter for bench objects only
            "fields": "object_value,images,geometry",
            "limit": limit,
        }

        try:
            logger.info(f"Searching Mapillary map_features for benches in bbox: {bbox}")
            response = self.session.get(url, params=params)
            response.raise_for_status()

            # Parse response using Pydantic
            raw_data = response.json()
            api_response = MapillaryMapFeaturesResponse(**raw_data)

            # Calculate center point for result metadata
            center_lat = (bbox[1] + bbox[3]) / 2  # (min_lat + max_lat) / 2
            center_lng = (bbox[0] + bbox[2]) / 2  # (min_lng + max_lng) / 2

            # Approximate radius from bbox
            import math

            radius_meters = int(
                math.sqrt(
                    ((bbox[2] - bbox[0]) * 111000) ** 2
                    + ((bbox[3] - bbox[1]) * 111000) ** 2
                )
                / 2
            )

            # Create search result from API response
            result = MapillarySearchResult.from_api_response(
                api_response, center_lat, center_lng, radius_meters
            )

            logger.info(
                f"Found {result.total_images} images with {result.total_detections} bench detections from map_features"
            )
            return result

        except requests.RequestException:
            logger.exception("Error fetching Mapillary images")
            # Return empty search result
            center_lat = (bbox[1] + bbox[3]) / 2
            center_lng = (bbox[0] + bbox[2]) / 2
            return MapillarySearchResult(
                images=[],
                search_center_lat=center_lat,
                search_center_lng=center_lng,
                search_radius_meters=0,
                total_images=0,
                total_detections=0,
            )

    def get_image_detections(self, image_id: str) -> list[MapillaryDetection]:
        """
        Get bench detections for a specific image using map_features.

        Args:
            image_id: Mapillary image ID

        Returns:
            List of bench detections for the image
        """
        # Note: The map_features endpoint doesn't directly support filtering by image_id
        # This method is now less efficient as it needs to search in an area around the image
        # First, we need to get the image location
        image_url = f"{self.base_url}/{image_id}"
        image_params = {"fields": "geometry", "access_token": self.access_token}

        try:
            # Get image location
            image_response = self.session.get(image_url, params=image_params)
            image_response.raise_for_status()
            image_data = image_response.json()

            coords = image_data.get("geometry", {}).get("coordinates", [0, 0])
            lng, lat = coords[0], coords[1]

            # Search for bench features in a small area around the image
            buffer = 0.0001  # Very small buffer ~10m
            bbox = (lng - buffer, lat - buffer, lng + buffer, lat + buffer)

            # Use the main search method
            images_with_detections = self.search_images_with_detections(bbox, limit=100)

            # Filter results for this specific image
            for image_result in images_with_detections.images:
                if image_result.image_id == image_id:
                    return image_result.detections

            return []

        except requests.RequestException:
            logger.exception(f"Error fetching detections for image {image_id}")
            return []

    def search_benches_by_location(
        self, center_lat: float, center_lng: float, radius_meters: int = 1000
    ) -> MapillarySearchResult:
        """
        Search for bench detections around a center point.

        Args:
            center_lat: Center latitude
            center_lng: Center longitude
            radius_meters: Search radius in meters

        Returns:
            MapillarySearchResult with found detections
        """
        # Convert radius to approximate degrees
        # 1 degree ≈ 111,000 meters at equator
        radius_deg = radius_meters / 111000

        bbox = (
            center_lng - radius_deg,  # min_lng
            center_lat - radius_deg,  # min_lat
            center_lng + radius_deg,  # max_lng
            center_lat + radius_deg,  # max_lat
        )

        return self.search_images_with_detections(bbox)

    def download_image(
        self, image_id: str, size: int = 2048, filename: Optional[str] = None
    ) -> MapillaryImageDownloadResult:
        """
        Download a Mapillary image.

        Args:
            image_id: Mapillary image ID
            size: Image size (width in pixels, height will be proportional)
            filename: Custom filename (if None, uses image_id)

        Returns:
            MapillaryImageDownloadResult with download info
        """
        if filename is None:
            filename = f"mapillary_{image_id}.jpg"

        filepath = os.path.join(self.images_dir, filename)

        # Check if image already exists
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            logger.debug(
                f"Image {image_id} already exists at {filepath} ({file_size} bytes)"
            )
            return MapillaryImageDownloadResult(
                success=True,
                image_id=image_id,
                filepath=filepath,
                filename=filename,
                file_size=file_size,
                downloaded=False,  # Already existed
            )

        # Download the image
        url = f"{self.base_url}/{image_id}"
        params = {
            "fields": "thumb_2048_url"
            if size >= 2048
            else "thumb_1024_url"
            if size >= 1024
            else "thumb_256_url",
            "access_token": self.access_token,
        }

        try:
            # First get the image metadata with thumb URL
            response = self.session.get(url, params=params)
            response.raise_for_status()

            # Parse metadata using Pydantic
            raw_data = response.json()
            metadata = MapillaryImageMetadata(**raw_data)

            # Get the appropriate thumbnail URL
            thumb_url = metadata.get_thumb_url(size)

            if not thumb_url:
                logger.error(f"No thumbnail URL found for image {image_id}")
                return MapillaryImageDownloadResult(
                    success=False, image_id=image_id, error="No thumbnail URL found"
                )

            # Download the image
            logger.info(f"Downloading Mapillary image {image_id} from {thumb_url}")
            img_response = self.session.get(thumb_url)
            img_response.raise_for_status()

            # Save the image
            with open(filepath, "wb") as f:
                f.write(img_response.content)

            file_size = len(img_response.content)
            logger.info(
                f"Successfully downloaded image {image_id} to {filepath} ({file_size} bytes)"
            )

            return MapillaryImageDownloadResult(
                success=True,
                image_id=image_id,
                filepath=filepath,
                filename=filename,
                file_size=file_size,
                downloaded=True,
                thumb_url=thumb_url,
            )

        except requests.RequestException as e:
            logger.exception(f"Error downloading image {image_id}")
            return MapillaryImageDownloadResult(
                success=False, image_id=image_id, error=str(e)
            )
        except Exception:
            logger.exception(f"Unexpected error downloading image {image_id}")
            return MapillaryImageDownloadResult(
                success=False, image_id=image_id, error=str(e)
            )

    def download_images_for_benches(
        self, images: list[MapillaryImage]
    ) -> list[MapillaryImageDownloadResult]:
        """
        Download all images that contain bench detections.

        Args:
            images: List of MapillaryImage objects with bench detections

        Returns:
            List of MapillaryImageDownloadResult objects
        """
        download_results = []

        for image in images:
            if image.detections:  # Only download if there are bench detections
                result = self.download_image(image.image_id)
                download_results.append(result)

        success_count = sum(1 for r in download_results if r.success)
        logger.info(
            f"Downloaded {success_count}/{len(download_results)} Mapillary images"
        )

        return download_results

    def get_detection_statistics(
        self, images: list[MapillaryImage]
    ) -> MapillaryDetectionStatistics:
        """Get statistics about bench detections."""
        return MapillaryDetectionStatistics.from_images(images)


def create_mapillary_client(access_token: str) -> MapillaryBenchDetector:
    """Create a Mapillary client instance."""
    return MapillaryBenchDetector(access_token)
