"""
Base class for location-based search clients.
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LocationSearchResult(BaseModel):
    """Base class for location-based search results."""
    search_center_lat: float
    search_center_lng: float
    search_radius_meters: int
    total_count: int
    
    @property
    def has_results(self) -> bool:
        """Check if any results were found."""
        return self.total_count > 0


class BaseLocationClient(ABC):
    """Base class for location-based search clients."""
    
    def __init__(self, name: str):
        """
        Initialize the base client.
        
        Args:
            name: Client name for logging
        """
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    def search_near_point(
        self, 
        lat: float, 
        lng: float, 
        radius: int = 1000
    ) -> LocationSearchResult:
        """
        Search for items near a given point.
        
        Args:
            lat: Latitude of the center point
            lng: Longitude of the center point
            radius: Search radius in meters
            
        Returns:
            LocationSearchResult with found items
        """
        pass
    
    @abstractmethod
    def get_item_details(self, provider_id: str) -> Optional[dict]:
        """
        Get detailed information about a specific item.
        
        Args:
            provider_id: Provider-specific ID
            
        Returns:
            Dictionary with item details or None if not found
        """
        pass
    
    def validate_coordinates(self, lat: float, lng: float) -> bool:
        """
        Validate that coordinates are within valid ranges.
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            True if coordinates are valid
        """
        return -90 <= lat <= 90 and -180 <= lng <= 180
    
    def calculate_distance_meters(
        self, 
        lat1: float, 
        lng1: float, 
        lat2: float, 
        lng2: float
    ) -> float:
        """
        Calculate distance between two points in meters using Haversine formula.
        
        Args:
            lat1, lng1: First point coordinates
            lat2, lng2: Second point coordinates
            
        Returns:
            Distance in meters
        """
        import math
        
        # Convert to radians
        lat1_rad = math.radians(lat1)
        lng1_rad = math.radians(lng1)
        lat2_rad = math.radians(lat2)
        lng2_rad = math.radians(lng2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlng = lng2_rad - lng1_rad
        
        a = (math.sin(dlat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth's radius in meters
        earth_radius = 6371000
        
        return earth_radius * c
