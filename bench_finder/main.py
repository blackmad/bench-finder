"""
Main bench finder pipeline orchestration.
"""
import logging
import math
import os
import shutil
from typing import List, Dict, Optional, Tuple
from PIL import Image as PILImage

from bench_finder.clients.base_detection_client import DetectionClient, DetectionResult
from bench_finder.config import SEARCH_RADIUS_METERS, DETECTION_BACKEND, MAPILLARY_ACCESS_TOKEN
from bench_finder.models.streetview_models import StreetViewImageCapture
from bench_finder.utils import ProgressTracker, log_execution_time, retry_on_failure
from bench_finder.core.geocoder import Geocoder
from bench_finder.core.streetview import StreetViewClient
from bench_finder.clients.overpass_client import OverpassClient
from bench_finder.clients.roboflow_client import RoboflowClient
from bench_finder.clients.ultralytics_client import UltralyticsClient
from bench_finder.clients.multi_model_client import MultiModelDetectionClient
from bench_finder.services.database import BenchDatabase
from bench_finder.models.schemas import (
    SearchCreate, BenchCreate, ImageCreate, DetectionCreate, 
    UltralyticsDetectionCreate, SearchResults, BenchProcessingResult, ProcessingStats,
    PipelineResult
)
from examples.bench_generator import BenchGenerator, BenchCandidate
from examples.overpass_bench_generator import OverpassBenchGenerator
from examples.mapillary_bench_generator import MapillaryBenchGenerator
from bench_finder.display import display_bench_detection_results, display_no_bench_detected, create_combined_image_display

logger = logging.getLogger(__name__)


class BenchFinder:
    """Main class that orchestrates the bench finding pipeline."""
    
    def __init__(self, detection_backend: str | None = None, enable_fallback: bool = True, copy_bench_images: bool = True, bench_generators: List[BenchGenerator] | None = None):
        """Initialize all API clients and database.
        
        Args:
            detection_backend: Detection backend to use ('roboflow', 'ultralytics', or 'multi')
                             If None, uses config.DETECTION_BACKEND or defaults to 'multi'
            enable_fallback: Whether to enable multi-model fallback detection (default: True)
            copy_bench_images: Whether to copy images with detected benches to bench_images/{model_name}/ (default: True)
            bench_generators: List of BenchGenerator instances to use for finding benches.
                            If None, creates default generators (OSM + Mapillary if available)
        """
        self.geocoder = Geocoder()
        self.streetview_client = StreetViewClient()
        self.database = BenchDatabase()
        
        # Initialize bench generators
        if bench_generators is None:
            self.bench_generators = self._create_default_generators()
        else:
            self.bench_generators = bench_generators
        
        logger.info(f"BenchFinder initialized with {len(self.bench_generators)} generators: {[g.name for g in self.bench_generators]}")
        
        # Initialize detection client based on backend selection
        self.detection_backend = detection_backend or DETECTION_BACKEND
        self.enable_fallback = enable_fallback
        self.copy_bench_images = copy_bench_images
        
        # Default to multi-model detection if fallback is enabled
        if enable_fallback and self.detection_backend != 'multi':
            logger.info(f"Enabling multi-model detection with fallback (primary: {self.detection_backend})")
            self.detection_backend = 'multi'

        self.detection_client: DetectionClient
        if self.detection_backend == 'multi':
            logger.info("Initializing multi-model detection client with fallback")
            self.detection_client = MultiModelDetectionClient()
        elif self.detection_backend == 'ultralytics':
            logger.info("Initializing Ultralytics detection backend (no fallback)")
            self.detection_client = UltralyticsClient()
        elif self.detection_backend == 'roboflow':
            logger.info("Initializing Roboflow detection backend (no fallback)")
            self.detection_client = RoboflowClient()
        else:
            raise ValueError(f"Unsupported detection backend: {self.detection_backend}. Use 'ultralytics', 'roboflow', or 'multi'")
        
        logger.info(f"BenchFinder initialized with {self.detection_backend} backend")
        if self.copy_bench_images:
            logger.info("Bench image copying enabled - detected bench images will be copied to bench_images/{model_name}/")
        else:
            logger.info("Bench image copying disabled")
    
    def _create_default_generators(self) -> List[BenchGenerator]:
        """Create default set of bench generators."""
        generators: List[BenchGenerator] = []
        
        # Always add OSM generator
        try:
            osm_generator = OverpassBenchGenerator()
            generators.append(osm_generator)
            logger.info("Added OpenStreetMap generator")
        except Exception as e:
            logger.error(f"Failed to initialize OSM generator: {e}")
        
        # Add Mapillary generator if token is available
        try:
            if MAPILLARY_ACCESS_TOKEN:
                mapillary_generator = MapillaryBenchGenerator()
                generators.append(mapillary_generator)
                logger.info("Added Mapillary generator")
            else:
                logger.warning("MAPILLARY_ACCESS_TOKEN not set - Mapillary generator not available")
        except Exception as e:
            logger.warning(f"Failed to initialize Mapillary generator: {e}")
        
        if not generators:
            raise ValueError("No bench generators could be initialized")
        
        return generators
    
    def _copy_bench_image(self, image_path: str, model_name: str, bench_id: str, heading: int) -> Optional[str]:
        """
        Copy an image with detected bench to the bench_images directory.
        
        Args:
            image_path: Source image file path
            model_name: Name of the model that detected the bench
            bench_id: Bench identifier for organizing files
            heading: Image heading for unique naming
            
        Returns:
            Path to copied image, or None if copy failed
        """
        if not self.copy_bench_images or not os.path.exists(image_path):
            return None
        
        try:
            # Create directory structure: bench_images/{model_name}/
            output_dir = os.path.join('bench_images', model_name)
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate unique filename
            base_filename = os.path.basename(image_path)
            name, ext = os.path.splitext(base_filename)
            new_filename = f"{bench_id}_heading_{heading}_{name}{ext}"
            output_path = os.path.join(output_dir, new_filename)
            
            # Copy the file
            shutil.copy2(image_path, output_path)
            logger.debug(f"Copied bench image to: {output_path}")
            return output_path
            
        except Exception as e:
            logger.warning(f"Failed to copy bench image {image_path}: {e}")
            return None
    
    def _calculate_pixel_coverage(self, detection_result: DetectionResult, image_path: str) -> float:
        """
        Calculate what percentage of pixels the bench occupies in the image.
        
        Args:
            detection_result: StandardDetectionResult from the ML model
            image_path: Path to the image file for dimensions
            
        Returns:
            Percentage of pixels covered by bench detections (0.0 to 100.0)
        """
        try:
            if not detection_result.has_bench:
                return 0.0
            
            # Debug logging
            logger.debug(f"Calculating pixel coverage for {image_path}")
            logger.debug(f"Detection result has {len(detection_result.detections)} detections")
            
            # Get image dimensions
            with PILImage.open(image_path) as img:
                image_width, image_height = img.size
                total_pixels = image_width * image_height
            
            total_bench_pixels: float = 0
            
            # Process standardized detections
            for detection_item in detection_result.detections:
                bbox = detection_item.bbox
                logger.debug(f"Using standardized bbox: x1={bbox.x1:.1f}, y1={bbox.y1:.1f}, x2={bbox.x2:.1f}, y2={bbox.y2:.1f}")
                
                # Use pre-calculated width and height from BoundingBox
                bbox_pixels = bbox.width * bbox.height
                total_bench_pixels += bbox_pixels
                logger.debug(f"Bbox area: {bbox.width:.1f} x {bbox.height:.1f} = {bbox_pixels:.0f} pixels")
            
            # Calculate percentage
            if total_pixels > 0:
                coverage_percentage = (total_bench_pixels / total_pixels) * 100
                logger.debug(f"Pixel coverage calculation: {total_bench_pixels} bench pixels / {total_pixels} total pixels = {coverage_percentage:.2f}%")
                return min(coverage_percentage, 100.0)  # Cap at 100%
            
            logger.debug(f"No pixels found - returning 0.0% coverage")
            return 0.0
            
        except Exception as e:
            logger.debug(f"Failed to calculate pixel coverage for {image_path}: {e}")
            return 0.0
    
    @log_execution_time
    def find_benches(self, query: str, radius: int | None = None) -> PipelineResult:
        """
        Complete bench finding pipeline for a given query.
        
        Args:
            query: Search query (address, location name, etc.)
            radius: Search radius in meters (defaults to config value)
            
        Returns:
            PipelineResult with results and statistics
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
            
            # Step 3: Find benches using all available generators (OSM, Mapillary, etc.)
            benches: List[BenchCandidate] = self._find_nearby_benches(start_lat, start_lng, radius)
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
    def _find_nearby_benches(self, lat: float, lng: float, radius: int) -> List[BenchCandidate]:
        """Find benches near the given coordinates using all generators."""
        logger.info(f"Searching for benches within {radius}m of {lat}, {lng} using {len(self.bench_generators)} generators")
        
        all_candidates = []
        generator_results = {}
        
        # Query each generator
        for generator in self.bench_generators:
            try:
                logger.debug(f"Querying {generator.name} for benches")
                candidates = generator.find_benches_near_point(lat, lng, radius)
                all_candidates.extend(candidates)
                generator_results[generator.name] = len(candidates)
                logger.info(f"{generator.name}: found {len(candidates)} bench candidates")
            except Exception as e:
                logger.error(f"Error querying {generator.name}: {e}")
                generator_results[generator.name] = 0
        
        logger.info(f"Total bench candidates found: {len(all_candidates)} ({generator_results})")
        
        # Deduplicate benches based on proximity (same location from different sources)
        deduplicated_candidates = self._deduplicate_bench_candidates(all_candidates)
        logger.info(f"After deduplication: {len(deduplicated_candidates)} unique benches")

        return deduplicated_candidates
    
    def _deduplicate_bench_candidates(self, candidates: List[BenchCandidate]) -> List[BenchCandidate]:
        """
        Remove duplicate bench candidates based on proximity.
        
        Two benches are considered duplicates if they are within 10 meters of each other.
        When duplicates are found, prefers the one with higher confidence or from OSM.
        
        Args:
            candidates: List of BenchCandidate objects
            
        Returns:
            List of unique BenchCandidate objects
        """
        if not candidates:
            return candidates
        
        # Distance threshold for considering two benches as duplicates (meters)
        DUPLICATE_THRESHOLD_METERS = 10
        
        unique_candidates: List[BenchCandidate] = []
        
        for candidate in candidates:
            is_duplicate = False
            
            # Check if this candidate is close to any existing unique candidate
            for i, existing in enumerate(unique_candidates):
                distance = self._haversine_distance(
                    candidate.lat, candidate.lng,
                    existing.lat, existing.lng
                )
                
                if distance <= DUPLICATE_THRESHOLD_METERS:
                    is_duplicate = True
                    
                    # Replace existing if current candidate is "better"
                    if self._is_better_candidate(candidate, existing):
                        unique_candidates[i] = candidate
                        logger.debug(f"Replaced duplicate bench: {existing.provider_id} -> {candidate.provider_id}")
                    else:
                        logger.debug(f"Skipped duplicate bench: {candidate.provider_id} (keeping {existing.provider_id})")
                    break
            
            if not is_duplicate:
                unique_candidates.append(candidate)
        
        return unique_candidates
    
    def _is_better_candidate(self, candidate1: BenchCandidate, candidate2: BenchCandidate) -> bool:
        """
        Determine which candidate is "better" for deduplication purposes.
        
        Args:
            candidate1: First candidate
            candidate2: Second candidate
            
        Returns:
            True if candidate1 is better than candidate2
        """
        # Prefer candidate with confidence score
        if candidate1.confidence is not None and candidate2.confidence is None:
            return True
        if candidate1.confidence is None and candidate2.confidence is not None:
            return False
        
        # If both have confidence, prefer higher confidence
        if candidate1.confidence is not None and candidate2.confidence is not None:
            return candidate1.confidence > candidate2.confidence
        
        # If neither has confidence, prefer OSM (more reliable positioning)
        if candidate1.source == 'osm' and candidate2.source != 'osm':
            return True
        if candidate1.source != 'osm' and candidate2.source == 'osm':
            return False
        
        # If same source type, prefer the first one (arbitrary)
        return False
    
    def _haversine_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calculate the Haversine distance between two points in meters.
        
        Args:
            lat1, lng1: First point coordinates
            lat2, lng2: Second point coordinates
            
        Returns:
            Distance in meters
        """
        # Convert decimal degrees to radians
        lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Radius of Earth in meters
        R = 6371000
        return R * c
    
    def _process_benches(self, search_id: int, benches: List[BenchCandidate]) -> ProcessingStats:
        """
        Process each bench: capture images and run detection.
        
        Args:
            search_id: Database search ID
            benches: List of bench dictionaries from various sources (OSM, Mapillary, etc.)
            
        Returns:
            ProcessingStats with processing results summary
        """
        progress = ProgressTracker(len(benches), "Processing benches")
        
        stats = ProcessingStats(
            benches_processed=0,
            benches_added=0,
            images_captured=0,
            images_successful=0,
            detections_performed=0,
            benches_detected=0,
            best_confidence=0.0
        )
        
        for bench in benches:
            try:
                result = self._process_single_bench(search_id, bench)
                
                stats.benches_processed += 1
                if result.bench_added:
                    stats.benches_added += 1
                
                stats.images_captured += result.images_captured
                stats.images_successful += result.images_successful
                stats.detections_performed += result.detections_performed
                
                if result.bench_detected:
                    stats.benches_detected += 1
                
                if result.best_confidence > stats.best_confidence:
                    stats.best_confidence = result.best_confidence
                
                progress.update()
                
            except Exception as e:
                bench_id = bench.provider_id
                logger.error(f"Failed to process bench {bench_id}: {type(e).__name__}: {e}")
                import traceback
                logger.debug(f"Full traceback for bench {bench_id}:\n{traceback.format_exc()}")
                logger.debug(f"Bench data that caused the error: {bench}")
                progress.update()
                continue
        
        progress.finish()
        
        logger.info(f"Processing complete - {stats.benches_detected}/{stats.benches_processed} "
                   f"benches detected with best confidence: {stats.best_confidence:.2f}")
        
        return stats
    
    def _process_single_bench(self, search_id: int, bench: BenchCandidate) -> BenchProcessingResult:
        """
        Process a single bench: add to DB, capture images, run detection.
        
        Args:
            search_id: Database search ID
            bench: Bench dictionary from any source (OSM, Mapillary, etc.)
            
        Returns:
            BenchProcessingResult for this bench
        """
        result = BenchProcessingResult(
            bench_added=False,
            images_captured=0,
            images_successful=0,
            detections_performed=0,
            bench_detected=False,
            best_confidence=0.0
        )
        
        # Validate coordinate types
        try:
            lat = float(bench.lat)
            lng = float(bench.lng)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid coordinates in bench data: lat={bench.lat}, lng={bench.lng}. Error: {e}")
        
        # Add bench to database
        try:
            bench_data = BenchCreate(
                search_id=search_id,
                provider_id=bench.provider_id,
                lat=lat,  # Use validated coordinates
                lng=lng,
                tags=bench.tags,
                source=bench.source,
                external_id=bench.external_id
            )
            bench_id = self.database.add_bench(bench_data)
            if bench_id:
                result.bench_added = True
                logger.debug(f"Added bench {bench.provider_id} as DB record {bench_id}")
            else:
                logger.warning(f"Failed to add bench {bench.provider_id} to database")
                return result
        except Exception as e:
            raise RuntimeError(f"Failed to add bench {bench.provider_id} to database: {e}") from e
        
        # Generate unique identifier for image filenames
        bench_identifier = bench.provider_id or f"bench_{bench_id}"
        
        # Capture street view images
        try:
            image_results = self.streetview_client.capture_bench_images(
                lat, lng, bench_identifier  # Use validated coordinates
            )
        except Exception as e:
            raise RuntimeError(f"Failed to capture images for bench {bench.provider_id}: {e}") from e
        
        result.images_captured = len(image_results.captures)
        result.images_successful = sum(1 for img in image_results.captures if img.success)
        
        # Phase 1: Add all images to database and collect successful ones
        successful_images: List[StreetViewImageCapture] = []
        for image_capture in image_results.captures:
            
            # Add image record to database
            try:
                image_id = self.database.add_image(ImageCreate(
                    bench_id=bench_id,
                    heading=image_capture.heading,
                    filepath=image_capture.filepath,
                    filename=image_capture.filename,
                    file_size=image_capture.file_size,
                    capture_success=image_capture.success,
                    capture_error=image_capture.error
                ))
                
                # Track successful images for detection
                if image_capture.success and image_capture.filepath:
                    successful_images.append(image_capture)
                    
            except Exception as e:
                logger.error(f"Failed to add image record for bench {bench.provider_id}, heading {image_capture.heading}: {e}, type: {type(e).__name__}")
                continue
        
        # Phase 2: Run detection on all successful images and calculate pixel coverage
        detection_results: List[DetectionResult] = []
        
        for image_result in successful_images:
            try:
                logger.debug(f"Running detection on {image_result.filepath}")
                detection_result = self.detection_client.detect_benches_in_image(
                    image_result.filepath
                )
                
                # Calculate pixel coverage
                pixel_coverage = self._calculate_pixel_coverage(detection_result, image_result.filepath)
                
                detection_results.append(detection_result)
                result.detections_performed += 1
                
                # Update overall results
                if detection_result.has_bench:
                    result.bench_detected = True
                    if detection_result.max_confidence > result.best_confidence:
                        result.best_confidence = detection_result.max_confidence
                
                logger.debug(f"Image {image_result.heading}° - Bench: {detection_result.has_bench}, "
                           f"Confidence: {detection_result.max_confidence:.2f}, "
                           f"Pixel coverage: {pixel_coverage:.1f}%")
                
            except Exception as e:
                logger.error(f"Detection failed for bench {bench.provider_id}, image {image_result.filepath}: {type(e).__name__}: {e}")
                import traceback
                logger.debug(f"Detection error traceback:\n{traceback.format_exc()}")
        
        # Phase 3: Find the representative image (highest pixel coverage with bench detected)
        representative_detection = None
        
        if detection_results:
            # Sort by pixel coverage (descending), then by confidence (descending)
            representative_detection = max(detection_results, key=lambda x: (x.pixel_coverage, x.max_confidence))
            
            logger.info(f"🎯 Selected representative image: heading {representative_detection.image_path.heading}° "
                       f"with {representative_detection.pixel_coverage:.1f}% pixel coverage and "
                       f"{representative_detection.detection_result.max_confidence:.2f} confidence")
        
        # Phase 4: Save all detection results to database and display representative image
        for detection_info in detection_results:
            image_result = detection_info['image_result']
            detection_result = detection_info.detection_result
            image_id = image_result.image_id
            
            if detection_result is None:
                # Handle detection failure
                error = detection_info.get('error', 'Unknown error')
                if self.detection_backend == 'ultralytics':
                    self.database.add_ultralytics_detection(UltralyticsDetectionCreate(
                        image_id=image_id,
                        has_bench=False,
                        bench_count=0,
                        max_confidence=0.0,
                        bench_detections=[],
                        detection_success=False,
                        detection_error=error,
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
                        detections=[],  # Empty list for failed detections
                        detection_success=False,
                        detection_error=error,
                        model_id=getattr(self.detection_client, 'model_id', 'unknown'),
                        confidence_threshold=getattr(self.detection_client, 'confidence_threshold', 0.0)
                    ))
                continue
            
            # Store successful detection result
            winning_backend = detection_info.backend_name
            winning_model = detection_info.model_name
            
            if (hasattr(detection_result, 'bench_detections') and hasattr(detection_result, 'full_response')) or winning_backend == 'ultralytics':
                # Ultralytics detection format
                model_url = winning_model if winning_backend == 'ultralytics' else getattr(self.detection_client, 'model_url', 'unknown')
                self.database.add_ultralytics_detection(UltralyticsDetectionCreate(
                    image_id=image_id,
                    has_bench=detection_result.has_bench,
                    bench_count=detection_result.bench_count,
                    max_confidence=detection_result.max_confidence,
                    full_response=getattr(detection_result, 'full_response', {}),
                    bench_detections=getattr(detection_result, 'bench_detections', []),
                    detection_success=True,
                    detection_error=None,
                    model_url=model_url,
                    confidence_threshold=getattr(self.detection_client, 'confidence_threshold', 0.0),
                    iou_threshold=getattr(self.detection_client, 'iou_threshold', 0.0),
                    image_size=getattr(self.detection_client, 'image_size', 640),
                    # Enhanced metadata for multi-model tracking
                    inference_time=getattr(detection_result, 'inference_time', None),
                    preprocess_time=getattr(detection_result, 'preprocess_time', None),
                    postprocess_time=getattr(detection_result, 'postprocess_time', None)
                ))
            else:
                # Roboflow detection format
                model_id = getattr(detection_result, 'winning_model_id', getattr(self.detection_client, 'model_id', 'unknown'))
                self.database.add_detection(DetectionCreate(
                    image_id=image_id,
                    has_bench=detection_result.has_bench,
                    bench_count=detection_result.bench_count,
                    max_confidence=detection_result.max_confidence,
                    detections=getattr(detection_result, 'detections', []),
                    detection_success=True,
                    detection_error=None,
                    model_id=model_id,
                    confidence_threshold=getattr(self.detection_client, 'confidence_threshold', 0.0)
                ))
            
            # Display and copy only the representative image
            if detection_info == representative_detection:
                winning_model = detection_info['winning_model']
                pixel_coverage = detection_info['pixel_coverage']
                
                # Log detection success with model information
                logger.info(f"✅ Representative detection: {winning_model} (backend: {winning_backend}, "
                           f"attempts: {detection_info['total_attempts']}, fallback: {detection_info['fallback_used']})")
                
                # Copy the representative image
                copied_path = self._copy_bench_image(
                    image_result.filepath,
                    winning_model, 
                    bench_identifier, 
                    image_result.heading
                )
                copy_info = f" (copied to {copied_path})" if copied_path else ""
                
                print(f"🏆 Representative bench image: {image_result.filepath} "
                      f"(heading {image_result.heading}°) with {pixel_coverage:.1f}% pixel coverage "
                      f"and confidence {detection_result.max_confidence:.2f} using {winning_model}{copy_info}")
                
                # Import here to avoid circular imports
                from tools.roboflow_detector import render_detections
                from term_image.image import AutoImage
                
                # Pass StandardDetectionResult object directly to render_detections
                print(AutoImage(render_detections(image_result.filepath, detection_result, winning_model)))
        
        # Use display utilities for consistent output
        display_bench_detection_results(
            bench_identifier, 
            successful_images,
            detection_results,
            representative_detection,
            self.copy_bench_images
        )
        
        # If no bench was detected, show debug information
        if not result.bench_detected:
            display_no_bench_detected([{'filepath': img.filepath, 'heading': img.heading} for img in successful_images])
            
            # Create combined image display
            combined_img = create_combined_image_display([{'filepath': img.filepath} for img in successful_images])
            if combined_img:
                from term_image.image import AutoImage
                print(AutoImage(combined_img))
            else:
                print("(Combined image display unavailable - check individual files below)")
            
            # Also print the file paths
            for image_result in successful_images:
                print(f"  - {image_result.filepath}")
            print("You can manually review these images to check for benches or detection issues.\n")

        return result
    
    def _create_result(self, search_id: int, message: str, stats: ProcessingStats | None = None) -> PipelineResult:
        """Create a standardized result."""
        search_results = self.database.get_search_results(search_id)
        
        return PipelineResult(
            success=True,
            search_id=search_id,
            message=message,
            stats=stats
        )
    
    def _create_error_result(self, error_message: str) -> PipelineResult:
        """Create a standardized error result."""
        return PipelineResult(
            success=False,
            search_id=None,
            message="",
            error=error_message
        )
