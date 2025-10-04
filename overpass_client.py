"""
OpenStreetMap Overpass API integration for finding benches.
"""
import requests
import json
import logging
from typing import List, Dict, Tuple
from config import OVERPASS_URL, OVERPASS_TIMEOUT, SEARCH_RADIUS_METERS

logger = logging.getLogger(__name__)


class OverpassClient:
    """Client for querying OpenStreetMap data via Overpass API."""
    
    def __init__(self):
        """Initialize the Overpass client."""
        self.base_url = OVERPASS_URL
        self.timeout = OVERPASS_TIMEOUT
    
    def find_benches_near_point(self, lat: float, lng: float, radius: int = None) -> List[Dict]:
        """
        Find all benches within a radius of a given point using Overpass API.
        
        Args:
            lat: Latitude of the center point
            lng: Longitude of the center point  
            radius: Search radius in meters (defaults to SEARCH_RADIUS_METERS)
            
        Returns:
            List of bench dictionaries with id, lat, lng, and any tags
            
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
            
            data = response.json()
            
            if 'elements' not in data:
                logger.warning("No 'elements' key in Overpass response")
                return []
            
            benches = []
            for element in data['elements']:
                bench = self._parse_bench_element(element)
                if bench:
                    benches.append(bench)
            
            logger.info(f"Found {len(benches)} benches within {radius}m")
            return benches
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP error querying Overpass API: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error from Overpass API: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error querying Overpass API: {e}")
            raise
    
    def _parse_bench_element(self, element: Dict) -> Dict:
        """
        Parse a bench element from Overpass API response.
        
        Args:
            element: Raw element dictionary from Overpass response
            
        Returns:
            Parsed bench dictionary or None if invalid
        """
        try:
            osm_id = element.get('id')
            osm_type = element.get('type')
            
            bench = {
                'provider_id': f"{osm_id}_{osm_type}" if osm_id and osm_type else None,
                'source': 'osm',
                'external_id': str(osm_id) if osm_id else None,
                'tags': element.get('tags', {})
            }
            
            # Handle different element types (node, way, relation)
            if element['type'] == 'node':
                bench['lat'] = element.get('lat')
                bench['lng'] = element.get('lon')
                
            elif element['type'] == 'way':
                # For ways, use the center point of the geometry
                if 'geometry' in element and element['geometry']:
                    coords = [(node['lat'], node['lon']) for node in element['geometry']]
                    if coords:
                        # Calculate centroid
                        bench['lat'] = sum(coord[0] for coord in coords) / len(coords)
                        bench['lng'] = sum(coord[1] for coord in coords) / len(coords)
                    else:
                        logger.warning(f"Way {element['id']} has no geometry coordinates")
                        return None
                else:
                    logger.warning(f"Way {element['id']} missing geometry")
                    return None
                    
            elif element['type'] == 'relation':
                # For relations, we'd need to process the members
                # For now, skip relations as they're complex to handle
                logger.debug(f"Skipping relation {element['id']} (not implemented)")
                return None
            else:
                logger.warning(f"Unknown element type: {element['type']}")
                return None
            
            # Validate coordinates
            if bench.get('lat') is None or bench.get('lng') is None:
                logger.warning(f"Element {element['id']} missing coordinates")
                return None
                
            # Add any interesting tags for logging
            interesting_tags = []
            for tag_key in ['name', 'operator', 'material', 'backrest', 'seats']:
                if tag_key in bench['tags']:
                    interesting_tags.append(f"{tag_key}={bench['tags'][tag_key]}")
            
            if interesting_tags:
                logger.debug(f"Bench {bench['provider_id']}: {', '.join(interesting_tags)}")
            
            return bench
            
        except Exception as e:
            logger.error(f"Error parsing bench element: {e}")
            logger.debug(f"Problematic element: {element}")
            return None
    
    def get_bench_details(self, provider_id: str) -> Dict:
        """
        Get detailed information about a specific bench.
        
        Args:
            provider_id: Provider ID in format "osm_id_osm_type"
            
        Returns:
            Detailed bench information dictionary
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
            
            data = response.json()
            
            if 'elements' not in data or not data['elements']:
                logger.warning(f"No details found for {osm_type} {osm_id}")
                return {}
            
            return self._parse_bench_element(data['elements'][0]) or {}
            
        except Exception as e:
            logger.error(f"Error getting bench details for provider_id {provider_id}: {e}")
            return {}
