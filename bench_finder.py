#!/usr/bin/env python3
"""
Main bench finder script that orchestrates the entire pipeline:
1. Geocode a search query to get starting coordinates
2. Find benches near that location using OSM Overpass API
3. Capture Street View images for each bench at multiple headings
4. Use either Roboflow or Ultralytics API to detect if benches are visible in the images
5. Save results to SQLite database (including full segmentation data for Ultralytics)
"""
import argparse
import logging
import sys
from typing import List, Dict, Optional

from config import validate_config, SEARCH_RADIUS_METERS, DETECTION_BACKEND
from utils import setup_logging, ProgressTracker, log_execution_time, retry_on_failure
from geocoder import Geocoder
from overpass_client import OverpassClient
from streetview import StreetViewClient
from roboflow_client import RoboflowClient
from ultralytics_client import UltralyticsClient
from multi_model_client import MultiModelDetectionClient
from database import BenchDatabase
from schemas import (
    SearchCreate, BenchCreate, ImageCreate, DetectionCreate, UltralyticsDetectionCreate,
    SearchResults, BenchWithDetections
)


logger = logging.getLogger(__name__)


class BenchFinder:
    """Main class that orchestrates the bench finding pipeline."""
    
    def __init__(self, detection_backend: str | None = None, enable_fallback: bool = True):
        """Initialize all API clients and database.
        
        Args:
            detection_backend: Detection backend to use ('roboflow', 'ultralytics', or 'multi')
                             If None, uses config.DETECTION_BACKEND or defaults to 'multi'
            enable_fallback: Whether to enable multi-model fallback detection (default: True)
        """
        self.geocoder = Geocoder()
        self.overpass_client = OverpassClient()
        self.streetview_client = StreetViewClient()
        self.database = BenchDatabase()
        
        # Initialize detection client based on backend selection
        self.detection_backend = detection_backend or DETECTION_BACKEND
        self.enable_fallback = enable_fallback
        
        # Default to multi-model detection if fallback is enabled
        if enable_fallback and self.detection_backend != 'multi':
            logger.info(f"Enabling multi-model detection with fallback (primary: {self.detection_backend})")
            self.detection_backend = 'multi'

        if self.detection_backend == 'multi':
            logger.info("Initializing multi-model detection client with fallback")
            self.detection_client = MultiModelDetectionClient(
                enable_ultralytics=True,
                enable_roboflow_fallback=True
            )
        elif self.detection_backend == 'ultralytics':
            logger.info("Initializing Ultralytics detection backend (no fallback)")
            self.detection_client = UltralyticsClient()
        elif self.detection_backend == 'roboflow':
            logger.info("Initializing Roboflow detection backend (no fallback)")
            self.detection_client = RoboflowClient()
        else:
            raise ValueError(f"Unsupported detection backend: {self.detection_backend}. Use 'ultralytics', 'roboflow', or 'multi'")
        
        logger.info(f"BenchFinder initialized with {self.detection_backend} backend")
    
    @log_execution_time
    def find_benches(self, query: str, radius: int | None = None) -> Dict:
        """
        Complete bench finding pipeline for a given query.
        
        Args:
            query: Search query (address, location name, etc.)
            radius: Search radius in meters (defaults to config value)
            
        Returns:
            Dictionary with results and statistics
        """
        if radius is None:
            radius = SEARCH_RADIUS_METERS
            
        logger.info(f"Starting bench finding pipeline for query: '{query}' (radius: {radius}m)")
        
        try:
            # Step 1: Geocode the query
            coordinates = self._geocode_query(query)
            if not coordinates:
                return self._create_error_result("Failed to geocode query")
            
            start_lat, start_lng = coordinates
            
            # Step 2: Create search record in database
            search_id = self.database.create_search(SearchCreate(
                query=query,
                start_lat=start_lat,
                start_lng=start_lng,
                search_radius=radius
            ))
            
            # Step 3: Find benches using OSM Overpass API
            benches = self._find_nearby_benches(start_lat, start_lng, radius)
            if not benches:
                self.database.update_search_status(search_id, 'completed')
                return self._create_result(search_id, "No benches found in the area")
            
            logger.info(f"Found {len(benches)} benches to process")
            
            # Step 4: Process each bench
            results = self._process_benches(search_id, benches)
            
            # Step 5: Mark search as completed
            self.database.update_search_status(search_id, 'completed')
            
            # Step 6: Generate final results
            return self._create_result(search_id, f"Successfully processed {len(benches)} benches", results)
            
        except Exception as e:
            logger.error(f"Bench finding pipeline failed: {e}")
            if 'search_id' in locals():
                self.database.update_search_status(search_id, 'failed')
            return self._create_error_result(f"Pipeline failed: {e}")
    
    @retry_on_failure(max_retries=2, delay=1.0)
    def _geocode_query(self, query: str) -> Optional[tuple]:
        """Geocode a query string to coordinates."""
        logger.info(f"Geocoding query: {query}")
        return self.geocoder.geocode_query(query)
    
    @retry_on_failure(max_retries=2, delay=2.0)
    def _find_nearby_benches(self, lat: float, lng: float, radius: int) -> List[Dict]:
        """Find benches near the given coordinates."""
        logger.info(f"Searching for benches within {radius}m of {lat}, {lng}")
        return self.overpass_client.find_benches_near_point(lat, lng, radius)
    
    def _process_benches(self, search_id: int, benches: List[Dict]) -> Dict:
        """
        Process each bench: capture images and run detection.
        
        Args:
            search_id: Database search ID
            benches: List of bench dictionaries from OSM
            
        Returns:
            Processing results summary
        """
        progress = ProgressTracker(len(benches), "Processing benches")
        
        stats = {
            'benches_processed': 0,
            'benches_added': 0,
            'images_captured': 0,
            'images_successful': 0,
            'detections_performed': 0,
            'benches_detected': 0,
            'best_confidence': 0.0
        }
        
        for bench in benches:
            try:
                result = self._process_single_bench(search_id, bench)
                
                stats['benches_processed'] += 1
                if result['bench_added']:
                    stats['benches_added'] += 1
                
                stats['images_captured'] += result['images_captured']
                stats['images_successful'] += result['images_successful']
                stats['detections_performed'] += result['detections_performed']
                
                if result['bench_detected']:
                    stats['benches_detected'] += 1
                
                if result['best_confidence'] > stats['best_confidence']:
                    stats['best_confidence'] = result['best_confidence']
                
                progress.update()
                
            except Exception as e:
                bench_id = bench.get('provider_id', 'unknown')
                logger.error(f"Failed to process bench {bench_id}: {type(e).__name__}: {e}")
                import traceback
                logger.debug(f"Full traceback for bench {bench_id}:\n{traceback.format_exc()}")
                logger.debug(f"Bench data that caused the error: {bench}")
                progress.update()
                continue
        
        progress.finish()
        
        logger.info(f"Processing complete - {stats['benches_detected']}/{stats['benches_processed']} "
                   f"benches detected with best confidence: {stats['best_confidence']:.2f}")
        
        return stats
    
    def _process_single_bench(self, search_id: int, bench: Dict) -> Dict:
        """
        Process a single bench: add to DB, capture images, run detection.
        
        Args:
            search_id: Database search ID
            bench: Bench dictionary from OSM
            
        Returns:
            Processing results for this bench
        """
        result = {
            'bench_added': False,
            'images_captured': 0,
            'images_successful': 0,
            'detections_performed': 0,
            'bench_detected': False,
            'best_confidence': 0.0
        }
        
        # Validate required bench fields
        required_fields = ['lat', 'lng', 'provider_id']
        missing_fields = [field for field in required_fields if field not in bench or bench[field] is None]
        if missing_fields:
            raise ValueError(f"Bench missing required fields: {missing_fields}. Bench data: {bench}")
        
        # Validate coordinate types
        try:
            lat = float(bench['lat'])
            lng = float(bench['lng'])
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid coordinates in bench data: lat={bench.get('lat')}, lng={bench.get('lng')}. Error: {e}")
        
        # Add bench to database
        try:
            bench_data = BenchCreate(
                search_id=search_id,
                provider_id=bench['provider_id'],
                lat=lat,  # Use validated coordinates
                lng=lng,
                tags=bench.get('tags', {}),
                source=bench.get('source', 'osm'),
                external_id=bench.get('external_id')
            )
            bench_id = self.database.add_bench(bench_data)
            if bench_id:
                result['bench_added'] = True
                logger.debug(f"Added bench {bench['provider_id']} as DB record {bench_id}")
            else:
                logger.warning(f"Failed to add bench {bench['provider_id']} to database")
                return result
        except Exception as e:
            raise RuntimeError(f"Failed to add bench {bench['provider_id']} to database: {e}") from e
        
        # Generate unique identifier for image filenames
        bench_identifier = bench['provider_id'] or f"bench_{bench_id}"
        
        # Capture street view images
        try:
            image_results = self.streetview_client.capture_bench_images(
                lat, lng, bench_identifier  # Use validated coordinates
            )
        except Exception as e:
            raise RuntimeError(f"Failed to capture images for bench {bench['provider_id']}: {e}") from e
        
        result['images_captured'] = len(image_results)
        result['images_successful'] = sum(1 for img in image_results if img['success'])
        
        # Process each image
        for image_result in image_results:
            
            # Add image record to database
            try:
                image_id = self.database.add_image(ImageCreate(
                    bench_id=bench_id,
                    heading=image_result['heading'],
                    filepath=image_result['filepath'],
                    filename=image_result.get('filename'),
                    file_size=image_result.get('file_size'),
                    capture_success=image_result.get('success', False),
                    capture_error=image_result.get('error')
                ))
            except Exception as e:
                logger.error(f"Failed to add image record for bench {bench['provider_id']}, heading {image_result.get('heading')}: {e}, type: {type(e).__name__}")    
                continue
            
            # Skip detection if image capture failed
            if not image_result['success'] or not image_result.get('filepath'):
                continue
            
            # Run bench detection on the image
            try:
                detection_result = self.detection_client.detect_benches_in_image(
                    image_result['filepath']
                )
                
                # Add detection record to database based on backend type and result
                winning_backend = detection_result.get('winning_backend', 'unknown')
                winning_model = detection_result.get('winning_model', 'unknown')
                fallback_used = detection_result.get('fallback_used', False)
                total_attempts = detection_result.get('total_attempts', 1)
                
                # Log detection success with model information
                if detection_result['has_bench']:
                    logger.info(f"✅ Detection success: {winning_model} (backend: {winning_backend}, attempts: {total_attempts}, fallback: {fallback_used})")
                else:
                    logger.debug(f"❌ No detection: tried {total_attempts} models")
                
                # Store detection based on winning backend or detection structure
                if ('bench_detections' in detection_result and 'full_response' in detection_result) or winning_backend == 'ultralytics':
                    # Ultralytics detection format
                    model_url = winning_model if winning_backend == 'ultralytics' else getattr(self.detection_client, 'model_url', 'unknown')
                    self.database.add_ultralytics_detection(UltralyticsDetectionCreate(
                        image_id=image_id,
                        has_bench=detection_result['has_bench'],
                        bench_count=detection_result['bench_count'],
                        max_confidence=detection_result['max_confidence'],
                        full_response=detection_result.get('full_response', {}),
                        bench_detections=detection_result.get('bench_detections', []),
                        detection_success=True,
                        detection_error=None,
                        model_url=model_url,
                        confidence_threshold=getattr(self.detection_client, 'confidence_threshold', 0.0),
                        iou_threshold=getattr(self.detection_client, 'iou_threshold', 0.0),
                        image_size=getattr(self.detection_client, 'image_size', 640),
                        # Enhanced metadata for multi-model tracking
                        inference_time=detection_result.get('inference_time'),
                        preprocess_time=detection_result.get('preprocess_time'),
                        postprocess_time=detection_result.get('postprocess_time')
                    ))
                else:
                    # Roboflow detection format
                    model_id = detection_result.get('winning_model_id', getattr(self.detection_client, 'model_id', 'unknown'))
                    self.database.add_detection(DetectionCreate(
                        image_id=image_id,
                        has_bench=detection_result['has_bench'],
                        bench_count=detection_result['bench_count'],
                        max_confidence=detection_result['max_confidence'],
                        detections=detection_result.get('detections', []),
                        detection_success=True,
                        detection_error=None,
                        model_id=model_id,
                        confidence_threshold=getattr(self.detection_client, 'confidence_threshold', 0.0)
                    ))
                
                result['detections_performed'] += 1
                
                if detection_result['has_bench']:
                    result['bench_detected'] = True
                    if detection_result['max_confidence'] > result['best_confidence']:
                        result['best_confidence'] = detection_result['max_confidence']
                
            except Exception as e:
                logger.error(f"Detection failed for bench {bench['provider_id']}, image {image_result.get('filepath')}: {type(e).__name__}: {e}")
                import traceback
                logger.debug(f"Detection error traceback:\n{traceback.format_exc()}")
                # Add failed detection record based on backend
                if self.detection_backend == 'ultralytics':
                    self.database.add_ultralytics_detection(UltralyticsDetectionCreate(
                        image_id=image_id,
                        has_bench=False,
                        bench_count=0,
                        max_confidence=0.0,
                        bench_detections=[],
                        detection_success=False,
                        detection_error=str(e),
                        model_url=getattr(self.detection_client, 'model_url', 'unknown'),
                        confidence_threshold=getattr(self.detection_client, 'confidence_threshold', 0.0),
                        iou_threshold=getattr(self.detection_client, 'iou_threshold', 0.0),
                        image_size=getattr(self.detection_client, 'image_size', 640)
                    ))
                else:  # roboflow
                    self.database.add_detection(DetectionCreate(
                        image_id=image_id,
                        has_bench=False,
                        bench_count=0,
                        max_confidence=0.0,
                        detections=[],
                        detection_success=False,
                        detection_error=str(e),
                        model_id=getattr(self.detection_client, 'model_id', 'unknown'),
                        confidence_threshold=getattr(self.detection_client, 'confidence_threshold', 0.0)
                    ))
        
        # If no bench was detected, print image filepaths for manual debugging
        if not result.get('bench_detected', False):
            print("\n[DEBUG] No bench detected for this location.")
            print("Captured image filepaths for manual inspection:")
            for image_result in image_results:
                print(f"  - {image_result.get('filepath')}")
            print("You can manually review these images to check for benches or detection issues.\n")

        return result
    
    def _create_result(self, search_id: int, message: str, details: Dict  | None= None) -> Dict:
        """Create a standardized result dictionary."""
        result = {
            'success': True,
            'search_id': search_id,
            'message': message,
            'search_results': self.database.get_search_results(search_id)
        }
        
        if details:
            result['processing_stats'] = details
        
        return result
    
    def _create_error_result(self, error_message: str) -> Dict:
        """Create a standardized error result dictionary."""
        return {
            'success': False,
            'error': error_message,
            'search_id': None
        }


def main():
    """Main entry point for the bench finder CLI."""
    parser = argparse.ArgumentParser(
        description="Find benches using OSM data, Street View images, and AI detection (Roboflow or Ultralytics)"
    )
    parser.add_argument(
        'query',
        help='Search query (address, location name, etc.)'
    )
    parser.add_argument(
        '--radius',
        type=int,
        default=SEARCH_RADIUS_METERS,
        help=f'Search radius in meters (default: {SEARCH_RADIUS_METERS})'
    )
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    parser.add_argument(
        '--results',
        action='store_true',
        help='Show detailed results for the most recent search'
    )
    parser.add_argument(
        '--backend',
        choices=['roboflow', 'ultralytics', 'multi'],
        default=None,
        help=f'Detection backend to use: roboflow, ultralytics, or multi (default: multi with fallback)'
    )
    parser.add_argument(
        '--disable-fallback',
        action='store_true',
        help='Disable multi-model fallback detection (use single backend only)'
    )
    
    args = parser.parse_args()
    
    try:
        # Setup logging
        setup_logging(level=args.log_level)
        
        # Validate configuration
        validate_config()
        
        # Initialize bench finder with selected backend and fallback setting
        enable_fallback = not args.disable_fallback
        bench_finder = BenchFinder(detection_backend=args.backend, enable_fallback=enable_fallback)
        
        if args.results:
            # Show results for the most recent search (simplified for now)
            logger.info("Results display not implemented yet - check database directly")
            return 0
        
        # Run the bench finding pipeline
        logger.info(f"BenchFinder starting with query: '{args.query}' using {bench_finder.detection_backend} backend")
        
        results = bench_finder.find_benches(args.query, args.radius)
        
        if results['success']:
            logger.info(f"✅ {results['message']}")
            
            search_results: SearchResults = results['search_results']
            logger.info(f"📊 Summary:")
            logger.info(f"   • Search ID: {search_results.search.id}")
            logger.info(f"   • Query: {search_results.search.query}")
            logger.info(f"   • Location: ({search_results.search.start_lat}, {search_results.search.start_lng})")
            logger.info(f"   • Search radius: {search_results.search.search_radius}m")
            logger.info(f"   • Benches found: {search_results.bench_count}")
            logger.info(f"   • Images captured: {search_results.successful_images}/{search_results.total_images}")
            logger.info(f"   • Images with benches detected: {search_results.images_with_benches}")
            logger.info(f"   • Best confidence: {search_results.best_confidence:.2f}")

            if 'processing_stats' in results:
                stats = results['processing_stats']
                logger.info(f"   • Processing stats: {stats['benches_detected']}/{stats['benches_processed']} benches detected")
            
            # Show multi-model detection statistics if available
            if hasattr(bench_finder.detection_client, 'get_detection_stats'):
                detection_stats = bench_finder.detection_client.get_detection_stats()
                if not detection_stats.get('no_data', False):
                    logger.info(f"🔍 Detection Statistics:")
                    logger.info(f"   • Total model attempts: {detection_stats['total_attempts']}")
                    if detection_stats.get('ultralytics_attempts', 0) > 0:
                        success_rate = detection_stats.get('ultralytics_success_rate', 0) * 100
                        logger.info(f"   • Ultralytics: {detection_stats['ultralytics_successes']}/{detection_stats['ultralytics_attempts']} ({success_rate:.1f}%)")
                    if detection_stats.get('roboflow_attempts', 0) > 0:
                        success_rate = detection_stats.get('roboflow_success_rate', 0) * 100
                        logger.info(f"   • Roboflow: {detection_stats['roboflow_successes']}/{detection_stats['roboflow_attempts']} ({success_rate:.1f}%)")
        
        else:
            logger.error(f"❌ {results['error']}")
            return 1
        
        return 0
        
    except KeyboardInterrupt:
        logger.warning("🛑 Operation cancelled by user")
        return 130
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())