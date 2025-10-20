"""
OpenStreetMap Overpass bench generator implementation.
"""

import logging

from clients.overpass_client import OverpassClient

from models.overpass_models import OSMBench

from .bench_generator import BenchCandidate, BenchGenerator


logger = logging.getLogger(__name__)


class OverpassBenchGenerator(BenchGenerator):
    """Bench generator that uses OpenStreetMap data via Overpass API."""

    def __init__(self):
        super().__init__("OpenStreetMap Overpass")
        self.overpass_client = OverpassClient()

    def get_source_identifier(self) -> str:
        return "osm"

    def find_benches_near_point(
        self, lat: float, lng: float, radius: int = 1000
    ) -> list[BenchCandidate]:
        try:
            logger.debug(
                f"Searching OSM for benches near {lat}, {lng} (radius: {radius}m)"
            )
            search_result = self.overpass_client.find_benches_near_point(
                lat, lng, radius
            )

            bench_candidates: list[BenchCandidate] = []
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

        except Exception:
            self._update_stats(success=False)
            logger.exception("OSM bench search failed")
            raise

    def _convert_osm_bench_to_candidate(self, osm_bench: OSMBench) -> BenchCandidate:
        tags_dict = osm_bench.tags.model_dump() if osm_bench.tags else {}
        return BenchCandidate(
            provider_id=osm_bench.provider_id,
            lat=osm_bench.lat,
            lng=osm_bench.lng,
            source=osm_bench.source,
            external_id=osm_bench.external_id,
            tags=tags_dict,
            confidence=None,
        )

    def supports_area_search(self) -> bool:
        return True

    def find_benches_in_area(
        self, min_lng: float, min_lat: float, max_lng: float, max_lat: float, **kwargs
    ) -> list[BenchCandidate]:
        return super().find_benches_in_area(
            min_lng, min_lat, max_lng, max_lat, **kwargs
        )
