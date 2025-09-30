#!/usr/bin/env python3
"""
Test script to validate both local and API Ultralytics inference modes.
"""
import os
import sys
import logging
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from ultralytics_client import UltralyticsClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def test_local_mode():
    """Test local YOLO inference mode."""
    logger.info("=== Testing Local Mode ===")
    
    try:
        # Force local mode
        client = UltralyticsClient(use_local=True)
        model_info = client.get_model_info()
        
        logger.info(f"Local mode initialized successfully:")
        logger.info(f"  Mode: {model_info.get('mode')}")
        logger.info(f"  Model: {model_info.get('model_url')}")
        logger.info(f"  Segmentation supported: {model_info.get('supports_segmentation')}")
        
        return True
        
    except Exception as e:
        logger.error(f"Local mode test failed: {e}")
        return False

def test_api_mode():
    """Test API mode."""
    logger.info("=== Testing API Mode ===")
    
    # Set environment variable to force API mode
    os.environ['ULTRALYTICS_USE_LOCAL'] = 'false'
    
    try:
        # Import after setting env var to pick up the change
        import importlib
        import config
        importlib.reload(config)
        
        # Check if API key is available
        if not os.getenv('ULTRALYTICS_API_KEY'):
            logger.warning("ULTRALYTICS_API_KEY not set, skipping API mode test")
            return True
        
        client = UltralyticsClient()
        model_info = client.get_model_info()
        
        logger.info(f"API mode initialized successfully:")
        logger.info(f"  Mode: {model_info.get('mode')}")
        logger.info(f"  Model: {model_info.get('model_url')}")
        logger.info(f"  API endpoint: {model_info.get('api_endpoint')}")
        logger.info(f"  Segmentation supported: {model_info.get('supports_segmentation')}")
        
        return True
        
    except Exception as e:
        logger.error(f"API mode test failed: {e}")
        return False

def test_with_sample_image():
    """Test with sample image if available."""
    logger.info("=== Testing with Sample Image ===")
    
    # Look for any image files in the images directory
    images_dir = Path("images")
    if not images_dir.exists():
        logger.warning("No images directory found, skipping image test")
        return True
    
    # Find first image file
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
    sample_image = None
    
    for ext in image_extensions:
        for img_file in images_dir.glob(f"*{ext}"):
            sample_image = img_file
            break
        if sample_image:
            break
    
    if not sample_image:
        logger.warning("No image files found, skipping image test")
        return True
    
    logger.info(f"Testing with image: {sample_image}")
    
    # Test local mode with image
    os.environ['ULTRALYTICS_USE_LOCAL'] = 'true'
    import importlib
    import config
    importlib.reload(config)
    
    try:
        client = UltralyticsClient()
        result = client.detect_benches_in_image(str(sample_image))
        
        logger.info(f"Local detection result:")
        logger.info(f"  Success: {result['success']}")
        logger.info(f"  Mode: {result.get('inference_mode')}")
        if result['success']:
            logger.info(f"  Benches found: {result['bench_count']}")
            logger.info(f"  Max confidence: {result['max_confidence']:.3f}")
        else:
            logger.info(f"  Error: {result.get('error', 'Unknown error')}")
        
        return result['success']
        
    except Exception as e:
        logger.error(f"Image test failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting Ultralytics modes test")
    
    # Test both modes
    local_success = test_local_mode()
    api_success = test_api_mode()
    image_success = test_with_sample_image()
    
    # Summary
    logger.info("=== Test Summary ===")
    logger.info(f"Local mode: {'✓' if local_success else '✗'}")
    logger.info(f"API mode: {'✓' if api_success else '✗'}")
    logger.info(f"Image test: {'✓' if image_success else '✗'}")
    
    if local_success and api_success:
        logger.info("All tests passed! 🎉")
        sys.exit(0)
    else:
        logger.error("Some tests failed")
        sys.exit(1)