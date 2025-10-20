#!/usr/bin/env python3
"""
Test script for the refactored bench finder with multiple generators.

This script tests that both OSM and Mapillary generators work correctly together.
"""

import logging
import sys

from config import MAPILLARY_ACCESS_TOKEN
from mapillary_bench_generator import MapillaryBenchGenerator
from overpass_bench_generator import OverpassBenchGenerator


# Setup basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_osm_generator():
    """Test the OpenStreetMap generator."""
    logger.info("Testing OSM generator...")

    try:
        generator = OverpassBenchGenerator()
        logger.info(f"Created OSM generator: {generator.name}")

        # Test with a location that should have benches (Union Square, NYC)
        test_lat, test_lng = 40.7359, -73.9911
        radius = 200  # Small radius for quick test

        logger.info(
            f"Searching for benches near {test_lat}, {test_lng} (radius: {radius}m)"
        )
        candidates = generator.find_benches_near_point(test_lat, test_lng, radius)

        logger.info(f"OSM generator found {len(candidates)} bench candidates")

        # Print first few candidates
        for i, candidate in enumerate(candidates[:3]):
            logger.info(
                f"  {i+1}. {candidate.provider_id} at ({candidate.lat}, {candidate.lng}) - source: {candidate.source}"
            )

        # Check generator stats
        stats = generator.get_stats()
        logger.info(
            f"OSM generator stats: {stats.total_requests} requests, {stats.success_rate:.1f}% success"
        )

        return len(candidates) > 0

    except Exception:
        logger.exception("OSM generator test failed")
        return False


def test_mapillary_generator():
    """Test the Mapillary generator."""
    logger.info("Testing Mapillary generator...")

    if not MAPILLARY_ACCESS_TOKEN:
        logger.warning("MAPILLARY_ACCESS_TOKEN not set - skipping Mapillary test")
        return True  # Consider this a pass since it's optional

    try:
        generator = MapillaryBenchGenerator()
        logger.info(f"Created Mapillary generator: {generator.name}")

        # Test with a location that might have Mapillary bench detections
        # Using Central Park, NYC - popular area with good Mapillary coverage
        test_lat, test_lng = 40.7812, -73.9665
        radius = 500  # Larger radius since Mapillary data might be sparser

        logger.info(
            f"Searching for benches near {test_lat}, {test_lng} (radius: {radius}m)"
        )
        candidates = generator.find_benches_near_point(test_lat, test_lng, radius)

        logger.info(f"Mapillary generator found {len(candidates)} bench candidates")

        # Print first few candidates
        for i, candidate in enumerate(candidates[:3]):
            logger.info(
                f"  {i+1}. {candidate.provider_id} at ({candidate.lat}, {candidate.lng}) - source: {candidate.source}, confidence: {candidate.confidence}"
            )

        # Check generator stats
        stats = generator.get_stats()
        logger.info(
            f"Mapillary generator stats: {stats.total_requests} requests, {stats.success_rate:.1f}% success"
        )

        return True  # Pass even if no candidates found (Mapillary data might be sparse)

    except Exception:
        logger.exception("Mapillary generator test failed")
        return False


def test_combined_generators():
    """Test using both generators together."""
    logger.info("Testing combined generators...")

    try:
        generators = []

        # Add OSM generator
        try:
            osm_gen = OverpassBenchGenerator()
            generators.append(osm_gen)
            logger.info("Added OSM generator")
        except Exception:
            logger.exception("Failed to add OSM generator")

        # Add Mapillary generator if available
        try:
            if MAPILLARY_ACCESS_TOKEN:
                mapillary_gen = MapillaryBenchGenerator()
                generators.append(mapillary_gen)
                logger.info("Added Mapillary generator")
            else:
                logger.info("Skipping Mapillary generator (no token)")
        except Exception as e:
            logger.warning(f"Failed to add Mapillary generator: {e}")

        if not generators:
            logger.error("No generators available for testing")
            return False

        # Test location: Washington Square Park, NYC
        test_lat, test_lng = 40.7308, -73.9973
        radius = 300

        logger.info(
            f"Testing {len(generators)} generators at {test_lat}, {test_lng} (radius: {radius}m)"
        )

        all_candidates = []
        generator_results = {}

        for generator in generators:
            try:
                candidates = generator.find_benches_near_point(
                    test_lat, test_lng, radius
                )
                all_candidates.extend(candidates)
                generator_results[generator.name] = len(candidates)
                logger.info(f"{generator.name}: {len(candidates)} candidates")
            except Exception:
                logger.exception(f"Error with {generator.name}")
                generator_results[generator.name] = 0

        logger.info(f"Total candidates from all generators: {len(all_candidates)}")
        logger.info(f"Generator breakdown: {generator_results}")

        # Test deduplication logic (simulate what BenchFinder does)
        if len(all_candidates) > 1:
            from bench_finder import BenchFinder

            finder = BenchFinder()
            unique_candidates = finder._deduplicate_bench_candidates(all_candidates)
            logger.info(
                f"After deduplication: {len(unique_candidates)} unique candidates"
            )

        return len(all_candidates) > 0

    except Exception:
        logger.exception("Combined generators test failed")
        return False


def main():
    """Run all tests."""
    logger.info("Starting generator tests...")

    tests = [
        ("OSM Generator", test_osm_generator),
        ("Mapillary Generator", test_mapillary_generator),
        ("Combined Generators", test_combined_generators),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        logger.info(f"\n--- Running {test_name} Test ---")
        try:
            if test_func():
                logger.info(f"✅ {test_name} test passed")
                passed += 1
            else:
                logger.error(f"❌ {test_name} test failed")
        except Exception:
            logger.exception(f"💥 {test_name} test crashed")

    logger.info("\n--- Test Results ---")
    logger.info(f"Passed: {passed}/{total} tests")

    if passed == total:
        logger.info("🎉 All tests passed!")
        return 0
    else:
        logger.error(f"💔 {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
