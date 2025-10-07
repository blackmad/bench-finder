"""
Google Street View Static API integration for capturing street view images.
"""
import requests
import os
import logging
from typing import Optional, List, Tuple, Dict
from PIL import Image
from io import BytesIO
from ..config import (
    GOOGLE_MAPS_API_KEY, STREETVIEW_SIZE, STREETVIEW_FOV, 
    STREETVIEW_HEADINGS, IMAGES_DIR
)

logger = logging.getLogger(__name__)


class StreetViewClient:
    """Client for Google Street View Static API."""
    
    def __init__(self):
        """Initialize the Street View client."""
        if not GOOGLE_MAPS_API_KEY:
            raise ValueError("GOOGLE_MAPS_API_KEY is required")
        
        self.api_key = GOOGLE_MAPS_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api/streetview"
        
        # Ensure images directory exists
        os.makedirs(IMAGES_DIR, exist_ok=True)
    
    def capture_bench_images(self, lat: float, lng: float, bench_id: str) -> List[Dict]:
        """
        Capture street view images from multiple headings for a bench location.
        
        Args:
            lat: Latitude of the bench
            lng: Longitude of the bench
            bench_id: Unique identifier for the bench
            
        Returns:
            List of dictionaries with image info (filepath, heading, success)
        """
        logger.info(f"Capturing street view images for bench {bench_id} at {lat}, {lng}")
        
        results = []
        downloaded_count = 0
        cached_count = 0
        
        for heading in STREETVIEW_HEADINGS:
            try:
                result = self.capture_image(lat, lng, bench_id, heading)
                results.append(result)
                
                if result['success']:
                    if result.get('cached', False):
                        cached_count += 1
                        logger.debug(f"Using cached image at heading {heading}°")
                    else:
                        downloaded_count += 1
                        logger.debug(f"Successfully downloaded image at heading {heading}°")
                else:
                    logger.warning(f"Failed to capture image at heading {heading}°")
                    
            except Exception as e:
                logger.error(f"Error capturing image at heading {heading}°: {e}")
                results.append({
                    'bench_id': bench_id,
                    'lat': lat,
                    'lng': lng,
                    'heading': heading,
                    'filepath': None,
                    'success': False,
                    'error': str(e)
                })
        
        successful_images = sum(1 for r in results if r['success'])
        failed_images = len(STREETVIEW_HEADINGS) - successful_images
        
        logger.info(f"Bench {bench_id}: {successful_images}/{len(STREETVIEW_HEADINGS)} images total "
                   f"({downloaded_count} downloaded, {cached_count} cached, {failed_images} failed)")
        
        return results
    
    def capture_image(self, lat: float, lng: float, bench_id: str, heading: int) -> Dict:
        """
        Capture a single street view image at specified heading.
        
        Args:
            lat: Latitude
            lng: Longitude  
            bench_id: Unique identifier for the bench
            heading: Compass heading (0-360 degrees)
            
        Returns:
            Dictionary with capture results
        """
        try:
            # Generate filename first to check if image already exists
            filename = f"bench_{bench_id}_heading_{heading}.jpg"
            filepath = os.path.join(IMAGES_DIR, filename)
            
            # Check if image already exists
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                logger.debug(f"Image already exists: {filename}, skipping download")
                return {
                    'bench_id': bench_id,
                    'lat': lat,
                    'lng': lng,
                    'heading': heading,
                    'filepath': filepath,
                    'filename': filename,
                    'success': True,
                    'file_size': os.path.getsize(filepath),
                    'cached': True
                }
            
            # Build the Street View Static API URL
            params = {
                'location': f"{lat},{lng}",
                'size': STREETVIEW_SIZE,
                'heading': heading,
                'fov': STREETVIEW_FOV,
                'key': self.api_key
            }
            
            logger.debug(f"Requesting street view image: lat={lat}, lng={lng}, heading={heading}")

            # Make the API request
            response = requests.get(self.base_url, params=params, timeout=30)
            
            # Check if we got a valid response
            if response.status_code != 200:
                logger.error(f"Street View API returned status {response.status_code}")
                return self._create_failure_result(bench_id, lat, lng, heading, 
                                                 f"HTTP {response.status_code}")
            
            # Check content type to ensure we got an image
            content_type = response.headers.get('content-type', '')
            if not content_type.startswith('image/'):
                logger.error(f"Expected image, got content-type: {content_type}")
                return self._create_failure_result(bench_id, lat, lng, heading, 
                                                 f"Invalid content type: {content_type}")
            
            # Save the image
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            # Verify the image was saved correctly
            if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
                logger.error(f"Failed to save image to {filepath}")
                return self._create_failure_result(bench_id, lat, lng, heading, 
                                                 "Failed to save image")
            
            # Optionally verify it's a valid image
            try:
                with Image.open(filepath) as img:
                    width, height = img.size
                    logger.debug(f"Saved image {filename}: {width}x{height}")
            except Exception as e:
                logger.warning(f"Could not verify image {filename}: {e}")
            
            return {
                'bench_id': bench_id,
                'lat': lat,
                'lng': lng,
                'heading': heading,
                'filepath': filepath,
                'filename': filename,
                'success': True,
                'file_size': os.path.getsize(filepath),
                'cached': False
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error capturing street view image: {e}")
            return self._create_failure_result(bench_id, lat, lng, heading, f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error capturing street view image: {e}")
            return self._create_failure_result(bench_id, lat, lng, heading, f"Unexpected error: {e}")
    
    def _create_failure_result(self, bench_id: str, lat: float, lng: float, 
                              heading: int, error: str) -> Dict:
        """Create a standardized failure result dictionary."""
        return {
            'bench_id': bench_id,
            'lat': lat,
            'lng': lng,
            'heading': heading,
            'filepath': None,
            'filename': None,
            'success': False,
            'error': error
        }
    
    def get_street_view_metadata(self, lat: float, lng: float) -> Optional[Dict]:
        """
        Get metadata about street view availability at a location.
        
        Args:
            lat: Latitude
            lng: Longitude
            
        Returns:
            Metadata dictionary or None if not available
        """
        try:
            metadata_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
            params = {
                'location': f"{lat},{lng}",
                'key': self.api_key
            }
            
            response = requests.get(metadata_url, params=params, timeout=10)
            response.raise_for_status()
            
            metadata = response.json()
            
            if metadata.get('status') == 'OK':
                logger.debug(f"Street view available at {lat}, {lng}")
                return metadata
            else:
                logger.debug(f"Street view not available at {lat}, {lng}: {metadata.get('status')}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting street view metadata: {e}")
            return None
    
    def cleanup_images(self, filepaths: List[str]):
        """
        Clean up image files.
        
        Args:
            filepaths: List of file paths to delete
        """
        for filepath in filepaths:
            try:
                if filepath and os.path.exists(filepath):
                    os.remove(filepath)
                    logger.debug(f"Removed image file: {filepath}")
            except Exception as e:
                logger.warning(f"Could not remove image file {filepath}: {e}")