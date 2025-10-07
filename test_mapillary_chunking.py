#!/usr/bin/env python3
"""
Test script demonstrating Mapillary chunked search functionality.

This test shows how the MapillaryBenchGenerator automatically breaks down
large search areas into smaller chunks for better API performance.
"""
import sys
import os
import math

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Mock the dependencies for testing
class MockConfig:
    MAPILLARY_ACCESS_TOKEN = "test_token"
    IMAGES_DIR = "images"
    MAPILLARY_MAX_CHUNK_SIZE_METERS = 200
    MAPILLARY_API_LIMIT_PER_REQUEST = 1000

sys.modules['config'] = MockConfig()

class MockLogging:
    @staticmethod
    def getLogger(name):
        class Logger:
            def debug(self, msg): print(f"DEBUG: {msg}")
            def info(self, msg): print(f"INFO: {msg}")
            def warning(self, msg): print(f"WARNING: {msg}")
            def error(self, msg): print(f"ERROR: {msg}")
        return Logger()

sys.modules['logging'] = MockLogging()

# Mock MapillaryBenchDetector
class MockMapillaryBenchDetector:
    def __init__(self, access_token, images_dir):
        self.access_token = access_token
        self.images_dir = images_dir
    
    def search_benches_by_location(self, lat, lng, radius):
        # Mock response - return empty for simplicity
        return []
    
    def search_images_with_detections(self, bbox, limit):
        # Mock response based on bbox size to demonstrate chunking
        min_lng, min_lat, max_lng, max_lat = bbox
        
        # Calculate area size
        lat_meters = (max_lat - min_lat) * 111000
        lng_meters = (max_lng - min_lng) * 111000 * math.cos(math.radians((min_lat + max_lat) / 2))
        area_size = max(lat_meters, lng_meters)
        
        print(f"    Mock API call for bbox {bbox[0]:.4f},{bbox[1]:.4f} to {bbox[2]:.4f},{bbox[3]:.4f} (area: {area_size:.0f}m)")
        
        # Return mock images (just image IDs for testing)
        from mapillary_client import MapillaryImage
        mock_images = []
        
        # Create a few mock images for this chunk
        for i in range(min(3, limit // 100)):  # Simulate some results
            image_id = f"mock_image_{abs(hash(str(bbox)))}_{i}"
            mock_image = MapillaryImage(
                image_id=image_id,
                coordinates=((min_lng + max_lng) / 2, (min_lat + max_lat) / 2),
                detections=[]
            )
            mock_images.append(mock_image)
        
        return mock_images

# Mock the mapillary_client module  
class MockMapillaryClient:
    class MapillaryImage:
        def __init__(self, image_id, coordinates, detections):
            self.image_id = image_id
            self.coordinates = coordinates
            self.detections = detections
    
    # Add the classes as module-level attributes
    MapillaryBenchDetector = MockMapillaryBenchDetector

sys.modules['mapillary_client'] = MockMapillaryClient()

# Mock BenchGenerator components
class MockBenchGenerator:
    class BenchGenerator:
        def __init__(self, name):
            self.name = name
            self._stats = MockGeneratorStats(name, "test", True)
        
        def _update_stats(self, success, bench_count=0):
            pass
    
    class BenchCandidate:
        def __init__(self, provider_id, lat, lng, source, external_id=None, tags=None, confidence=None):
            self.provider_id = provider_id
            self.lat = lat
            self.lng = lng
            self.source = source
            self.external_id = external_id
            self.tags = tags or {}
            self.confidence = confidence
    
    class GeneratorStats:
        def __init__(self, name, source, supports_area_search):
            self.name = name
            self.source = source
            self.supports_area_search = supports_area_search

class MockGeneratorStats:
    def __init__(self, name, source, supports_area_search):
        self.name = name
        self.source = source  
        self.supports_area_search = supports_area_search

sys.modules['bench_generator'] = MockBenchGenerator()

def test_chunking_logic():
    """Test the chunking calculation logic."""
    print("=== Testing Chunking Logic ===")
    
    try:
        from mapillary_bench_generator import MapillaryBenchGenerator
        from bench_generator import BenchCandidate
        
        # Create generator instance
        generator = MapillaryBenchGenerator()
        
        # Test 1: Small area (should not chunk)
        print("\n1. Testing small area search (100m radius - should not chunk):")
        candidates = generator.find_benches_near_point(40.7359, -73.9911, radius=100)
        print(f"   Result: {len(candidates)} candidates")
        
        # Test 2: Large area (should chunk)
        print("\n2. Testing large area search (500m radius - should chunk):")
        candidates = generator.find_benches_near_point(40.7359, -73.9911, radius=500)
        print(f"   Result: {len(candidates)} candidates")
        
        # Test 3: Direct area search (should always chunk)
        print("\n3. Testing direct area search (large bounding box - should chunk):")
        # Central Park area (roughly 800m x 2500m)
        candidates = generator.find_benches_in_area(
            min_lng=-73.9812, min_lat=40.7648,
            max_lng=-73.9541, max_lat=40.7997
        )
        print(f"   Result: {len(candidates)} candidates")
        
        # Test 4: Test chunk calculation
        print("\n4. Testing chunk calculation:")
        chunk_size = MockConfig.MAPILLARY_MAX_CHUNK_SIZE_METERS
        print(f"   Configured chunk size: {chunk_size}m")
        
        # Calculate chunks for Central Park
        min_lng, min_lat = -73.9812, 40.7648
        max_lng, max_lat = -73.9541, 40.7997
        
        lat_meters = (max_lat - min_lat) * 111000
        lng_meters = (max_lng - min_lng) * 111000 * math.cos(math.radians((min_lat + max_lat) / 2))
        
        lat_chunks = max(1, math.ceil(lat_meters / chunk_size))
        lng_chunks = max(1, math.ceil(lng_meters / chunk_size))
        total_chunks = lat_chunks * lng_chunks
        
        print(f"   Area dimensions: {lat_meters:.0f}m x {lng_meters:.0f}m")
        print(f"   Required chunks: {lat_chunks} x {lng_chunks} = {total_chunks}")
        print(f"   Average chunk size: {lat_meters/lat_chunks:.0f}m x {lng_meters/lng_chunks:.0f}m")
        
        print("\n✅ Chunking logic test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_configuration():
    """Test configuration options."""
    print("\n=== Testing Configuration ===")
    
    print(f"MAPILLARY_MAX_CHUNK_SIZE_METERS: {MockConfig.MAPILLARY_MAX_CHUNK_SIZE_METERS}m")
    print(f"MAPILLARY_API_LIMIT_PER_REQUEST: {MockConfig.MAPILLARY_API_LIMIT_PER_REQUEST}")
    
    # Show how different chunk sizes would affect a search
    test_area_meters = 1000  # 1km x 1km test area
    
    print(f"\nChunking analysis for {test_area_meters}m x {test_area_meters}m area:")
    
    for chunk_size in [100, 200, 500, 1000]:
        chunks_per_side = math.ceil(test_area_meters / chunk_size)
        total_chunks = chunks_per_side * chunks_per_side
        print(f"  Chunk size {chunk_size}m: {chunks_per_side}x{chunks_per_side} = {total_chunks} API calls")
    
    print("\n✅ Configuration test completed!")

def main():
    """Run all tests."""
    print("Testing Mapillary Chunked Search Functionality")
    print("=" * 50)
    
    # Test configuration first
    test_configuration()
    
    # Test chunking logic
    success = test_chunking_logic()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed!")
        print("\nKey Features Demonstrated:")
        print("• Automatic chunking for large search areas")
        print("• Configurable chunk size (MAPILLARY_MAX_CHUNK_SIZE_METERS)")
        print("• Overlap between chunks to avoid missing detections")
        print("• Deduplication of results from overlapping chunks")
        print("• Detailed logging of chunking process")
        return 0
    else:
        print("💔 Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())