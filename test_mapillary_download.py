#!/usr/bin/env python3
"""
Test script for Mapillary bench detection with image downloading.
"""

import os
import logging
from config import MAPILLARY_ACCESS_TOKEN, DATABASE_PATH, IMAGES_DIR
from mapillary_service import MapillaryBenchService

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_mapillary_download():
    """Test Mapillary bench detection with image downloading."""
    
    if not MAPILLARY_ACCESS_TOKEN:
        print("❌ MAPILLARY_ACCESS_TOKEN not set in environment variables")
        print("Please set your Mapillary access token:")
        print("export MAPILLARY_ACCESS_TOKEN='your_token_here'")
        return False
    
    # Test coordinates (Amsterdam, Netherlands - should have bench data)
    test_lat = 52.3613577
    test_lng = 4.8666322
    radius = 500  # 500 meters
    
    print("🔍 Testing Mapillary bench detection with image downloading...")
    print(f"📍 Location: {test_lat}, {test_lng}")
    print(f"🎯 Radius: {radius}m")
    print(f"💾 Database: {DATABASE_PATH}")
    print(f"📁 Images directory: {IMAGES_DIR}")
    print()
    
    try:
        # Initialize Mapillary service
        service = MapillaryBenchService(DATABASE_PATH, MAPILLARY_ACCESS_TOKEN, IMAGES_DIR)
        print("✅ Mapillary service initialized successfully")
        
        # Search for benches and download images
        print(f"\n🔍 Searching for benches around {test_lat}, {test_lng}...")
        result = service.search_and_store_benches(
            center_lat=test_lat,
            center_lng=test_lng,
            radius_meters=radius,
            limit=10  # Limit to 10 for testing
        )
        
        print(f"\n📊 Results:")
        print(f"   Found {len(result.benches)} bench detections")
        print(f"   Total pages: {result.pagination.total_pages}")
        print(f"   Total count: {result.pagination.total_count}")
        
        # Show details of found benches
        if result.benches:
            print(f"\n🪑 Bench Details:")
            for i, bench in enumerate(result.benches[:5]):  # Show first 5
                print(f"   {i+1}. ID: {bench.id}")
                print(f"      Provider ID: {bench.provider_id}")
                print(f"      Location: {bench.lat:.6f}, {bench.lng:.6f}")
                print(f"      Source: {bench.source}")
                print(f"      Confidence: {bench.best_confidence}")
                print(f"      Images: {bench.image_count}")
                if bench.image_filenames:
                    print(f"      Image files: {', '.join(bench.image_filenames)}")
                print(f"      Distance: {bench.distance_meters}m")
                print()
        
        # Check downloaded images
        if os.path.exists(IMAGES_DIR):
            image_files = [f for f in os.listdir(IMAGES_DIR) if f.startswith('mapillary_')]
            print(f"📷 Downloaded {len(image_files)} Mapillary images to {IMAGES_DIR}")
            if image_files[:3]:  # Show first 3 filenames
                print(f"   Sample files: {', '.join(image_files[:3])}")
        
        print("\n✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        logger.exception("Detailed error:")
        return False

def main():
    """Main function."""
    print("Mapillary Bench Detection with Image Download Test")
    print("=" * 50)
    
    success = test_mapillary_download()
    
    if success:
        print("\n🎉 All tests passed!")
    else:
        print("\n💥 Some tests failed!")
    
    return success

if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)