"""
Bench finder pipeline orchestration.

This module contains the BenchFinder class that orchestrates the complete
bench finding pipeline: geocoding, candidate generation, and image capture.
Detection is handled separately by the BenchDetector class.
"""

import logging
import math
from typing import TYPE_CHECKING, Optional

from bench_finder.config import MAPILLARY_ACCESS_TOKEN, SEARCH_RADIUS_METERS
from bench_finder.core.geocoder import Geocoder
from bench_finder.models.schemas import (
    PipelineResult,
    ProcessingStats,
    SearchCreate,
)
from bench_finder.services.database import BenchDatabase
from bench_finder.services.image_download_service import ImageDownloadService
from bench_finder.utils import log_execution_time, retry_on_failure
from examples.bench_generator import BenchCandidate, BenchGenerator
from examples.mapillary_bench_generator import MapillaryBenchGenerator
from examples.overpass_bench_generator import OverpassBenchGenerator




logger = logging.getLogger(__name__)


class BenchFinder:
    """Main class that orchestrates the bench finding pipeline."""

    def __init__(
        self,
        bench_generators: list[BenchGenerator] | None = None,
    ):
        """Initialize all API clients and database.

        Args:
            bench_generators: List of BenchGenerator instances to use for finding benches.
                            If None, creates default generators (OSM + Mapillary if available)
        """
        self.geocoder = Geocoder()
        self.database = BenchDatabase()
        self.image_download_service = ImageDownloadService()

        # Initialize bench generators
        if bench_generators is None:
            self.bench_generators = self._create_default_generators()
        else:
            self.bench_generators = bench_generators

        logger.info(
            f"BenchFinder initialized with {len(self.bench_generators)} generators: {[g.name for g in self.bench_generators]}"
        )

    def _create_default_generators(self) -> list[BenchGenerator]:
        """Create default set of bench generators."""
        generators: list[BenchGenerator] = []

        # Always add OSM generator
        try:
            osm_generator = OverpassBenchGenerator()
            generators.append(osm_generator)
            logger.info("Added OpenStreetMap generator")
        except Exception:
            logger.exception("Failed to initialize OSM generator")

        # Add Mapillary generator if token is available
        try:
            if MAPILLARY_ACCESS_TOKEN:
                mapillary_generator = MapillaryBenchGenerator()
                generators.append(mapillary_generator)
                logger.info("Added Mapillary generator")
            else:
                logger.warning(
                    "MAPILLARY_ACCESS_TOKEN not set - Mapillary generator not available"
                )
        except Exception as e:
            logger.warning(f"Failed to initialize Mapillary generator: {e}")

        if not generators:
            raise ValueError("No bench generators could be initialized")

        return generators


    @log_execution_time
    def find_benches(self, query: str, radius: int | None = None) -> PipelineResult:
        """
        Complete bench finding pipeline for a given query.

        Args:
            query: Search query (address, location name, etc.)
            radius: Search radius in meters (defaults to config value)

        Returns:
            PipelineResult with results and statistics
        """
        if radius is None:
            radius = SEARCH_RADIUS_METERS

        logger.info(
            f"Starting bench finding pipeline for query: '{query}' (radius: {radius}m)"
        )

        try:
            # Step 1: Geocode the query
            coordinates = self._geocode_query(query)
            if not coordinates:
                return self._create_error_result("Failed to geocode query")

            start_lat, start_lng = coordinates

            # Step 2: Create search record in database
            search_id = self.database.create_search(
                SearchCreate(
                    query=query,
                    start_lat=start_lat,
                    start_lng=start_lng,
                    search_radius=radius,
                )
            )

            # Step 3: Find benches using all available generators (OSM, Mapillary, etc.)
            benches: list[BenchCandidate] = self._find_nearby_benches(
                start_lat, start_lng, radius
            )
            if not benches:
                self.database.update_search_status(search_id, "completed")
                return self._create_result(search_id, "No benches found in the area")

            logger.info(f"Found {len(benches)} benches to process")

            # Step 4: Process each bench (add to database and capture images)
            results = self._process_benches(search_id, benches)

            # Step 5: Mark search as completed
            self.database.update_search_status(search_id, "completed")

            # Step 6: Generate final results
            return self._create_result(
                search_id, f"Successfully processed {len(benches)} benches", results
            )

        except Exception as e:
            logger.exception("Bench finding pipeline failed")
            if "search_id" in locals():
                self.database.update_search_status(search_id, "failed")
            return self._create_error_result(f"Pipeline failed: {e}")

    @retry_on_failure(max_retries=2, delay=1.0)
    def _geocode_query(self, query: str) -> Optional[tuple]:
        """Geocode a query string to coordinates."""
        logger.info(f"Geocoding query: {query}")
        return self.geocoder.geocode_query(query)

    @retry_on_failure(max_retries=2, delay=2.0)
    def _find_nearby_benches(
        self, lat: float, lng: float, radius: int
    ) -> list[BenchCandidate]:
        """Find benches near the given coordinates using all generators."""
        logger.info(
            f"Searching for benches within {radius}m of {lat}, {lng} using {len(self.bench_generators)} generators"
        )

        all_candidates = []
        generator_results = {}

        # Query each generator
        for generator in self.bench_generators:
            try:
                logger.debug(f"Querying {generator.name} for benches")
                candidates = generator.find_benches_near_point(lat, lng, radius)
                all_candidates.extend(candidates)
                generator_results[generator.name] = len(candidates)
                logger.info(
                    f"{generator.name}: found {len(candidates)} bench candidates"
                )
            except Exception:
                logger.exception(f"Error querying {generator.name}")
                generator_results[generator.name] = 0

        logger.info(
            f"Total bench candidates found: {len(all_candidates)} ({generator_results})"
        )


        # Deduplicate benches based on proximity (same location from different sources)
        deduplicated_candidates = self._deduplicate_bench_candidates(all_candidates)
        logger.info(
            f"After deduplication: {len(deduplicated_candidates)} unique benches"
        )

        return deduplicated_candidates

    def _deduplicate_bench_candidates(
        self, candidates: list[BenchCandidate]
    ) -> list[BenchCandidate]:
        """
        Remove duplicate bench candidates based on proximity.

        Two benches are considered duplicates if they are within 10 meters of each other.
        When duplicates are found, prefers the one with higher confidence or from OSM.

        Args:
            candidates: List of BenchCandidate objects

        Returns:
            List of unique BenchCandidate objects
        """
        if not candidates:
            return candidates

        # Distance threshold for considering two benches as duplicates (meters)
        DUPLICATE_THRESHOLD_METERS = 10

        unique_candidates: list[BenchCandidate] = []

        for candidate in candidates:
            is_duplicate = False

            # Check if this candidate is close to any existing unique candidate
            for i, existing in enumerate(unique_candidates):
                distance = self._haversine_distance(
                    candidate.lat, candidate.lng, existing.lat, existing.lng
                )

                if distance <= DUPLICATE_THRESHOLD_METERS:
                    is_duplicate = True

                    # Replace existing if current candidate is "better"
                    if self._is_better_candidate(candidate, existing):
                        unique_candidates[i] = candidate
                        logger.debug(
                            f"Replaced duplicate bench: {existing.provider_id} -> {candidate.provider_id}"
                        )
                    else:
                        logger.debug(
                            f"Skipped duplicate bench: {candidate.provider_id} (keeping {existing.provider_id})"
                        )
                    break

            if not is_duplicate:
                unique_candidates.append(candidate)

        return unique_candidates

    def _is_better_candidate(
        self, candidate1: BenchCandidate, candidate2: BenchCandidate
    ) -> bool:
        """
        Determine which candidate is "better" for deduplication purposes.

        Args:
            candidate1: First candidate
            candidate2: Second candidate

        Returns:
            True if candidate1 is better than candidate2
        """
        # Prefer candidate with confidence score
        if candidate1.confidence is not None and candidate2.confidence is None:
            return True
        if candidate1.confidence is None and candidate2.confidence is not None:
            return False

        # If both have confidence, prefer higher confidence
        if candidate1.confidence is not None and candidate2.confidence is not None:
            return candidate1.confidence > candidate2.confidence

        # If neither has confidence, prefer OSM (more reliable positioning)
        if candidate1.source == "osm" and candidate2.source != "osm":
            return True
        if candidate1.source != "osm" and candidate2.source == "osm":
            return False

        # If same source type, prefer the first one (arbitrary)
        return False

    def _haversine_distance(
        self, lat1: float, lng1: float, lat2: float, lng2: float
    ) -> float:
        """
        Calculate the Haversine distance between two points in meters.

        Args:
            lat1, lng1: First point coordinates
            lat2, lng2: Second point coordinates

        Returns:
            Distance in meters
        """
        # Convert decimal degrees to radians
        lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])

        # Haversine formula
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        )
        c = 2 * math.asin(math.sqrt(a))

        # Radius of Earth in meters
        R = 6371000
        return R * c

    def _process_benches(
        self, search_id: int, benches: list[BenchCandidate]
    ) -> ProcessingStats:
        """
        Process each bench: add to database and capture images.

        Args:
            search_id: Database search ID
            benches: List of bench dictionaries from various sources (OSM, Mapillary, etc.)

        Returns:
            ProcessingStats with processing results summary
        """
        # Use the ImageDownloadService to process benches
        return self.image_download_service.process_benches(search_id, benches)

    # _process_single_bench method removed - now handled by ImageDownloadService

    def _create_result(
        self, search_id: int, message: str, stats: ProcessingStats | None = None
    ) -> PipelineResult:
        """Create a standardized result."""
        self.database.get_search_results(search_id)

        return PipelineResult(
            success=True, search_id=search_id, message=message, stats=stats
        )

    def _create_error_result(self, error_message: str) -> PipelineResult:
        """Create a standardized error result."""
        return PipelineResult(
            success=False, search_id=None, message="", error=error_message
        )
