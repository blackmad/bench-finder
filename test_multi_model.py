#!/usr/bin/env python3
"""
Test script to demonstrate the new multi-model fallback detection system.
"""
import logging
import sys
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from multi_model_client import MultiModelDetectionClient
from utils import setup_logging

def test_multi_model_detection():
    """Test the multi-model detection client with a sample image."""
    
    # Setup logging
    setup_logging(level='INFO')
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Testing Multi-Model Detection Client")
    logger.info("=" * 50)
    
    try:
        # Initialize the multi-model client
        logger.info("Initializing multi-model detection client...")
        client = MultiModelDetectionClient(
            enable_ultralytics=True,
            enable_roboflow_fallback=True
        )
        
        # Find a sample image from the images directory
        images_dir = Path("images")
        if not images_dir.exists():
            logger.error("❌ Images directory not found. Run bench_finder.py first to capture some images.")
            return 1
        
        # Get the first image file
        image_files = list(images_dir.glob("*.jpg")) + list(images_dir.glob("*.png"))
        if not image_files:
            logger.error("❌ No image files found in images directory.")
            return 1
        
        test_image = image_files[0]
        logger.info(f"📸 Testing with image: {test_image}")
        
        # Run detection
        logger.info("\n🔍 Starting multi-model detection...")
        result = client.detect_benches_in_image(str(test_image))
        
        # Display results
        logger.info("\n📊 Detection Results:")
        logger.info("-" * 30)
        logger.info(f"Success: {result.get('success', False)}")
        logger.info(f"Bench Detected: {result.get('has_bench', False)}")
        logger.info(f"Confidence: {result.get('max_confidence', 0):.3f}")
        logger.info(f"Winning Backend: {result.get('winning_backend', 'unknown')}")
        logger.info(f"Winning Model: {result.get('winning_model', 'unknown')}")
        logger.info(f"Fallback Used: {result.get('fallback_used', False)}")
        logger.info(f"Total Attempts: {result.get('total_attempts', 0)}")
        
        # Show attempt details
        if 'detection_attempts' in result:
            logger.info(f"\n🎯 Detection Attempts ({len(result['detection_attempts'])}):")
            for i, attempt in enumerate(result['detection_attempts'], 1):
                status = "✅" if attempt['has_bench'] else "❌"
                logger.info(f"  {i}. {status} {attempt['model_id']} ({attempt['model_type']}) - "
                           f"confidence: {attempt['confidence']:.3f}")
                if attempt.get('error'):
                    logger.info(f"     Error: {attempt['error']}")
        
        # Show overall statistics
        stats = client.get_detection_stats()
        if not stats.get('no_data'):
            logger.info(f"\n📈 Overall Statistics:")
            logger.info(f"Total Attempts: {stats['total_attempts']}")
            logger.info(f"Successful Detections: {stats['successful_attempts']}")
            
            if stats.get('ultralytics_attempts', 0) > 0:
                rate = stats.get('ultralytics_success_rate', 0) * 100
                logger.info(f"Ultralytics: {stats['ultralytics_successes']}/{stats['ultralytics_attempts']} ({rate:.1f}%)")
            
            if stats.get('roboflow_attempts', 0) > 0:
                rate = stats.get('roboflow_success_rate', 0) * 100
                logger.info(f"Roboflow: {stats['roboflow_successes']}/{stats['roboflow_attempts']} ({rate:.1f}%)")
        
        logger.info("\n✅ Multi-model detection test completed!")
        return 0
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return 1

def main():
    """Main entry point."""
    return test_multi_model_detection()

if __name__ == '__main__':
    sys.exit(main())