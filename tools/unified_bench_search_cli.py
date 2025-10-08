#!/usr/bin/env python3
"""
Unified bench search CLI tool that tests both OSM and Mapillary clients.
"""
import argparse
import logging
import os
import sys
import time
from typing import Optional, Tuple

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bench_finder.clients.overpass_client import OverpassClient
from bench_finder.clients.mapillary_client import MapillaryBenchDetector
from bench_finder.models.unified_models import CombinedSearchResult
from bench_finder.config import SEARCH_RADIUS_METERS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_coordinates(coord_str: str) -> Tuple[float, float]:
    """
    Parse coordinate string in format 'lat,lng' or 'lat lng'.
    
    Args:
        coord_str: Coordinate string
        
    Returns:
        Tuple of (latitude, longitude)
        
    Raises:
        ValueError: If coordinates cannot be parsed
    """
    # Try comma-separated first
    if ',' in coord_str:
        parts = coord_str.split(',')
    else:
        parts = coord_str.split()
    
    if len(parts) != 2:
        raise ValueError(f"Invalid coordinate format: {coord_str}. Expected 'lat,lng' or 'lat lng'")
    
    try:
        lat = float(parts[0].strip())
        lng = float(parts[1].strip())
        return lat, lng
    except ValueError as e:
        raise ValueError(f"Invalid coordinate values: {e}")


def search_with_osm(lat: float, lng: float, radius: int) -> Optional[object]:
    """Search for benches using OSM Overpass API."""
    try:
        logger.info("🔍 Searching OSM Overpass API...")
        start_time = time.time()
        
        client = OverpassClient()
        result = client.search_near_point_unified(lat, lng, radius)
        
        end_time = time.time()
        processing_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        result.processing_time_ms = processing_time
        logger.info(f"✅ OSM search completed in {processing_time:.1f}ms")
        return result
        
    except Exception as e:
        logger.error(f"❌ OSM search failed: {e}")
        return None


def search_with_mapillary(lat: float, lng: float, radius: int, access_token: str) -> Optional[object]:
    """Search for benches using Mapillary API."""
    try:
        logger.info("🔍 Searching Mapillary API...")
        start_time = time.time()
        
        client = MapillaryBenchDetector(access_token)
        result = client.search_near_point_unified(lat, lng, radius)
        
        end_time = time.time()
        processing_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        result.processing_time_ms = processing_time
        logger.info(f"✅ Mapillary search completed in {processing_time:.1f}ms")
        return result
        
    except Exception as e:
        logger.error(f"❌ Mapillary search failed: {e}")
        return None


def print_search_results(combined_result: CombinedSearchResult):
    """Print formatted search results."""
    print("\n" + "="*80)
    print("🎯 UNIFIED BENCH SEARCH RESULTS")
    print("="*80)
    
    # Search metadata
    print(f"📍 Search Center: {combined_result.search_center_lat:.6f}, {combined_result.search_center_lng:.6f}")
    print(f"📏 Search Radius: {combined_result.search_radius_meters:,} meters")
    print(f"🕒 Search Time: {combined_result.search_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Summary statistics
    print(f"\n📊 SUMMARY:")
    print(f"   Total Benches Found: {combined_result.total_benches}")
    print(f"   OSM Benches: {combined_result.osm_benches}")
    print(f"   Mapillary Benches: {combined_result.mapillary_benches}")
    print(f"   Unique Locations: {combined_result.unique_locations}")
    print(f"   Sources Available: {', '.join(combined_result.sources_available)}")
    
    if not combined_result.has_any_results:
        print("\n❌ No benches found in the specified area.")
        return
    
    # Detailed results by source
    if combined_result.osm_result and combined_result.osm_result.has_benches:
        print(f"\n🗺️  OSM OVERPASS RESULTS ({combined_result.osm_benches} benches):")
        print("-" * 60)
        for i, bench in enumerate(combined_result.osm_result.benches[:10], 1):  # Show first 10
            print(f"   {i:2d}. {bench.provider_id} | {bench.lat:.6f}, {bench.lng:.6f}")
            if bench.tags.name:
                print(f"       Name: {bench.tags.name}")
            if bench.tags.material:
                print(f"       Material: {bench.tags.material}")
            if bench.tags.backrest:
                print(f"       Backrest: {bench.tags.backrest}")
            print()
        
        if combined_result.osm_benches > 10:
            print(f"   ... and {combined_result.osm_benches - 10} more OSM benches")
    
    if combined_result.mapillary_result and combined_result.mapillary_result.has_benches:
        print(f"\n📸 MAPILLARY RESULTS ({combined_result.mapillary_benches} detections):")
        print("-" * 60)
        for i, bench in enumerate(combined_result.mapillary_result.benches[:10], 1):  # Show first 10
            print(f"   {i:2d}. {bench.provider_id} | {bench.lat:.6f}, {bench.lng:.6f}")
            if bench.image_id:
                print(f"       Image ID: {bench.image_id}")
            if bench.confidence:
                print(f"       Confidence: {bench.confidence:.2f}")
            print()
        
        if combined_result.mapillary_benches > 10:
            print(f"   ... and {combined_result.mapillary_benches - 10} more Mapillary detections")
    
    # Combined results summary
    print(f"\n🔄 COMBINED RESULTS:")
    print("-" * 60)
    print(f"   Total unique bench locations: {combined_result.unique_locations}")
    print(f"   Data sources: {', '.join(combined_result.sources_available)}")
    
    # Show some combined benches
    if combined_result.combined_result.benches:
        print(f"\n   Sample combined results (first 5):")
        for i, bench in enumerate(combined_result.combined_result.benches[:5], 1):
            print(f"   {i}. [{bench.source.upper()}] {bench.provider_id} | {bench.lat:.6f}, {bench.lng:.6f}")


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Unified bench search tool using OSM and Mapillary APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search with default coordinates (40.74, -74.0 - New York area)
  python unified_bench_search_cli.py

  # Search with custom coordinates
  python unified_bench_search_cli.py --coordinates "40.7589,-73.9851"

  # Search with custom radius
  python unified_bench_search_cli.py --radius 500

  # Search only OSM (no Mapillary token needed)
  python unified_bench_search_cli.py --osm-only

  # Search only Mapillary
  python unified_bench_search_cli.py --mapillary-only --mapillary-token YOUR_TOKEN
        """
    )
    
    parser.add_argument(
        '--coordinates', '-c',
        type=str,
        default='40.74,-74.0',
        help='Search center coordinates as "lat,lng" (default: 40.74,-74.0)'
    )
    
    parser.add_argument(
        '--radius', '-r',
        type=int,
        default=SEARCH_RADIUS_METERS,
        help=f'Search radius in meters (default: {SEARCH_RADIUS_METERS})'
    )
    
    parser.add_argument(
        '--mapillary-token', '-t',
        type=str,
        help='Mapillary API access token (can also be set via MAPILLARY_ACCESS_TOKEN env var)'
    )
    
    parser.add_argument(
        '--osm-only',
        action='store_true',
        help='Search only OSM Overpass API'
    )
    
    parser.add_argument(
        '--mapillary-only',
        action='store_true',
        help='Search only Mapillary API'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Parse coordinates
    try:
        lat, lng = parse_coordinates(args.coordinates)
        logger.info(f"Search coordinates: {lat:.6f}, {lng:.6f}")
    except ValueError as e:
        logger.error(f"Invalid coordinates: {e}")
        sys.exit(1)
    
    # Get Mapillary token
    mapillary_token = args.mapillary_token or os.getenv('MAPILLARY_ACCESS_TOKEN')
    
    # Determine which searches to perform
    search_osm = not args.mapillary_only
    search_mapillary = not args.osm_only and mapillary_token is not None
    
    if not search_osm and not search_mapillary:
        logger.error("No search methods available. Either provide --mapillary-token or use --osm-only")
        sys.exit(1)
    
    if search_mapillary and not mapillary_token:
        logger.warning("Mapillary token not provided. Skipping Mapillary search.")
        logger.info("Set MAPILLARY_ACCESS_TOKEN environment variable or use --mapillary-token")
        search_mapillary = False
    
    # Perform searches
    logger.info(f"Starting unified bench search...")
    logger.info(f"Search center: {lat:.6f}, {lng:.6f}")
    logger.info(f"Search radius: {args.radius:,} meters")
    logger.info(f"Search methods: OSM={search_osm}, Mapillary={search_mapillary}")
    
    osm_result = None
    mapillary_result = None
    
    if search_osm:
        osm_result = search_with_osm(lat, lng, args.radius)
    
    if search_mapillary:
        mapillary_result = search_with_mapillary(lat, lng, args.radius, mapillary_token)
    
    # Create combined result
    combined_result = CombinedSearchResult.from_individual_results(
        osm_result=osm_result,
        mapillary_result=mapillary_result,
        search_center_lat=lat,
        search_center_lng=lng,
        search_radius_meters=args.radius
    )
    
    # Print results
    print_search_results(combined_result)
    
    # Exit with appropriate code
    if combined_result.has_any_results:
        logger.info("✅ Search completed successfully with results")
        sys.exit(0)
    else:
        logger.info("ℹ️  Search completed but no benches found")
        sys.exit(1)


if __name__ == '__main__':
    main()
