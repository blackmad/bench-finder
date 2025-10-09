"""
Unified Pydantic models for bench data from different sources.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UnifiedBenchTags(BaseModel):
    """Unified tags for bench data from any source."""

    model_config = ConfigDict(extra="allow")  # Allow additional tags

    # Common tags
    name: Optional[str] = None
    material: Optional[str] = None
    backrest: Optional[str] = None
    seats: Optional[str] = None
    colour: Optional[str] = None
    access: Optional[str] = None
    shelter: Optional[str] = None
    direction: Optional[str] = None
    operator: Optional[str] = None

    # Source-specific tags
    amenity: Optional[str] = None  # OSM specific
    object_value: Optional[str] = None  # Mapillary specific


class UnifiedBench(BaseModel):
    """Unified bench model that can represent data from any source."""

    provider_id: str = Field(..., description="Unique provider ID")
    source: str = Field(..., description="Data source: 'osm', 'mapillary'")
    external_id: str = Field(..., description="External system ID")
    lat: float = Field(..., description="Bench latitude")
    lng: float = Field(..., description="Bench longitude")
    tags: UnifiedBenchTags = Field(
        default_factory=UnifiedBenchTags, description="Bench tags"
    )

    # Additional metadata
    confidence: Optional[float] = Field(
        None, description="Detection confidence if applicable"
    )
    created_at: Optional[datetime] = Field(
        None, description="When this bench was first detected"
    )

    # Source-specific fields
    osm_type: Optional[str] = Field(
        None, description="OSM element type (node, way, relation)"
    )
    osm_id: Optional[int] = Field(None, description="OSM element ID")
    image_id: Optional[str] = Field(None, description="Mapillary image ID")
    detection_id: Optional[str] = Field(None, description="Mapillary detection ID")

    @classmethod
    def from_osm_bench(cls, osm_bench) -> "UnifiedBench":
        """Create UnifiedBench from OSMBench."""
        return cls(
            provider_id=osm_bench.provider_id,
            source="osm",
            external_id=osm_bench.external_id,
            lat=osm_bench.lat,
            lng=osm_bench.lng,
            tags=UnifiedBenchTags(**osm_bench.tags.model_dump()),
            confidence=None,
            created_at=None,
            image_id=None,
            detection_id=None,
            osm_type=osm_bench.osm_type,
            osm_id=osm_bench.osm_id,
        )

    @classmethod
    def from_mapillary_detection(
        cls, detection, image_coords: tuple[float, float]
    ) -> "UnifiedBench":
        """Create UnifiedBench from MapillaryDetection."""
        return cls(
            provider_id=f"mapillary_{detection.detection_id}",
            source="mapillary",
            external_id=detection.detection_id,
            lat=image_coords[1],  # Mapillary uses (lng, lat) format
            lng=image_coords[0],
            tags=UnifiedBenchTags(object_value=detection.value),
            confidence=detection.confidence,
            created_at=detection.created_at,
            image_id=detection.image_id,
            detection_id=detection.detection_id,
            osm_type=None,
            osm_id=None,
        )


class UnifiedSearchResult(BaseModel):
    """Unified search result that can contain benches from any source."""

    benches: list[UnifiedBench] = Field(
        default_factory=list, description="Found benches"
    )
    search_center_lat: float = Field(..., description="Search center latitude")
    search_center_lng: float = Field(..., description="Search center longitude")
    search_radius_meters: int = Field(..., description="Search radius in meters")
    total_count: int = Field(..., description="Total number of benches found")
    source: str = Field(..., description="Data source: 'osm', 'mapillary', 'combined'")

    # Additional metadata
    search_timestamp: datetime = Field(
        default_factory=datetime.now, description="When search was performed"
    )
    processing_time_ms: Optional[float] = Field(
        None, description="Search processing time in milliseconds"
    )

    @property
    def has_benches(self) -> bool:
        """Check if any benches were found."""
        return len(self.benches) > 0

    @property
    def sources_used(self) -> list[str]:
        """Get list of unique sources in the results."""
        return list({bench.source for bench in self.benches})

    def get_benches_by_source(self, source: str) -> list[UnifiedBench]:
        """Get benches from a specific source."""
        return [bench for bench in self.benches if bench.source == source]

    def get_benches_with_confidence(
        self, min_confidence: float = 0.0
    ) -> list[UnifiedBench]:
        """Get benches with confidence above threshold."""
        return [
            bench
            for bench in self.benches
            if bench.confidence is None or bench.confidence >= min_confidence
        ]


class CombinedSearchResult(BaseModel):
    """Result combining searches from multiple sources."""

    osm_result: Optional[UnifiedSearchResult] = Field(
        None, description="OSM search results"
    )
    mapillary_result: Optional[UnifiedSearchResult] = Field(
        None, description="Mapillary search results"
    )
    combined_result: UnifiedSearchResult = Field(
        ..., description="Combined results from all sources"
    )

    # Search metadata
    search_center_lat: float = Field(..., description="Search center latitude")
    search_center_lng: float = Field(..., description="Search center longitude")
    search_radius_meters: int = Field(..., description="Search radius in meters")
    search_timestamp: datetime = Field(
        default_factory=datetime.now, description="When search was performed"
    )

    # Statistics
    total_benches: int = Field(
        ..., description="Total benches found across all sources"
    )
    osm_benches: int = Field(0, description="Number of OSM benches")
    mapillary_benches: int = Field(0, description="Number of Mapillary benches")
    unique_locations: int = Field(0, description="Number of unique bench locations")
    processing_time_ms: Optional[float] = Field(
        None, description="Total processing time in milliseconds"
    )

    @classmethod
    def from_individual_results(
        cls,
        osm_result: Optional[UnifiedSearchResult] = None,
        mapillary_result: Optional[UnifiedSearchResult] = None,
        search_center_lat: float = 0.0,
        search_center_lng: float = 0.0,
        search_radius_meters: int = 1000,
    ) -> "CombinedSearchResult":
        """Create combined result from individual source results."""
        all_benches = []

        if osm_result:
            all_benches.extend(osm_result.benches)

        if mapillary_result:
            all_benches.extend(mapillary_result.benches)

        # Create combined result
        combined_result = UnifiedSearchResult(
            benches=all_benches,
            search_center_lat=search_center_lat,
            search_center_lng=search_center_lng,
            search_radius_meters=search_radius_meters,
            total_count=len(all_benches),
            source="combined",
            processing_time_ms=None,
        )

        # Calculate unique locations (simple coordinate-based deduplication)
        unique_locations = set()
        for bench in all_benches:
            # Round to ~10m precision for deduplication
            lat_rounded = round(bench.lat, 4)
            lng_rounded = round(bench.lng, 4)
            unique_locations.add((lat_rounded, lng_rounded))

        return cls(
            osm_result=osm_result,
            mapillary_result=mapillary_result,
            combined_result=combined_result,
            search_center_lat=search_center_lat,
            search_center_lng=search_center_lng,
            search_radius_meters=search_radius_meters,
            total_benches=len(all_benches),
            osm_benches=len(osm_result.benches) if osm_result else 0,
            mapillary_benches=len(mapillary_result.benches) if mapillary_result else 0,
            unique_locations=len(unique_locations),
            processing_time_ms=None,
        )

    @property
    def has_any_results(self) -> bool:
        """Check if any results were found from any source."""
        return self.total_benches > 0

    @property
    def sources_available(self) -> list[str]:
        """Get list of sources that returned results."""
        sources = []
        if self.osm_result and self.osm_result.has_benches:
            sources.append("osm")
        if self.mapillary_result and self.mapillary_result.has_benches:
            sources.append("mapillary")
        return sources
