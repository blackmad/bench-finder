"""
Mapillary API client for fetching bench detections.
"""
import requests
import base64
import json
import logging
import os
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import struct
from urllib.parse import urljoin

logger = logging.getLogger(__name__)


@dataclass
class MapillaryDetection:
    """Represents a bench detection from Mapillary."""
    detection_id: str
    image_id: str
    image_coordinates: Tuple[float, float]  # [lng, lat]
    value: str
    geometry_encoded: str
    geometry_decoded: Optional[List[List[float]]] = None
    confidence: float = 1.0  # Mapillary doesn't provide confidence, assume high
    created_at: Optional[datetime] = None


@dataclass
class MapillaryImage:
    """Represents a Mapillary image with detections."""
    image_id: str
    coordinates: Tuple[float, float]  # [lng, lat]
    detections: List[MapillaryDetection]


class MapillaryBenchDetector:
    """Client for fetching bench detections from Mapillary API."""
    
    def __init__(self, access_token: str, images_dir: str = "images"):
        """
        Initialize Mapillary client.
        
        Args:
            access_token: Mapillary API access token
            images_dir: Directory to store downloaded images
        """
        self.access_token = access_token
        self.base_url = "https://graph.mapillary.com"
        self.images_dir = images_dir
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'OAuth {access_token}'
        })
        
        # Ensure images directory exists
        os.makedirs(self.images_dir, exist_ok=True)
    
    def search_images_with_detections(
        self,
        bbox: Tuple[float, float, float, float],  # [min_lng, min_lat, max_lng, max_lat]
        limit: int = 1000
    ) -> List[MapillaryImage]:
        """
        Search for images with bench detections in a bounding box.
        
        Args:
            bbox: Bounding box as [min_lng, min_lat, max_lng, max_lat]
            limit: Maximum number of images to return
            
        Returns:
            List of MapillaryImage objects with bench detections
        """
        min_lng, min_lat, max_lng, max_lat = bbox
        
        # Search for images with detections in the bounding box
        url = f"{self.base_url}/images"
        params = {
            'fields': 'id,geometry,detections.id,detections.value,detections.geometry,detections.created_at',
            'bbox': f"{min_lng},{min_lat},{max_lng},{max_lat}",
            'limit': limit,
            'access_token': self.access_token
        }
        
        try:
            logger.info(f"Searching Mapillary for images in bbox: {bbox}")
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            images_with_benches = []
            
            for image_data in data.get('data', []):
                bench_detections = self._filter_bench_detections(image_data)
                if bench_detections:
                    image = MapillaryImage(
                        image_id=image_data['id'],
                        coordinates=(
                            image_data['geometry']['coordinates'][0],
                            image_data['geometry']['coordinates'][1]
                        ),
                        detections=bench_detections
                    )
                    images_with_benches.append(image)
            
            logger.info(f"Found {len(images_with_benches)} images with bench detections")
            return images_with_benches
            
        except requests.RequestException as e:
            logger.error(f"Error fetching Mapillary images: {e}")
            return []
    
    def get_image_detections(self, image_id: str) -> List[MapillaryDetection]:
        """
        Get all detections for a specific image.
        
        Args:
            image_id: Mapillary image ID
            
        Returns:
            List of detections for the image
        """
        url = f"{self.base_url}/{image_id}/detections"
        params = {
            'fields': 'id,image,value,geometry,created_at',
            'access_token': self.access_token
        }
        
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            detections = []
            
            for detection_data in data.get('data', []):
                if detection_data.get('value') == 'object--bench':
                    detection = self._parse_detection(detection_data)
                    if detection:
                        detections.append(detection)
            
            return detections
            
        except requests.RequestException as e:
            logger.error(f"Error fetching detections for image {image_id}: {e}")
            return []
    
    def _filter_bench_detections(self, image_data: Dict) -> List[MapillaryDetection]:
        """Filter and parse bench detections from image data."""
        bench_detections = []
        
        detections = image_data.get('detections', {}).get('data', [])
        for detection_data in detections:
            if detection_data.get('value') == 'object--bench':
                detection = self._parse_detection(detection_data, image_data)
                if detection:
                    bench_detections.append(detection)
        
        return bench_detections
    
    def _parse_detection(
        self, 
        detection_data: Dict, 
        image_data: Optional[Dict] = None
    ) -> Optional[MapillaryDetection]:
        """Parse a detection from API response."""
        try:
            # Get image coordinates
            if image_data:
                image_coords = (
                    image_data['geometry']['coordinates'][0],
                    image_data['geometry']['coordinates'][1]
                )
                image_id = image_data['id']
            else:
                image_info = detection_data.get('image', {})
                image_coords = (
                    image_info.get('geometry', {}).get('coordinates', [0, 0])[0],
                    image_info.get('geometry', {}).get('coordinates', [0, 0])[1]
                )
                image_id = image_info.get('id', '')
            
            # Parse created_at if available
            created_at = None
            if 'created_at' in detection_data:
                try:
                    created_at = datetime.fromisoformat(detection_data['created_at'].replace('Z', '+00:00'))
                except ValueError:
                    pass
            
            # Decode geometry
            geometry_decoded = None
            geometry_encoded = detection_data.get('geometry', '')
            if geometry_encoded:
                geometry_decoded = self._decode_geometry(geometry_encoded)
            
            return MapillaryDetection(
                detection_id=detection_data['id'],
                image_id=image_id,
                image_coordinates=image_coords,
                value=detection_data['value'],
                geometry_encoded=geometry_encoded,
                geometry_decoded=geometry_decoded,
                created_at=created_at
            )
            
        except (KeyError, ValueError) as e:
            logger.warning(f"Error parsing detection: {e}")
            return None
    
    def _decode_geometry(self, encoded_geometry: str) -> Optional[List[List[float]]]:
        """
        Decode base64 encoded geometry from Mapillary.
        
        This is a simplified decoder - Mapillary uses a custom format.
        You may need to adjust based on the actual encoding format.
        """
        try:
            # Decode base64
            decoded_bytes = base64.b64decode(encoded_geometry)
            
            # This is a simplified implementation
            # The actual Mapillary geometry format may be more complex
            # and might require protobuf decoding
            
            # For now, return None and log that decoding is needed
            logger.debug(f"Geometry decoding not fully implemented for: {encoded_geometry[:50]}...")
            return None
            
        except Exception as e:
            logger.warning(f"Failed to decode geometry: {e}")
            return None
    
    def search_benches_by_location(
        self,
        center_lat: float,
        center_lng: float,
        radius_meters: int = 1000
    ) -> List[MapillaryImage]:
        """
        Search for bench detections around a center point.
        
        Args:
            center_lat: Center latitude
            center_lng: Center longitude  
            radius_meters: Search radius in meters
            
        Returns:
            List of images with bench detections
        """
        # Convert radius to approximate degrees
        # 1 degree ≈ 111,000 meters at equator
        radius_deg = radius_meters / 111000
        
        bbox = (
            center_lng - radius_deg,  # min_lng
            center_lat - radius_deg,  # min_lat
            center_lng + radius_deg,  # max_lng
            center_lat + radius_deg   # max_lat
        )
        
        return self.search_images_with_detections(bbox)
    
    def download_image(
        self,
        image_id: str,
        size: int = 2048,
        filename: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Download a Mapillary image.
        
        Args:
            image_id: Mapillary image ID
            size: Image size (width in pixels, height will be proportional)
            filename: Custom filename (if None, uses image_id)
            
        Returns:
            Dict with download result info or None if failed
        """
        if filename is None:
            filename = f"mapillary_{image_id}.jpg"
        
        filepath = os.path.join(self.images_dir, filename)
        
        # Check if image already exists
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            logger.debug(f"Image {image_id} already exists at {filepath} ({file_size} bytes)")
            return {
                'success': True,
                'image_id': image_id,
                'filepath': filepath,
                'filename': filename,
                'file_size': file_size,
                'downloaded': False  # Already existed
            }
        
        # Download the image
        url = f"{self.base_url}/{image_id}"
        params = {
            'fields': 'thumb_2048_url' if size >= 2048 else 'thumb_1024_url' if size >= 1024 else 'thumb_256_url',
            'access_token': self.access_token
        }
        
        try:
            # First get the image metadata with thumb URL
            response = self.session.get(url, params=params)
            response.raise_for_status()
            
            image_data = response.json()
            
            # Get the appropriate thumbnail URL
            thumb_url = None
            if size >= 2048 and 'thumb_2048_url' in image_data:
                thumb_url = image_data['thumb_2048_url']
            elif size >= 1024 and 'thumb_1024_url' in image_data:
                thumb_url = image_data['thumb_1024_url']
            elif 'thumb_256_url' in image_data:
                thumb_url = image_data['thumb_256_url']
            
            if not thumb_url:
                logger.error(f"No thumbnail URL found for image {image_id}")
                return None
            
            # Download the image
            logger.info(f"Downloading Mapillary image {image_id} from {thumb_url}")
            img_response = self.session.get(thumb_url)
            img_response.raise_for_status()
            
            # Save the image
            with open(filepath, 'wb') as f:
                f.write(img_response.content)
            
            file_size = len(img_response.content)
            logger.info(f"Successfully downloaded image {image_id} to {filepath} ({file_size} bytes)")
            
            return {
                'success': True,
                'image_id': image_id,
                'filepath': filepath,
                'filename': filename,
                'file_size': file_size,
                'downloaded': True,
                'thumb_url': thumb_url
            }
            
        except requests.RequestException as e:
            logger.error(f"Error downloading image {image_id}: {e}")
            return {
                'success': False,
                'image_id': image_id,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error downloading image {image_id}: {e}")
            return {
                'success': False,
                'image_id': image_id,
                'error': str(e)
            }
    
    def download_images_for_benches(self, images: List[MapillaryImage]) -> List[Dict]:
        """
        Download all images that contain bench detections.
        
        Args:
            images: List of MapillaryImage objects with bench detections
            
        Returns:
            List of download results
        """
        download_results = []
        
        for image in images:
            if image.detections:  # Only download if there are bench detections
                result = self.download_image(image.image_id)
                if result:
                    download_results.append(result)
        
        success_count = sum(1 for r in download_results if r.get('success', False))
        logger.info(f"Downloaded {success_count}/{len(download_results)} Mapillary images")
        
        return download_results
    
    def get_detection_statistics(self, images: List[MapillaryImage]) -> Dict:
        """Get statistics about bench detections."""
        total_images = len(images)
        total_detections = sum(len(img.detections) for img in images)
        
        # Group by location for density analysis
        location_counts: Dict[Tuple[float, float], int] = {}
        for image in images:
            # Round coordinates to create location buckets
            lat_bucket = round(image.coordinates[1], 3)
            lng_bucket = round(image.coordinates[0], 3)
            key = (lat_bucket, lng_bucket)
            location_counts[key] = location_counts.get(key, 0) + len(image.detections)
        
        return {
            'total_images': total_images,
            'total_detections': total_detections,
            'avg_detections_per_image': total_detections / max(total_images, 1),
            'unique_locations': len(location_counts),
            'max_detections_at_location': max(location_counts.values()) if location_counts else 0
        }


def create_mapillary_client(access_token: str) -> MapillaryBenchDetector:
    """Create a Mapillary client instance."""
    return MapillaryBenchDetector(access_token)