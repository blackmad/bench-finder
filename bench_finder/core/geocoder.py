"""
Google Geocoder integration for converting address/query strings to coordinates.
"""

import logging
from typing import Any

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

    def reverse_geocode_structured(
        self, lat: float, lng: float
    ) -> dict[str, Any] | None:
        """
        Convert coordinates to structured address components.

        Args:
            lat: Latitude
            lng: Longitude

        Returns:
            Dictionary with structured address components if successful, None if not found.
            Keys: formatted_address, street_number, street_name, city, state, postal_code, country, raw_response
        """
        try:
            logger.debug(f"Reverse geocoding coordinates (structured): {lat}, {lng}")

            # Call Google Reverse Geocoding API
            reverse_result = self.gmaps.reverse_geocode((lat, lng))

            if not reverse_result:
                logger.warning(
                    f"No reverse geocoding results found for coordinates: {lat}, {lng}"
                )
                return None

            result = reverse_result[0]
            formatted_address = result.get("formatted_address", "")
            if not formatted_address:
                return None

            # Parse address components from Google's response
            address_components = result.get("address_components", [])

            structured = {
                "formatted_address": formatted_address,
                "street_number": None,
                "street_name": None,
                "city": None,
                "state": None,
                "postal_code": None,
                "country": None,
                "raw_response": result,
            }

            # Parse address components by type
            for component in address_components:
                types = component.get("types", [])
                long_name = component.get("long_name", "")
                short_name = component.get("short_name", "")

                if "street_number" in types:
                    structured["street_number"] = long_name
                elif "route" in types:
                    structured["street_name"] = long_name
                elif "locality" in types:
                    structured["city"] = long_name
                elif "administrative_area_level_1" in types:
                    structured["state"] = (
                        short_name  # Use short name for state (e.g., "CA" instead of "California")
                    )
                elif "postal_code" in types:
                    structured["postal_code"] = long_name
                elif "country" in types:
                    structured["country"] = (
                        short_name  # Use short name for country (e.g., "US" instead of "United States")
                    )

            logger.debug(
                f"Reverse geocoded {lat}, {lng} to structured address: {structured['city']}, {structured['state']}"
            )

            return structured

        except googlemaps.exceptions.ApiError:
            logger.exception(f"Google Maps API error reverse geocoding {lat}, {lng}")
            return None
        except Exception:
            logger.exception(f"Unexpected error reverse geocoding {lat}, {lng}")
            return None
