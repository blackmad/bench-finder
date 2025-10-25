"""
OpenStreetMap Overpass API integration for finding benches.
"""

import json
import logging

import requests
from clients.base_location_client import (
    BaseLocationClient,
    LocationSearchResult,
)
from config import OVERPASS_TIMEOUT, OVERPASS_URL, SEARCH_RADIUS_METERS

from models.enums import DataSource
from models.overpass_models import (
    OSMBench,
    OverpassResponse,
    OverpassSearchResult,
)
from models.unified_models import UnifiedBench, UnifiedSearchResult


logger = logging.getLogger(__name__)


class OverpassClient(BaseLocationClient):
    """Client for querying OpenStreetMap data via Overpass API."""

    def __init__(self):
        """Initialize the Overpass client."""
        super().__init__("OverpassClient")
        self.base_url = OVERPASS_URL
        self.timeout = OVERPASS_TIMEOUT

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
        result = self.find_benches_near_point(lat, lng, radius)
        return LocationSearchResult(
            search_center_lat=result.search_center_lat,
            search_center_lng=result.search_center_lng,
            search_radius_meters=result.search_radius_meters,
            total_count=result.total_count,
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
        result = self.find_benches_near_point(lat, lng, radius)

        # Convert OSMBench objects to UnifiedBench objects
        unified_benches = [
            UnifiedBench.from_osm_bench(bench) for bench in result.benches
        ]

        return UnifiedSearchResult(
            benches=unified_benches,
            search_center_lat=result.search_center_lat,
            search_center_lng=result.search_center_lng,
            search_radius_meters=result.search_radius_meters,
            total_count=result.total_count,
            source=DataSource.OSM,
        )

    def find_benches_near_point(
        self, lat: float, lng: float, radius: int | None = None
    ) -> OverpassSearchResult:
        """
        Find all benches within a radius of a given point using Overpass API.

        Args:
            lat: Latitude of the center point
            lng: Longitude of the center point
            radius: Search radius in meters (defaults to SEARCH_RADIUS_METERS)

        Returns:
            OverpassSearchResult with found benches

        Raises:
            Exception: If Overpass API call fails
        """
        if radius is None:
            radius = SEARCH_RADIUS_METERS

        try:
            logger.info(f"Searching for benches within {radius}m of {lat}, {lng}")

            # Build Overpass QL query to find benches
            query = f"""
            [out:json][timeout:{self.timeout}];
            (
              node["amenity"="bench"](around:{radius},{lat},{lng});
              way["amenity"="bench"](around:{radius},{lat},{lng});
              relation["amenity"="bench"](around:{radius},{lat},{lng});
            );
            out geom;
            """

            # Make request to Overpass API
            response = requests.post(
                self.base_url, data={"data": query}, timeout=self.timeout
            )
            response.raise_for_status()

            # Parse response using Pydantic
            raw_data = response.json()
            overpass_response = OverpassResponse(**raw_data)

            # Convert elements to benches
            benches = []
            for element in overpass_response.elements:
                bench = OSMBench.from_osm_element(element)
                if bench:
                    benches.append(bench)

            logger.info(f"Found {len(benches)} benches within {radius}m")

            return OverpassSearchResult(
                benches=benches,
                search_center_lat=lat,
                search_center_lng=lng,
                search_radius_meters=radius,
                total_count=len(benches),
            )

        except requests.exceptions.RequestException:
            logger.exception("HTTP error querying Overpass API")
            raise
        except json.JSONDecodeError:
            logger.exception("JSON decode error from Overpass API")
            raise
        except Exception:
            logger.exception("Unexpected error querying Overpass API")
            raise

    def get_item_details(self, provider_id: str) -> dict | None:
        """
        Get detailed information about a specific bench (implements BaseLocationClient interface).

        Args:
            provider_id: Provider ID in format "osm_id_osm_type"

        Returns:
            Dictionary with bench details or None if not found
        """
        bench = self.get_bench_details(provider_id)
        if bench:
            return bench.model_dump()
        return None

    def get_bench_details(self, provider_id: str) -> OSMBench | None:
        """
        Get detailed information about a specific bench.

        Args:
            provider_id: Provider ID in format "osm_id_osm_type"

        Returns:
            OSMBench object with detailed information or None if not found
        """
        try:
            # Parse provider_id to extract osm_id and osm_type
            parts = provider_id.split("_")
            if len(parts) < 2:
                logger.error(f"Invalid provider_id format: {provider_id}")
                return {}

            osm_id = parts[0]
            osm_type = parts[1]

            logger.debug(f"Getting details for {osm_type} {osm_id}")

            query = f"""
            [out:json][timeout:{self.timeout}];
            {osm_type}({osm_id});
            out geom;
            """

            response = requests.post(
                self.base_url, data={"data": query}, timeout=self.timeout
            )
            response.raise_for_status()

            # Parse response using Pydantic
            raw_data = response.json()
            overpass_response = OverpassResponse(**raw_data)

            if not overpass_response.elements:
                logger.warning(f"No details found for {osm_type} {osm_id}")
                return None

            # Convert first element to bench
            return OSMBench.from_osm_element(overpass_response.elements[0])

        except Exception:
            logger.exception(
                f"Error getting bench details for provider_id {provider_id}"
            )
            return None
