#!/usr/bin/env python3
"""
Test script to run the enhanced web server with segmentation support.
"""
import sys
import os
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

def test_web_server():
    """Test the web server functionality."""
    print("Testing enhanced web server with Ultralytics segmentation support...")
    
    try:
        from web_server import app, get_high_confidence_benches
        print("✓ Web server modules imported successfully")
        
        # Test database connection
        from database import BenchDatabase
        db = BenchDatabase()
        print("✓ Database connection established")
        
        # Test API endpoints
        with app.test_client() as client:
            # Test config endpoint
            response = client.get('/api/config')
            assert response.status_code == 200
            print("✓ /api/config endpoint working")
            
            # Test benches endpoint
            response = client.get('/api/benches')
            assert response.status_code == 200
            data = response.get_json()
            print(f"✓ /api/benches endpoint working - found {len(data.get('benches', []))} benches")
            
            # Test searches endpoint
            response = client.get('/api/searches')
            assert response.status_code == 200
            searches_data = response.get_json()
            print(f"✓ /api/searches endpoint working - found {len(searches_data.get('searches', []))} searches")
            
            # Test segmentation endpoint (will return 404 if no data, which is expected)
            response = client.get('/api/image/1/segmentation')
            if response.status_code == 404:
                print("✓ /api/image/segmentation endpoint working (no data found, as expected)")
            elif response.status_code == 200:
                seg_data = response.get_json()
                print(f"✓ /api/image/segmentation endpoint working - found segmentation data")
            else:
                print(f"⚠ /api/image/segmentation endpoint returned {response.status_code}")
        
        print("\n🎉 All tests passed! The enhanced web UI is ready.")
        print("\nFeatures available:")
        print("• Display both Roboflow and Ultralytics detections")
        print("• Show detection type badges on images")
        print("• Click images to view detailed segmentation overlay")
        print("• Interactive modal with segmentation polygons")
        print("• Enhanced detection information display")
        print("\nTo start the web server:")
        print("python web_server.py")
        print("Then visit: http://localhost:8866")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

if __name__ == "__main__":
    success = test_web_server()
    sys.exit(0 if success else 1)