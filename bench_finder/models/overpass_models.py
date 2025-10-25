"""
Pydantic models for OpenStreetMap Overpass API responses.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import DataSource


class OSMTags(BaseModel):
    """OpenStreetMap tags dictionary."""

    model_config = ConfigDict(extra="allow")  # Allow additional tags

    # Common bench tags
    amenity: str | None = None
    name: str | None = None
    operator: str | None = None
    material: str | None = None
    backrest: str | None = None
    seats: str | None = None
    colour: str | None = None
    access: str | None = None
    shelter: str | None = None
    direction: str | None = None


class OSMGeometryNode(BaseModel):
    """A node in an OSM way geometry."""

    lat: float
    lon: float


class OSMElement(BaseModel):
    """Raw OSM element from Overpass API."""

    type: str = Field(..., description="Element type: node, way, or relation")
    id: int = Field(..., description="OSM element ID")
    lat: float | None = Field(None, description="Latitude (for nodes only)")
    lon: float | None = Field(None, description="Longitude (for nodes only)")
    tags: dict[str, str] | None = Field(default_factory=dict, description="OSM tags")
    geometry: list[OSMGeometryNode] | None = Field(
        None, description="Geometry for ways/relations"
    )


class OSMBench(BaseModel):
    """Parsed bench from OSM data."""

    provider_id: str = Field(..., description="Unique provider ID (osm_id_type)")
    source: DataSource = Field(default=DataSource.OSM, description="Data source")
    external_id: str = Field(..., description="Original OSM ID")
    lat: float = Field(..., description="Bench latitude")
    lng: float = Field(..., description="Bench longitude")
    tags: OSMTags = Field(default_factory=OSMTags, description="OSM tags")
    osm_type: str = Field(..., description="OSM element type (node, way, relation)")
    osm_id: int = Field(..., description="Original OSM element ID")

    @classmethod
    def from_osm_element(cls, element: OSMElement) -> Optional["OSMBench"]:
        """Create OSMBench from raw OSM element."""
        osm_id = element.id
        osm_type = element.type
        tags = OSMTags(**element.tags) if element.tags else OSMTags()

        # Calculate coordinates based on element type
        lat, lng = None, None

        if element.type == "node":
            lat = element.lat
            lng = element.lon

        elif element.type == "way":
            if element.geometry and len(element.geometry) > 0:
                # Calculate centroid
                coords = [(node.lat, node.lon) for node in element.geometry]
                lat = sum(coord[0] for coord in coords) / len(coords)
                lng = sum(coord[1] for coord in coords) / len(coords)
            else:
                return None  # Cannot process way without geometry

        elif element.type == "relation":
            # Skip relations for now as they're complex to handle
            return None

        # Validate coordinates
        if lat is None or lng is None:
            return None

        return cls(
            provider_id=f"{osm_id}_{osm_type}",
            external_id=str(osm_id),
            lat=lat,
            lng=lng,
            tags=tags,
            osm_type=osm_type,
            osm_id=osm_id,
        )


class OverpassResponse(BaseModel):
    """Full Overpass API response."""

    version: float | None = None
    generator: str | None = None
    osm3s: dict[str, Any] | None = None
    elements: list[OSMElement] = Field(default_factory=list, description="OSM elements")


class OverpassSearchResult(BaseModel):
    """Result of an Overpass search operation."""

    benches: list[OSMBench] = Field(default_factory=list, description="Found benches")
    search_center_lat: float = Field(..., description="Search center latitude")
    search_center_lng: float = Field(..., description="Search center longitude")
    search_radius_meters: int = Field(..., description="Search radius in meters")
    total_count: int = Field(..., description="Total number of benches found")

    @property
    def has_benches(self) -> bool:
        """Check if any benches were found."""
        return len(self.benches) > 0
