#!/usr/bin/env python3
"""
Test the fixed web server query to make sure it returns results.
"""
import sys
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_fixed_query():
    """Test the fixed query."""
    print("🧪 Testing fixed web server query...")
    
    try:
        from web_server import get_high_confidence_benches
        
        # Test with default parameters
        print("\n1. Testing with default parameters (confidence >= 0.8):")
        result = get_high_confidence_benches(page=0, page_size=10, min_confidence=0.8)
        
        benches = result.get('benches', [])
        pagination = result.get('pagination', {})
        
        print(f"   Found {len(benches)} benches")
        print(f"   Total available: {pagination.get('total_count', 0)}")
        print(f"   Has next page: {pagination.get('has_next', False)}")
        
        if benches:
            bench = benches[0]
            print(f"\n   First bench sample:")
            print(f"     ID: {bench.get('id')}")
            print(f"     Best confidence: {bench.get('best_confidence')}")
            print(f"     Detection type: {bench.get('detection_type')}")
            print(f"     Roboflow confidence: {bench.get('roboflow_confidence')}")
            print(f"     Ultralytics confidence: {bench.get('ultralytics_confidence')}")
            print(f"     Has segmentation: {bench.get('has_segmentation')}")
            print(f"     Image count: {bench.get('image_count')}")
        
        # Test with lower confidence
        print("\n2. Testing with lower confidence (>= 0.5):")
        result2 = get_high_confidence_benches(page=0, page_size=5, min_confidence=0.5)
        benches2 = result2.get('benches', [])
        pagination2 = result2.get('pagination', {})
        print(f"   Found {len(benches2)} benches")
        print(f"   Total available: {pagination2.get('total_count', 0)}")
        
        if len(benches) > 0:
            print("✅ Query is working correctly!")
            return True
        else:
            print("❌ Query returned no results")
            return False
            
    except Exception as e:
        print(f"❌ Error testing query: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_fixed_query()
    sys.exit(0 if success else 1)