"""
Roboflow API integration for bench detection using computer vision.
"""
import requests
import base64
import json
import logging
from typing import Dict, List, Optional
from config import ROBOFLOW_API_KEY, ROBOFLOW_MODEL_ID, ROBOFLOW_CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)


class RoboflowClient:
    """Client for Roboflow inference API."""
    
    def __init__(self):
        """Initialize the Roboflow client."""
        if not ROBOFLOW_API_KEY:
            raise ValueError("ROBOFLOW_API_KEY is required")
        
        self.api_key = ROBOFLOW_API_KEY
        self.model_id = ROBOFLOW_MODEL_ID
        self.confidence_threshold = ROBOFLOW_CONFIDENCE_THRESHOLD
        self.base_url = f"https://detect.roboflow.com/{self.model_id}"
    
    def detect_benches_in_image(self, image_path: str) -> Dict:
        """
        Detect benches in an image using Roboflow API.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with detection results
        """
        try:
            logger.debug(f"Analyzing image for benches: {image_path}")
            
            # Read and encode the image
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()
                encoded_image = base64.b64encode(image_data).decode('utf-8')
            
            # Prepare the API request
            url = f"{self.base_url}?api_key={self.api_key}&confidence={self.confidence_threshold}"
            
            # Make the request
            response = requests.post(
                url,
                data=encoded_image,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )
            
            if response.status_code != 200:
                logger.error(f"Roboflow API returned status {response.status_code}: {response.text}")
                return self._create_error_result(image_path, f"HTTP {response.status_code}")
            
            # Parse the response
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Roboflow response: {e}")
                return self._create_error_result(image_path, f"JSON decode error: {e}")
            
            # Process the detection results
            return self._process_detection_result(image_path, result)
            
        except FileNotFoundError:
            logger.error(f"Image file not found: {image_path}")
            return self._create_error_result(image_path, "File not found")
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling Roboflow API: {e}")
            return self._create_error_result(image_path, f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error analyzing image {image_path}: {e}")
            return self._create_error_result(image_path, f"Unexpected error: {e}")
    
    def _process_detection_result(self, image_path: str, api_result: Dict) -> Dict:
        """
        Process the raw Roboflow API result into a standardized format.
        
        Args:
            image_path: Path to the analyzed image
            api_result: Raw API response dictionary
            
        Returns:
            Processed detection result dictionary
        """
        try:
            predictions = api_result.get('predictions', [])
            
            # Filter predictions to only include benches above confidence threshold
            bench_detections = []
            for prediction in predictions:
                # Check if this is a bench detection with sufficient confidence
                class_name = prediction.get('class', '').lower()
                confidence = prediction.get('confidence', 0)
                
                if 'bench' in class_name and confidence >= self.confidence_threshold:
                    bench_detections.append({
                        'class': prediction.get('class'),
                        'confidence': confidence,
                        'x': prediction.get('x'),
                        'y': prediction.get('y'),
                        'width': prediction.get('width'),
                        'height': prediction.get('height')
                    })
            
            has_bench = len(bench_detections) > 0
            max_confidence = max((d['confidence'] for d in bench_detections), default=0)
            
            result = {
                'image_path': image_path,
                'success': True,
                'has_bench': has_bench,
                'bench_count': len(bench_detections),
                'max_confidence': max_confidence,
                'detections': bench_detections,
                'raw_predictions': len(predictions),
                'model_id': self.model_id,
                'confidence_threshold': self.confidence_threshold
            }
            
            if has_bench:
                logger.info(f"Bench detected in {image_path} - Count: {len(bench_detections)}, Max confidence: {max_confidence:.2f}")
            else:
                logger.debug(f"No bench detected in {image_path}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing detection result for {image_path}: {e}")
            return self._create_error_result(image_path, f"Processing error: {e}")
    
    def _create_error_result(self, image_path: str, error: str) -> Dict:
        """Create a standardized error result dictionary."""
        return {
            'image_path': image_path,
            'success': False,
            'has_bench': False,
            'bench_count': 0,
            'max_confidence': 0,
            'detections': [],
            'raw_predictions': 0,
            'error': error,
            'model_id': self.model_id,
            'confidence_threshold': self.confidence_threshold
        }
    
    def batch_detect_benches(self, image_paths: List[str]) -> List[Dict]:
        """
        Detect benches in multiple images.
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            List of detection result dictionaries
        """
        logger.info(f"Batch analyzing {len(image_paths)} images for benches")
        
        results = []
        successful_detections = 0
        benches_found = 0
        
        for i, image_path in enumerate(image_paths, 1):
            logger.debug(f"Processing image {i}/{len(image_paths)}: {image_path}")
            
            result = self.detect_benches_in_image(image_path)
            results.append(result)
            
            if result['success']:
                successful_detections += 1
                if result['has_bench']:
                    benches_found += 1
        
        logger.info(f"Batch analysis complete - {successful_detections}/{len(image_paths)} successful, "
                   f"{benches_found} images with benches detected")
        
        return results
    
    def get_model_info(self) -> Optional[Dict]:
        """
        Get information about the Roboflow model.
        
        Returns:
            Model information dictionary or None if unavailable
        """
        try:
            # This would need to be implemented based on Roboflow's model info endpoint
            # For now, return basic info
            return {
                'model_id': self.model_id,
                'confidence_threshold': self.confidence_threshold,
                'classes': ['bench']  # This model is specifically for bench detection
            }
        except Exception as e:
            logger.error(f"Error getting model info: {e}")
            return None
    
    def validate_image_file(self, image_path: str) -> bool:
        """
        Validate that an image file exists and is readable.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            True if valid, False otherwise
        """
        try:
            import os
            from PIL import Image
            
            if not os.path.exists(image_path):
                logger.warning(f"Image file does not exist: {image_path}")
                return False
            
            if os.path.getsize(image_path) == 0:
                logger.warning(f"Image file is empty: {image_path}")
                return False
            
            # Try to open as image to verify it's valid
            with Image.open(image_path) as img:
                img.verify()
            
            return True
            
        except Exception as e:
            logger.warning(f"Image validation failed for {image_path}: {e}")
            return False