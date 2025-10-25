"""
Mapillary bench generator implementation.

Provides a BenchGenerator that uses Mapillary crowd-sourced detections.
"""

import logging
import math

from clients.mapillary_client import MapillaryBenchDetector, MapillaryImage
from config import (
    IMAGES_DIR,
    MAPILLARY_ACCESS_TOKEN,
    MAPILLARY_API_LIMIT_PER_REQUEST,
    MAPILLARY_MAX_CHUNK_SIZE_METERS,
)

from models.enums import DataSource

from .bench_generator import BenchCandidate, BenchGenerator


logger = logging.getLogger(__name__)


class MapillaryBenchGenerator(BenchGenerator):
    """Bench generator that uses Mapillary crowd-sourced bench detections."""

    def __init__(self, access_token: str | None = None):
        super().__init__("Mapillary")

        self.access_token = access_token or MAPILLARY_ACCESS_TOKEN
        if not self.access_token:
            raise ValueError(
                "Mapillary access token is required. Set MAPILLARY_ACCESS_TOKEN environment variable."
            )

        self.mapillary_client = MapillaryBenchDetector(
            access_token=self.access_token, images_dir=IMAGES_DIR
        )

    def get_source_identifier(self) -> DataSource:
        return DataSource.MAPILLARY

    def supports_area_search(self) -> bool:
        return True

    def find_benches_near_point(
        self, lat: float, lng: float, radius: int = 1000
    ) -> list[BenchCandidate]:
        try:
            logger.debug(
                f"Searching Mapillary for benches near {lat}, {lng} (radius: {radius}m)"
            )

            if radius * 2 <= MAPILLARY_MAX_CHUNK_SIZE_METERS:
                search_result = self.mapillary_client.search_benches_by_location(
                    lat, lng, radius
                )
                mapillary_images = search_result.images
            else:
                logger.info(
                    f"Large search area ({radius}m radius) - breaking into chunks of {MAPILLARY_MAX_CHUNK_SIZE_METERS}m"
                )
                radius_deg = radius / 111000
                min_lng = lng - radius_deg
                min_lat = lat - radius_deg
                max_lng = lng + radius_deg
                max_lat = lat + radius_deg
                mapillary_images = self._search_area_chunked(
                    min_lng, min_lat, max_lng, max_lat
                )

            bench_candidates = []
            for mapillary_image in mapillary_images:
                candidates = self._convert_mapillary_image_to_candidates(
                    mapillary_image
                )
                bench_candidates.extend(candidates)

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
        try:
            logger.debug(
                f"Searching Mapillary for benches in area: {min_lng}, {min_lat}, {max_lng}, {max_lat}"
            )
            mapillary_images = self._search_area_chunked(
                min_lng, min_lat, max_lng, max_lat, **kwargs
            )

            bench_candidates = []
            for mapillary_image in mapillary_images:
                candidates = self._convert_mapillary_image_to_candidates(
                    mapillary_image
                )
                bench_candidates.extend(candidates)

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
        candidates = []
        for i, detection in enumerate(mapillary_image.detections):
            try:
                provider_id = f"mapillary_{mapillary_image.image_id}_{i}"
                candidate = BenchCandidate(
                    provider_id=provider_id,
                    lat=mapillary_image.coordinates[1],
                    lng=mapillary_image.coordinates[0],
                    source=DataSource.MAPILLARY,
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
        download_results = []
        image_ids = set()
        for candidate in candidates:
            if candidate.source == DataSource.MAPILLARY:
                image_id = candidate.tags.get("image_id")
                if image_id:
                    image_ids.add(image_id)

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
        lat_meters = (max_lat - min_lat) * 111000
        lng_meters = (
            (max_lng - min_lng)
            * 111000
            * math.cos(math.radians((min_lat + max_lat) / 2))
        )

        logger.debug(f"Search area: {lat_meters:.0f}m x {lng_meters:.0f}m")

        chunk_size = MAPILLARY_MAX_CHUNK_SIZE_METERS
        lat_chunks = max(1, math.ceil(lat_meters / chunk_size))
        lng_chunks = max(1, math.ceil(lng_meters / chunk_size))
        total_chunks = lat_chunks * lng_chunks
        logger.info(
            f"Breaking search area into {lat_chunks}x{lng_chunks} = {total_chunks} chunks"
        )

        all_images: list[MapillaryImage] = []
        chunks_processed = 0
        lat_step = (max_lat - min_lat) / lat_chunks
        lng_step = (max_lng - min_lng) / lng_chunks
        overlap_deg = 0.0001

        for lat_i in range(lat_chunks):
            for lng_i in range(lng_chunks):
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
                        logger.debug(
                            f"Chunk {chunks_processed + 1} found {len(chunk_images)} images"
                        )
                    else:
                        logger.debug(f"Chunk {chunks_processed + 1} found no images")
                except Exception as e:
                    logger.warning(f"Error searching chunk {chunks_processed + 1}: {e}")

                chunks_processed += 1

        unique_images = self._deduplicate_images_by_id(all_images)
        logger.info(f"After deduplication: {len(unique_images)} unique images")
        return unique_images

    def _deduplicate_images_by_id(
        self, images: list[MapillaryImage]
    ) -> list[MapillaryImage]:
        seen_ids = set()
        unique_images: list[MapillaryImage] = []
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
        seen_image_ids = set()
        unique_candidates: list[BenchCandidate] = []
        for candidate in candidates:
            image_id = candidate.tags.get("image_id") if candidate.tags else None
            if image_id and image_id not in seen_image_ids:
                unique_candidates.append(candidate)
                seen_image_ids.add(image_id)
            elif not image_id:
                unique_candidates.append(candidate)
            else:
                logger.debug(f"Skipping duplicate candidate from image: {image_id}")
        return unique_candidates
