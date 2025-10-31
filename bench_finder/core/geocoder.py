"""
Google Geocoder integration for converting address/query strings to coordinates.
"""

import logging

import googlemaps

from bench_finder.config import GOOGLE_MAPS_API_KEY


logger = logging.getLogger(__name__)


class Geocoder:
    """Google Geocoding API client."""

    def __init__(self) -> None:
        """Initialize the geocoder with API key."""
        if not GOOGLE_MAPS_API_KEY:
            raise ValueError("GOOGLE_MAPS_API_KEY is required")

        self.gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

    def geocode_query(self, query: str) -> tuple[float, float] | None:
        """
        Convert a query string to lat/lng coordinates using Google Geocoding API.

        Args:
            query: Address or location string to geocode

        Returns:
            Tuple of (latitude, longitude) if successful, None if not found

        Raises:
            Exception: If geocoding API call fails
        """
        try:
            logger.info(f"Geocoding query: {query}")

            # Call Google Geocoding API
            geocode_result = self.gmaps.geocode(query)

            if not geocode_result:
                logger.warning(f"No geocoding results found for query: {query}")
                return None

            # Extract coordinates from the first result
            location = geocode_result[0]["geometry"]["location"]
            lat = location["lat"]
            lng = location["lng"]

            logger.info(f"Geocoded '{query}' to coordinates: {lat}, {lng}")

            # Log the formatted address for reference
            formatted_address = geocode_result[0]["formatted_address"]
            logger.info(f"Formatted address: {formatted_address}")

            return (lat, lng)

        except googlemaps.exceptions.ApiError:
            logger.exception(f"Google Maps API error geocoding '{query}'")
            raise
        except Exception:
            logger.exception(f"Unexpected error geocoding '{query}'")
            raise

    def reverse_geocode(self, lat: float, lng: float) -> str | None:
        """
        Convert coordinates to a formatted address.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Formatted address string if successful, None if not found
        """
        try:
            logger.debug(f"Reverse geocoding coordinates: {lat}, {lng}")

            # Call Google Reverse Geocoding API
            reverse_result = self.gmaps.reverse_geocode((lat, lng))

            if not reverse_result:
                logger.warning(
                    f"No reverse geocoding results found for coordinates: {lat}, {lng}"
                )
                return None

            formatted_address = reverse_result[0].get("formatted_address", "")
            if not formatted_address:
                return None
            logger.debug(f"Reverse geocoded {lat}, {lng} to: {formatted_address}")

            return str(formatted_address)

        except googlemaps.exceptions.ApiError:
            logger.exception(f"Google Maps API error reverse geocoding {lat}, {lng}")
            return None
        except Exception:
            logger.exception(f"Unexpected error reverse geocoding {lat}, {lng}")
            return None
