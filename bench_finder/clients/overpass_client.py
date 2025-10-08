"""
OpenStreetMap Overpass API integration for finding benches.
"""
import requests
import json
import logging
from typing import List, Dict, Tuple, Optional
from bench_finder.config import OVERPASS_URL, OVERPASS_TIMEOUT, SEARCH_RADIUS_METERS
from bench_finder.models.overpass_models import (
    OverpassResponse, OverpassSearchResult, OSMElement, OSMBench
)

logger = logging.getLogger(__name__)


class OverpassClient:
    """Client for querying OpenStreetMap data via Overpass API."""
    
    def __init__(self):
        """Initialize the Overpass client."""
        self.base_url = OVERPASS_URL
        self.timeout = OVERPASS_TIMEOUT
    
    def find_benches_near_point(self, lat: float, lng: float, radius: int = None) -> OverpassSearchResult:
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
                self.base_url,
                data={'data': query},
                timeout=self.timeout
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
                total_count=len(benches)
            )
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error querying Overpass API: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error from Overpass API: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error querying Overpass API: {e}")
            raise
    
    def get_bench_details(self, provider_id: str) -> Optional[OSMBench]:
        """
        Get detailed information about a specific bench.
        
        Args:
            provider_id: Provider ID in format "osm_id_osm_type"
            
        Returns:
            OSMBench object with detailed information or None if not found
        """
        try:
            # Parse provider_id to extract osm_id and osm_type
            parts = provider_id.split('_')
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
                self.base_url,
                data={'data': query},
                timeout=self.timeout
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
            
        except Exception as e:
            logger.error(f"Error getting bench details for provider_id {provider_id}: {e}")
            return None
