"""
Mapillary bench generator implementation.

This module provides a BenchGenerator implementation that uses the existing
MapillaryBenchDetector to find benches from Mapillary crowd-sourced data.
"""

import logging
import math
from typing import Optional

from bench_finder.clients.mapillary_client import MapillaryBenchDetector, MapillaryImage
from bench_finder.config import (
    IMAGES_DIR,
    MAPILLARY_ACCESS_TOKEN,
    MAPILLARY_API_LIMIT_PER_REQUEST,
    MAPILLARY_MAX_CHUNK_SIZE_METERS,
)

from .bench_generator import BenchCandidate, BenchGenerator


logger = logging.getLogger(__name__)


class MapillaryBenchGenerator(BenchGenerator):
    """Bench generator that uses Mapillary crowd-sourced bench detections."""

    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize the Mapillary bench generator.

        Args:
            access_token: Mapillary API access token. If None, uses config.MAPILLARY_ACCESS_TOKEN
        """
        super().__init__("Mapillary")

        self.access_token = access_token or MAPILLARY_ACCESS_TOKEN
        if not self.access_token:
            raise ValueError(
                "Mapillary access token is required. Set MAPILLARY_ACCESS_TOKEN environment variable."
            )

        self.mapillary_client = MapillaryBenchDetector(
            access_token=self.access_token, images_dir=IMAGES_DIR
        )

    def get_source_identifier(self) -> str:
        """Get the source identifier for Mapillary data."""
        return "mapillary"

    def supports_area_search(self) -> bool:
        """Mapillary supports efficient area-based searches via bounding boxes."""
        return True

    def find_benches_near_point(
        self, lat: float, lng: float, radius: int = 1000
    ) -> list[BenchCandidate]:
        """
        Find benches from Mapillary data near a point.

        For large search areas, automatically breaks down into smaller chunks
        for better API performance.

        Args:
            lat: Latitude of the center point
            lng: Longitude of the center point
            radius: Search radius in meters

        Returns:
            List of BenchCandidate objects from Mapillary data

        Raises:
            Exception: If the Mapillary API call fails
        """
        try:
            logger.debug(
                f"Searching Mapillary for benches near {lat}, {lng} (radius: {radius}m)"
            )

            # Check if we need to chunk the search area
            if radius * 2 <= MAPILLARY_MAX_CHUNK_SIZE_METERS:
                # Small enough area - use single request
                search_result = self.mapillary_client.search_benches_by_location(
                    lat, lng, radius
                )
                mapillary_images = search_result.images
            else:
                # Large area - break into chunks
                logger.info(
                    f"Large search area ({radius}m radius) - breaking into chunks of {MAPILLARY_MAX_CHUNK_SIZE_METERS}m"
                )

                # Convert to bounding box and chunk it
                radius_deg = radius / 111000  # Approximate conversion
                min_lng = lng - radius_deg
                min_lat = lat - radius_deg
                max_lng = lng + radius_deg
                max_lat = lat + radius_deg

                mapillary_images = self._search_area_chunked(
                    min_lng, min_lat, max_lng, max_lat
                )

            # Convert MapillaryImage objects to BenchCandidate objects
            bench_candidates = []
            for mapillary_image in mapillary_images:
                candidates = self._convert_mapillary_image_to_candidates(
                    mapillary_image
                )
                bench_candidates.extend(candidates)

            # Remove duplicates that might come from overlapping chunks
            unique_candidates = self._deduplicate_by_image_id(bench_candidates)

            self._update_stats(success=True, bench_count=len(unique_candidates))
            logger.info(
                f"Found {len(unique_candidates)} unique Mapillary benches from {len(mapillary_images)} images"
            )
            return unique_candidates

        except Exception:
            self._update_stats(success=False)
            logger.exception("Mapillary bench search failed")
            raise

    def find_benches_in_area(
        self, min_lng: float, min_lat: float, max_lng: float, max_lat: float, **kwargs
    ) -> list[BenchCandidate]:
        """
        Find benches within a bounding box using Mapillary data.

        Automatically breaks large areas into smaller chunks for better API performance.

        Args:
            min_lng: Minimum longitude
            min_lat: Minimum latitude
            max_lng: Maximum longitude
            max_lat: Maximum latitude
            **kwargs: Additional search parameters (e.g., limit)

        Returns:
            List of BenchCandidate objects
        """
        try:
            logger.debug(
                f"Searching Mapillary for benches in area: {min_lng}, {min_lat}, {max_lng}, {max_lat}"
            )

            # Always use chunked search for area queries to ensure good API performance
            mapillary_images = self._search_area_chunked(
                min_lng, min_lat, max_lng, max_lat, **kwargs
            )

            # Convert MapillaryImage objects to BenchCandidate objects
            bench_candidates = []
            for mapillary_image in mapillary_images:
                candidates = self._convert_mapillary_image_to_candidates(
                    mapillary_image
                )
                bench_candidates.extend(candidates)

            # Remove duplicates that might come from overlapping chunks
            unique_candidates = self._deduplicate_by_image_id(bench_candidates)

            self._update_stats(success=True, bench_count=len(unique_candidates))
            logger.info(
                f"Found {len(unique_candidates)} unique Mapillary benches from {len(mapillary_images)} images in bbox"
            )
            return unique_candidates

        except Exception:
            self._update_stats(success=False)
            logger.exception("Mapillary area search failed")
            raise

    def _convert_mapillary_image_to_candidates(
        self, mapillary_image: MapillaryImage
    ) -> list[BenchCandidate]:
        """
        Convert a MapillaryImage with detections to BenchCandidate objects.

        Each detection in the image becomes a separate BenchCandidate.

        Args:
            mapillary_image: MapillaryImage object with bench detections

        Returns:
            List of BenchCandidate objects (one per detection)
        """
        candidates = []

        for i, detection in enumerate(mapillary_image.detections):
            try:
                # Create unique provider_id combining image ID and detection index
                provider_id = f"mapillary_{mapillary_image.image_id}_{i}"

                # Use image coordinates as bench location
                # Note: This is an approximation since we don't have precise bench coordinates
                candidate = BenchCandidate(
                    provider_id=provider_id,
                    lat=mapillary_image.coordinates[1],  # coordinates are (lng, lat)
                    lng=mapillary_image.coordinates[0],
                    source="mapillary",
                    external_id=detection.detection_id,
                    tags={
                        "image_id": mapillary_image.image_id,
                        "detection_value": detection.value,
                        "geometry_encoded": detection.geometry_encoded,
                        "created_at": detection.created_at.isoformat()
                        if detection.created_at
                        else None,
                    },
                    confidence=detection.confidence,
                )
                candidates.append(candidate)

            except Exception as e:
                logger.warning(
                    f"Failed to convert Mapillary detection to candidate: {e}"
                )
                continue

        return candidates

    def download_images_for_candidates(
        self, candidates: list[BenchCandidate]
    ) -> list[dict]:
        """
        Download images for Mapillary bench candidates.

        This is a helper method specific to Mapillary that can download
        the original images for further processing.

        Args:
            candidates: List of BenchCandidate objects from Mapillary

        Returns:
            List of download result dictionaries
        """
        download_results = []

        # Group candidates by image_id to avoid duplicate downloads
        image_ids = set()
        for candidate in candidates:
            if candidate.source == "mapillary":
                image_id = candidate.tags.get("image_id")
                if image_id:
                    image_ids.add(image_id)

        # Download each unique image
        for image_id in image_ids:
            try:
                result = self.mapillary_client.download_image(image_id)
                if result:
                    download_results.append(result)
            except Exception as e:
                logger.warning(f"Failed to download Mapillary image {image_id}: {e}")

        success_count = sum(1 for r in download_results if r.get("success", False))
        logger.info(
            f"Downloaded {success_count}/{len(image_ids)} Mapillary images for candidates"
        )

        return download_results

    def _search_area_chunked(
        self, min_lng: float, min_lat: float, max_lng: float, max_lat: float, **kwargs
    ) -> list[MapillaryImage]:
        """
        Search a bounding box area by breaking it into smaller chunks.

        Args:
            min_lng: Minimum longitude
            min_lat: Minimum latitude
            max_lng: Maximum longitude
            max_lat: Maximum latitude
            **kwargs: Additional parameters like limit

        Returns:
            List of MapillaryImage objects from all chunks
        """
        # Calculate area dimensions in meters (approximate)
        lat_meters = (max_lat - min_lat) * 111000  # ~111km per degree latitude
        lng_meters = (
            (max_lng - min_lng)
            * 111000
            * math.cos(math.radians((min_lat + max_lat) / 2))
        )

        logger.debug(f"Search area: {lat_meters:.0f}m x {lng_meters:.0f}m")

        # Determine number of chunks needed
        chunk_size = MAPILLARY_MAX_CHUNK_SIZE_METERS
        lat_chunks = max(1, math.ceil(lat_meters / chunk_size))
        lng_chunks = max(1, math.ceil(lng_meters / chunk_size))

        total_chunks = lat_chunks * lng_chunks
        logger.info(
            f"Breaking search area into {lat_chunks}x{lng_chunks} = {total_chunks} chunks"
        )

        all_images = []
        chunks_processed = 0
        chunks_with_results = 0

        # Calculate chunk dimensions
        lat_step = (max_lat - min_lat) / lat_chunks
        lng_step = (max_lng - min_lng) / lng_chunks

        # Add small overlap between chunks to avoid missing detections at boundaries
        overlap_deg = 0.0001  # ~10 meters

        for lat_i in range(lat_chunks):
            for lng_i in range(lng_chunks):
                # Calculate chunk boundaries with overlap
                chunk_min_lat = (
                    min_lat + (lat_i * lat_step) - (overlap_deg if lat_i > 0 else 0)
                )
                chunk_max_lat = (
                    min_lat
                    + ((lat_i + 1) * lat_step)
                    + (overlap_deg if lat_i < lat_chunks - 1 else 0)
                )
                chunk_min_lng = (
                    min_lng + (lng_i * lng_step) - (overlap_deg if lng_i > 0 else 0)
                )
                chunk_max_lng = (
                    min_lng
                    + ((lng_i + 1) * lng_step)
                    + (overlap_deg if lng_i < lng_chunks - 1 else 0)
                )

                # Ensure boundaries don't exceed original area
                chunk_min_lat = max(chunk_min_lat, min_lat)
                chunk_max_lat = min(chunk_max_lat, max_lat)
                chunk_min_lng = max(chunk_min_lng, min_lng)
                chunk_max_lng = min(chunk_max_lng, max_lng)

                try:
                    logger.debug(
                        f"Searching chunk {chunks_processed + 1}/{total_chunks}: "
                        f"({chunk_min_lng:.4f}, {chunk_min_lat:.4f}) to ({chunk_max_lng:.4f}, {chunk_max_lat:.4f})"
                    )

                    bbox = (chunk_min_lng, chunk_min_lat, chunk_max_lng, chunk_max_lat)
                    limit = kwargs.get("limit", MAPILLARY_API_LIMIT_PER_REQUEST)

                    search_result = self.mapillary_client.search_images_with_detections(
                        bbox, limit
                    )
                    chunk_images = search_result.images

                    if chunk_images:
                        all_images.extend(chunk_images)
                        chunks_with_results += 1
                        logger.debug(
                            f"Chunk {chunks_processed + 1} found {len(chunk_images)} images"
                        )
                    else:
                        logger.debug(f"Chunk {chunks_processed + 1} found no images")

                except Exception as e:
                    logger.warning(f"Error searching chunk {chunks_processed + 1}: {e}")

                chunks_processed += 1

        logger.info(
            f"Chunked search complete: {len(all_images)} total images from {chunks_with_results}/{total_chunks} chunks"
        )

        # Remove duplicate images that may appear in overlapping chunks
        unique_images = self._deduplicate_images_by_id(all_images)
        logger.info(f"After deduplication: {len(unique_images)} unique images")

        return unique_images

    def _deduplicate_images_by_id(
        self, images: list[MapillaryImage]
    ) -> list[MapillaryImage]:
        """
        Remove duplicate MapillaryImage objects based on image_id.

        Args:
            images: List of MapillaryImage objects that may contain duplicates

        Returns:
            List of unique MapillaryImage objects
        """
        seen_ids = set()
        unique_images = []

        for image in images:
            if image.image_id not in seen_ids:
                unique_images.append(image)
                seen_ids.add(image.image_id)
            else:
                logger.debug(f"Skipping duplicate image: {image.image_id}")

        return unique_images

    def _deduplicate_by_image_id(
        self, candidates: list[BenchCandidate]
    ) -> list[BenchCandidate]:
        """
        Remove duplicate BenchCandidate objects based on Mapillary image_id.

        Args:
            candidates: List of BenchCandidate objects that may contain duplicates

        Returns:
            List of unique BenchCandidate objects
        """
        seen_image_ids = set()
        unique_candidates = []

        for candidate in candidates:
            image_id = candidate.tags.get("image_id")
            if image_id and image_id not in seen_image_ids:
                unique_candidates.append(candidate)
                seen_image_ids.add(image_id)
            elif not image_id:
                # Keep candidates without image_id (shouldn't happen but be safe)
                unique_candidates.append(candidate)
            else:
                logger.debug(f"Skipping duplicate candidate from image: {image_id}")

        return unique_candidates
