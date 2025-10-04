#!/usr/bin/env python3
"""
CLI tool for testing Mapillary bench detection functionality.
"""
import os
import sys
import argparse
import logging
import math
from typing import Optional, List, Tuple, Set

from mapillary_service import create_mapillary_service
from config import DATABASE_PATH
from schemas import BenchListResponse, WebBenchData, PaginationInfo

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def calculate_grid_points(
    center_lat: float, 
    center_lng: float, 
    total_radius: int, 
    sub_radius: int = 100
) -> List[Tuple[float, float]]:
    """
    Calculate grid points for overlapping circular searches.
    
    Args:
        center_lat: Center latitude
        center_lng: Center longitude
        total_radius: Total radius to cover in meters
        sub_radius: Radius of each sub-search in meters (default 100m)
        
    Returns:
        List of (lat, lng) tuples for search centers
    """
    if total_radius <= sub_radius:
        return [(center_lat, center_lng)]
    
    # Calculate spacing between grid points
    # Use 70% of sub_radius to ensure good overlap
    spacing_meters = sub_radius * 0.7
    
    # Convert to degrees (approximate)
    # 1 degree latitude ≈ 111,000 meters
    # 1 degree longitude varies with latitude: cos(lat) * 111,000 meters
    lat_spacing = spacing_meters / 111000
    lng_spacing = spacing_meters / (111000 * math.cos(math.radians(center_lat)))
    
    # Calculate grid bounds
    total_radius_deg_lat = total_radius / 111000
    total_radius_deg_lng = total_radius / (111000 * math.cos(math.radians(center_lat)))
    
    # Generate grid points
    grid_points = []
    
    # Start from the southwest corner and work our way across
    lat_steps = int(math.ceil(2 * total_radius_deg_lat / lat_spacing)) + 1
    lng_steps = int(math.ceil(2 * total_radius_deg_lng / lng_spacing)) + 1
    
    for i in range(lat_steps):
        for j in range(lng_steps):
            point_lat = center_lat - total_radius_deg_lat + (i * lat_spacing)
            point_lng = center_lng - total_radius_deg_lng + (j * lng_spacing)
            
            # Only include points within the total radius
            distance = calculate_distance_meters(center_lat, center_lng, point_lat, point_lng)
            if distance <= total_radius:
                grid_points.append((point_lat, point_lng))
    
    # Always include the original center point
    if (center_lat, center_lng) not in grid_points:
        grid_points.append((center_lat, center_lng))
    
    logger.info(f"Generated {len(grid_points)} grid points to cover {total_radius}m radius")
    return grid_points


def calculate_distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate distance between two points using Haversine formula.
    
    Returns distance in meters.
    """
    # Convert decimal degrees to radians
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth's radius in meters
    r = 6371000
    return c * r


def merge_search_results(
    results: List[BenchListResponse],
    original_center_lat: float,
    original_center_lng: float
) -> BenchListResponse:
    """
    Merge multiple search results, removing duplicates and recalculating distances.
    
    Args:
        results: List of BenchListResponse objects to merge
        original_center_lat: Original search center latitude
        original_center_lng: Original search center longitude
        
    Returns:
        Merged BenchListResponse
    """
    seen_bench_ids: Set[int] = set()
    merged_benches: List[WebBenchData] = []
    total_images = 0
    total_detections = 0
    
    for result in results:
        total_images += result.pagination.total_count
        
        for bench in result.benches:
            # Avoid duplicates based on bench ID
            if bench.id not in seen_bench_ids:
                seen_bench_ids.add(bench.id)
                
                # Recalculate distance from original center
                distance = calculate_distance_meters(
                    original_center_lat, original_center_lng, bench.lat, bench.lng
                )
                
                # Create updated bench with correct distance
                updated_bench = WebBenchData(
                    id=bench.id,
                    osm_id=bench.osm_id,
                    osm_type=bench.osm_type,
                    lat=bench.lat,
                    lng=bench.lng,
                    tags=bench.tags,
                    source=bench.source,
                    external_id=bench.external_id,
                    best_confidence=bench.best_confidence,
                    roboflow_confidence=bench.roboflow_confidence,
                    ultralytics_confidence=bench.ultralytics_confidence,
                    mapillary_confidence=bench.mapillary_confidence,
                    detection_type=bench.detection_type,
                    has_segmentation=bench.has_segmentation,
                    image_count=bench.image_count,
                    image_filenames=bench.image_filenames,
                    image_ids=bench.image_ids,
                    distance_meters=round(distance),
                    distance_km=round(distance / 1000, 2)
                )
                merged_benches.append(updated_bench)
                total_detections += bench.image_count
    
    # Sort by distance from original center
    merged_benches.sort(key=lambda b: b.distance_meters)
    
    # Create merged pagination info
    pagination = PaginationInfo(
        page=0,
        page_size=len(merged_benches),
        total_count=len(merged_benches),
        total_pages=1,
        has_next=False
    )
    
    return BenchListResponse(
        benches=merged_benches,
        pagination=pagination
    )


def test_mapillary_search(
    access_token: str,
    lat: float,
    lng: float,
    radius: int = 1000,
    limit: int = 100
):
    """Test Mapillary bench search functionality."""
    print(f"\n🔍 Testing Mapillary Bench Detection")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📍 Location: {lat}, {lng}")
    print(f"📏 Radius: {radius}m")
    print(f"📊 Limit: {limit} images per sub-search")
    
    try:
        # Create service
        service = create_mapillary_service(DATABASE_PATH, access_token)
        print(f"✅ Mapillary service initialized")
        
        # Check if we need to use grid sampling
        grid_points = None
        if radius > 100:
            print(f"\n🌐 Large radius detected ({radius}m > 100m)")
            print(f"🔄 Using grid sampling with overlapping 100m sub-searches...")
            
            # Calculate grid points for sub-searches
            grid_points = calculate_grid_points(lat, lng, radius, sub_radius=100)
            print(f"📍 Generated {len(grid_points)} search points")
            
            # Perform searches at each grid point
            search_results = []
            for i, (grid_lat, grid_lng) in enumerate(grid_points, 1):
                print(f"\n🔍 Sub-search {i}/{len(grid_points)} at ({grid_lat:.6f}, {grid_lng:.6f})")
                
                try:
                    sub_result = service.search_and_store_benches(
                        center_lat=grid_lat,
                        center_lng=grid_lng,
                        radius_meters=100,  # Always use 100m for sub-searches
                        limit=limit
                    )
                    search_results.append(sub_result)
                    print(f"   Found {len(sub_result.benches)} benches")
                    
                except Exception as e:
                    logger.warning(f"Sub-search {i} failed: {e}")
                    continue
            
            # Merge all results
            print(f"\n🔗 Merging results from {len(search_results)} successful searches...")
            result = merge_search_results(search_results, lat, lng)
            print(f"✅ Merged to {len(result.benches)} unique benches")
            
        else:
            # Single search for radius <= 100m
            print(f"\n🚀 Single search (radius <= 100m)...")
            result = service.search_and_store_benches(
                center_lat=lat,
                center_lng=lng,
                radius_meters=radius,
                limit=limit
            )
        
        print(f"\n📊 Search Results:")
        print(f"   Benches found: {len(result.benches)}")
        if result.benches:
            total_detections = sum(bench.image_count for bench in result.benches)
            print(f"   Total detections: {total_detections}")
            print(f"   Avg detections per bench: {total_detections / len(result.benches):.2f}")
        
        # Show some example benches
        if result.benches:
            print(f"\n🏗️  Sample Benches:")
            for i, bench in enumerate(result.benches[:3], 1):
                print(f"   {i}. Bench {bench.id} (Source: {bench.source})")
                print(f"      Location: {bench.lat:.6f}, {bench.lng:.6f}")
                print(f"      Distance: {bench.distance_meters}m from center")
                print(f"      Confidence: {bench.best_confidence:.3f} ({bench.detection_type})")
                if bench.external_id:
                    print(f"      External ID: {bench.external_id}")
                print(f"      Images: {bench.image_count}")
        
        # Get statistics
        print(f"\n📈 Getting Statistics...")
        stats = service.get_detection_statistics(lat, lng, radius)
        print(f"   Stored benches: {stats.total_benches}")
        print(f"   Stored detections: {stats.total_detections}")
        print(f"   Unique locations: {stats.unique_locations}")
        print(f"   Coverage area: {stats.coverage_area_km2:.3f} km²")
        print(f"   Avg detections per bench: {stats.avg_detections_per_bench:.2f}")
        
        # Test stored retrieval
        print(f"\n💾 Testing stored data retrieval...")
        retrieval_limit = limit * len(grid_points) if grid_points else limit
        stored_benches = service.get_stored_benches(lat, lng, radius, retrieval_limit)
        print(f"   Retrieved {len(stored_benches)} benches from database")
        
        # Show coverage summary for large radius searches
        if radius > 100 and result.benches:
            distances = [bench.distance_meters for bench in result.benches]
            print(f"\n🔍 Coverage Analysis:")
            print(f"   Closest bench: {min(distances)}m from center")
            print(f"   Furthest bench: {max(distances)}m from center")
            print(f"   Average distance: {sum(distances) / len(distances):.1f}m")
            in_radius = sum(1 for d in distances if d <= radius)
            print(f"   Benches within target radius: {in_radius}/{len(distances)} ({in_radius/len(distances)*100:.1f}%)")
        
        print(f"\n✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.error(f"Test error: {e}", exc_info=True)
        return False


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description='Test Mapillary bench detection')
    parser.add_argument('--token', '-t', required=True, help='Mapillary access token')
    parser.add_argument('--lat', type=float, required=True, help='Latitude')
    parser.add_argument('--lng', type=float, required=True, help='Longitude') 
    parser.add_argument('--radius', type=int, default=1000, help='Search radius in meters (default: 1000)')
    parser.add_argument('--limit', type=int, default=100, help='Max images to fetch (default: 100)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Test the functionality
    success = test_mapillary_search(
        access_token=args.token,
        lat=args.lat,
        lng=args.lng,
        radius=args.radius,
        limit=args.limit
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()