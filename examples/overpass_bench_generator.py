"""
OpenStreetMap Overpass bench generator implementation.

This module provides a BenchGenerator implementation that uses the existing
OverpassClient to find benches from OpenStreetMap data.
"""
import logging
from typing import List
from .bench_generator import BenchGenerator, BenchCandidate
from bench_finder.clients.overpass_client import OverpassClient

logger = logging.getLogger(__name__)


class OverpassBenchGenerator(BenchGenerator):
    """Bench generator that uses OpenStreetMap data via Overpass API."""
    
    def __init__(self):
        """Initialize the Overpass bench generator."""
        super().__init__("OpenStreetMap Overpass")
        self.overpass_client = OverpassClient()
    
    def get_source_identifier(self) -> str:
        """Get the source identifier for OSM data."""
        return "osm"
    
    def find_benches_near_point(
        self, 
        lat: float, 
        lng: float, 
        radius: int = 1000
    ) -> List[BenchCandidate]:
        """
        Find benches from OSM data near a point.
        
        Args:
            lat: Latitude of the center point
            lng: Longitude of the center point  
            radius: Search radius in meters
            
        Returns:
            List of BenchCandidate objects from OSM data
            
        Raises:
            Exception: If the Overpass API call fails
        """
        try:
            logger.debug(f"Searching OSM for benches near {lat}, {lng} (radius: {radius}m)")
            
            # Use existing OverpassClient to get search result
            search_result = self.overpass_client.find_benches_near_point(lat, lng, radius)
            
            # Convert OSMBench objects to BenchCandidate objects
            bench_candidates = []
            for osm_bench in search_result.benches:
                try:
                    candidate = self._convert_osm_bench_to_candidate(osm_bench)
                    if candidate:
                        bench_candidates.append(candidate)
                except Exception as e:
                    logger.warning(f"Failed to convert OSM bench to candidate: {e}")
                    continue
            
            self._update_stats(success=True, bench_count=len(bench_candidates))
            logger.info(f"Found {len(bench_candidates)} OSM benches")
            return bench_candidates
            
        except Exception as e:
            self._update_stats(success=False)
            logger.error(f"OSM bench search failed: {e}")
            raise
    
    def _convert_osm_bench_to_candidate(self, osm_bench) -> BenchCandidate:
        """
        Convert an OSMBench object to a BenchCandidate.
        
        Args:
            osm_bench: OSMBench object from OverpassClient
            
        Returns:
            BenchCandidate object
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        from bench_finder.models.overpass_models import OSMBench
        
        if not isinstance(osm_bench, OSMBench):
            raise ValueError(f"Expected OSMBench object, got {type(osm_bench)}")
        
        # Convert OSMTags to regular dict
        tags_dict = osm_bench.tags.model_dump() if osm_bench.tags else {}
        
        return BenchCandidate(
            provider_id=osm_bench.provider_id,
            lat=osm_bench.lat,
            lng=osm_bench.lng,
            source=osm_bench.source,
            external_id=osm_bench.external_id,
            tags=tags_dict,
            confidence=None  # OSM doesn't provide confidence scores
        )
    
    def supports_area_search(self) -> bool:
        """OSM supports efficient area-based searches."""
        return True
    
    def find_benches_in_area(
        self,
        min_lng: float,
        min_lat: float, 
        max_lng: float,
        max_lat: float,
        **kwargs
    ) -> List[BenchCandidate]:
        """
        Find benches within a bounding box using OSM data.
        
        For now, this falls back to the point search at center.
        Could be extended to use Overpass bbox queries directly.
        
        Args:
            min_lng: Minimum longitude
            min_lat: Minimum latitude
            max_lng: Maximum longitude
            max_lat: Maximum latitude
            **kwargs: Additional search parameters
            
        Returns:
            List of BenchCandidate objects
        """
        # Use the base class implementation which does center point search
        return super().find_benches_in_area(min_lng, min_lat, max_lng, max_lat, **kwargs)