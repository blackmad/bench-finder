"""
Abstract base class for bench generators.

This module defines the common interface that all bench finding sources must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from bench_finder.models.enums import DataSource


@dataclass
class BenchCandidate:
    """Represents a bench found by a generator."""

    provider_id: str  # Unique identifier for this bench from this source
    lat: float
    lng: float
    source: DataSource  # Source identifier (e.g., 'osm', 'mapillary')
    external_id: Optional[str] = None  # Original ID from the source system
    tags: dict[str, Any] = None  # Additional metadata/tags
    confidence: Optional[float] = None  # Confidence score if available

    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


@dataclass
class GeneratorStats:
    """Statistics about a generator's usage."""

    name: str
    source: str
    supports_area_search: bool
    total_requests: int = 0
    successful_requests: int = 0
    total_benches_found: int = 0
    last_request_time: Optional[str] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a percentage."""
        return (self.successful_requests / max(self.total_requests, 1)) * 100


class BenchGenerator(ABC):
    """Abstract base class for all bench generators."""

    def __init__(self, name: str):
        """
        Initialize the bench generator.

        Args:
            name: Human-readable name for this generator (e.g., "OpenStreetMap", "Mapillary")
        """
        self.name = name
        self._stats = GeneratorStats(
            name=name,
            source=self.get_source_identifier(),
            supports_area_search=self.supports_area_search(),
        )

    @abstractmethod
    def find_benches_near_point(
        self, lat: float, lng: float, radius: int = 1000
    ) -> list[BenchCandidate]:
        """
        Find all benches within a radius of a given point.

        Args:
            lat: Latitude of the center point
            lng: Longitude of the center point
            radius: Search radius in meters

        Returns:
            List of BenchCandidate objects

        Raises:
            Exception: If the search operation fails
        """

    @abstractmethod
    def get_source_identifier(self) -> DataSource:
        """
        Get the source identifier string for this generator.

        Returns:
            Source identifier (e.g., 'osm', 'mapillary')
        """

    def supports_area_search(self) -> bool:
        """
        Whether this generator supports searching within arbitrary areas.

        Returns:
            True if area search is supported, False otherwise
        """
        return False

    def find_benches_in_area(
        self, min_lng: float, min_lat: float, max_lng: float, max_lat: float, **kwargs
    ) -> list[BenchCandidate]:
        """
        Find benches within a bounding box area.

        Default implementation falls back to point search at bbox center.

        Args:
            min_lng: Minimum longitude
            min_lat: Minimum latitude
            max_lng: Maximum longitude
            max_lat: Maximum latitude
            **kwargs: Additional search parameters

        Returns:
            List of BenchCandidate objects

        Raises:
            NotImplementedError: If area search is not supported and fallback fails
        """
        if not self.supports_area_search():
            # Fallback to point search at center of bounding box
            center_lat = (min_lat + max_lat) / 2
            center_lng = (min_lng + max_lng) / 2

            # Estimate radius from bbox dimensions
            # Simple approximation using degree-to-meter conversion
            lat_diff = max_lat - min_lat
            lng_diff = max_lng - min_lng
            radius = max(lat_diff, lng_diff) * 111000 / 2  # ~111km per degree
            radius = int(min(radius, 5000))  # Cap at 5km

            return self.find_benches_near_point(center_lat, center_lng, radius)
        else:
            raise NotImplementedError("Area search not implemented for this generator")

    def get_stats(self) -> GeneratorStats:
        """
        Get statistics about this generator's usage.

        Returns:
            GeneratorStats object with usage statistics
        """
        return self._stats

    def _update_stats(self, success: bool, bench_count: int = 0):
        """Update internal statistics after a request."""
        self._stats.total_requests += 1
        if success:
            self._stats.successful_requests += 1
            self._stats.total_benches_found += bench_count
        from datetime import datetime

        self._stats.last_request_time = datetime.now().isoformat()
