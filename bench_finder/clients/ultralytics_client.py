"""
Ultralytics integration for bench detection using computer vision with segmentation.
Supports both local YOLO11-seg inference and Ultralytics API.
"""
import requests
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
from ..models.schemas import (
    UltralyticsApiResponse, UltralyticsDetectionResult, UltralyticsImageResult,
    UltralyticsDetectionItem, UltralyticsBox, UltralyticsSegments, UltralyticsSpeed
)
from ..config import (
    ULTRALYTICS_API_KEY, 
    ULTRALYTICS_MODEL_URL,
    ULTRALYTICS_CONFIDENCE_THRESHOLD,
    ULTRALYTICS_IOU_THRESHOLD,
    ULTRALYTICS_IMAGE_SIZE,
    ULTRALYTICS_USE_LOCAL,
    ULTRALYTICS_LOCAL_MODEL,
    ULTRALYTICS_MODELS_DIR
)

logger = logging.getLogger(__name__)


class UltralyticsClient:
    """Client for Ultralytics inference supporting both local YOLO11-seg and API modes."""
    
    def __init__(self, use_local=None):
        """Initialize the Ultralytics client.
        
        Args:
            use_local: Override for local mode setting (for testing)
        """
        # Allow override for testing purposes
        if use_local is not None:
            self.use_local = use_local
        else:
            self.use_local = ULTRALYTICS_USE_LOCAL
            
        self.confidence_threshold = ULTRALYTICS_CONFIDENCE_THRESHOLD
        self.iou_threshold = ULTRALYTICS_IOU_THRESHOLD
        self.image_size = ULTRALYTICS_IMAGE_SIZE
        
        if self.use_local:
            self._init_local_mode()
        else:
            self._init_api_mode()
    
    def _init_local_mode(self):
        """Initialize local YOLO inference mode."""
        logger.info("Initializing Ultralytics client in local inference mode")
        
        try:
            from ultralytics import YOLO
            self.YOLO = YOLO
        except ImportError:
            raise ImportError("ultralytics package is required for local inference. Install with: pip install ultralytics")
        
        self.models_dir = Path(ULTRALYTICS_MODELS_DIR)
        self.models_dir.mkdir(exist_ok=True)
        
        self.local_model_path = self.models_dir / ULTRALYTICS_LOCAL_MODEL
        self.model_url = None
        self.api_key = None
        self.inference_url = None
        
        # Initialize the model (will download if needed)
        self._ensure_local_model()
        logger.info(f"Local YOLO model ready: {self.local_model_path}")
    
    def _init_api_mode(self):
        """Initialize API mode."""
        logger.info("Initializing Ultralytics client in API mode")
        
        if not ULTRALYTICS_API_KEY:
            raise ValueError("ULTRALYTICS_API_KEY is required for API mode")
        
        self.api_key = ULTRALYTICS_API_KEY
        self.model_url = ULTRALYTICS_MODEL_URL
        self.inference_url = "https://predict.ultralytics.com"
        self.local_model_path = None
        self.YOLO = None
    
    def _ensure_local_model(self):
        """Ensure the local YOLO model is available, download if necessary."""
        if not self.local_model_path.exists():
            logger.info(f"Local model not found at {self.local_model_path}, downloading {ULTRALYTICS_LOCAL_MODEL}...")
            try:
                # Load model - this will automatically download if not present
                model = self.YOLO(ULTRALYTICS_LOCAL_MODEL)
                # Save to our models directory
                model.save(self.local_model_path)
                logger.info(f"Model downloaded and saved to {self.local_model_path}")
            except Exception as e:
                logger.error(f"Failed to download model {ULTRALYTICS_LOCAL_MODEL}: {e}")
                raise
    
    def detect_benches_in_image(self, image_path: str) -> UltralyticsDetectionResult:
        """
        Detect benches in an image using either local YOLO11-seg or Ultralytics API.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            UltralyticsDetectionResult with detection results including full segmentation data
        """
        if self.use_local:
            return self._detect_benches_local(image_path)
        else:
            return self._detect_benches_api(image_path)
    
    def _detect_benches_local(self, image_path: str) -> UltralyticsDetectionResult:
        """
        Detect benches using local YOLO11-seg model.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            UltralyticsDetectionResult with detection results
        """
        try:
            logger.debug(f"Analyzing image for benches with local YOLO: {image_path}")
            
            # Load the model
            model = self.YOLO(self.local_model_path)
            
            # Run inference
            results = model(
                image_path,
                conf=self.confidence_threshold,
                iou=self.iou_threshold,
                imgsz=self.image_size,
                verbose=False
            )
            
            # Process the results
            return self._process_local_detection_result(image_path, results)
            
        except FileNotFoundError:
            logger.error(f"Image file not found: {image_path}")
            return self._create_error_result(image_path, "File not found")
        except Exception as e:
            logger.error(f"Unexpected error analyzing image {image_path}: {e}")
            return self._create_error_result(image_path, f"Unexpected error: {e}")
    
    def _detect_benches_api(self, image_path: str) -> UltralyticsDetectionResult:
        """
        Detect benches using Ultralytics API.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            UltralyticsDetectionResult with detection results
        """
        try:
            logger.debug(f"Analyzing image for benches with Ultralytics API: {image_path}")
            
            # Prepare the API request headers and data
            headers = {"x-api-key": self.api_key}
            data = {
                "model": self.model_url,
                "imgsz": self.image_size,
                "conf": self.confidence_threshold,
                "iou": self.iou_threshold
            }
            
            # Read the image file
            with open(image_path, 'rb') as f:
                files = {"file": f}
                
                # Make the request
                response = requests.post(
                    self.inference_url,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=60
                )
            
            if response.status_code != 200:
                logger.error(f"Ultralytics API returned status {response.status_code}: {response.text}")
                return self._create_error_result(image_path, f"HTTP {response.status_code}: {response.text}")
            
            # Parse the response
            try:
                result = response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Ultralytics response: {e}")
                return self._create_error_result(image_path, f"JSON decode error: {e}")
            
            # Process the detection results
            return self._process_api_detection_result(image_path, result)
            
        except FileNotFoundError:
            logger.error(f"Image file not found: {image_path}")
            return self._create_error_result(image_path, "File not found")
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling Ultralytics API: {e}")
            return self._create_error_result(image_path, f"Network error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error analyzing image {image_path}: {e}")
            return self._create_error_result(image_path, f"Unexpected error: {e}")
    
    def _process_local_detection_result(self, image_path: str, results) -> UltralyticsDetectionResult:
        """
        Process the local YOLO detection results into a standardized format.
        
        Args:
            image_path: Path to the analyzed image
            results: YOLO results object from local inference
            
        Returns:
            UltralyticsDetectionResult with processed detection data
        """
        try:
            # Extract timing information
            timing_info = {}
            if hasattr(results[0], 'speed') and results[0].speed is not None:
                speed = results[0].speed
                timing_info = {
                    'inference_time': speed.get('inference', 0),
                    'preprocess_time': speed.get('preprocess', 0),
                    'postprocess_time': speed.get('postprocess', 0)
                }
            
            # Process detections
            bench_detections = []
            all_results = []
            
            for result in results:
                # Get the class names
                class_names = result.names if hasattr(result, 'names') else {}
                
                if result.boxes is not None:
                    for i, box in enumerate(result.boxes):
                        # Get class information
                        class_id = int(box.cls.cpu().numpy())
                        class_name = class_names.get(class_id, f"class_{class_id}").lower()
                        confidence = float(box.conf.cpu().numpy())
                        
                        # Get bounding box coordinates
                        xyxy = box.xyxy.cpu().numpy()[0]
                        box_data = UltralyticsBox(
                            x1=float(xyxy[0]),
                            y1=float(xyxy[1]),
                            x2=float(xyxy[2]),
                            y2=float(xyxy[3])
                        )
                        
                        # Get segmentation data if available
                        segments_data = None
                        if result.masks is not None and i < len(result.masks.xy):
                            mask_points = result.masks.xy[i]
                            if len(mask_points) > 0:
                                segments_data = UltralyticsSegments(
                                    x=mask_points[:, 0].tolist(),
                                    y=mask_points[:, 1].tolist()
                                )
                        
                        detection_data = UltralyticsDetectionItem(
                            **{"class": class_names.get(class_id, f"class_{class_id}")},
                            class_id=class_id,
                            confidence=confidence,
                            box=box_data,
                            segments=segments_data,
                        )
                        
                        all_results.append(detection_data)
                        
                        # Check if this is a bench detection
                        if 'bench' in class_name and confidence >= self.confidence_threshold:
                            bench_detections.append(detection_data)
            
            has_bench = len(bench_detections) > 0
            max_confidence = max((d.confidence for d in bench_detections), default=0.0)
            
            # Create proper Pydantic models for the response
            speed_data = UltralyticsSpeed(
                inference=timing_info.get('inference_time'),
                preprocess=timing_info.get('preprocess_time'),
                postprocess=timing_info.get('postprocess_time')
            )
            
            image_result = UltralyticsImageResult(
                results=all_results,
                shape=results[0].orig_shape if hasattr(results[0], 'orig_shape') else [0, 0],
                speed=speed_data
            )
            
            full_response = UltralyticsApiResponse(images=[image_result])
            
            result_data = UltralyticsDetectionResult(
                image_path=image_path,
                success=True,
                has_bench=has_bench,
                bench_count=len(bench_detections),
                max_confidence=max_confidence,
                bench_detections=bench_detections,
                full_response=full_response,
                model_url=str(self.local_model_path) if self.local_model_path else 'local',
                confidence_threshold=self.confidence_threshold,
                iou_threshold=self.iou_threshold,
                image_size=self.image_size,
                inference_mode='local',
                inference_time=timing_info.get('inference_time'),
                preprocess_time=timing_info.get('preprocess_time'),
                postprocess_time=timing_info.get('postprocess_time')
            )
            
            if has_bench:
                logger.info(f"Bench detected in {image_path} - Count: {len(bench_detections)}, Max confidence: {max_confidence:.2f}")
                # Log segmentation info for first bench detection
                if bench_detections and bench_detections[0].segments:
                    segments = bench_detections[0].segments
                    logger.debug(f"Segmentation points: {len(segments.x)} coordinates")
            else:
                logger.debug(f"No bench detected in {image_path}")
            
            return result_data
            
        except Exception as e:
            logger.error(f"Error processing local detection result for {image_path}: {e}")
            return self._create_error_result(image_path, f"Processing error: {e}")
    
    def _process_api_detection_result(self, image_path: str, api_result: Dict) -> UltralyticsDetectionResult:
        """
        Process the raw Ultralytics API result into a standardized format.
        
        Args:
            image_path: Path to the analyzed image
            api_result: Raw API response dictionary
            
        Returns:
            UltralyticsDetectionResult with processed detection data
        """
        try:
            # Extract timing information if available
            timing_info = {}
            if 'images' in api_result and len(api_result['images']) > 0:
                speed_info = api_result['images'][0].get('speed', {})
                timing_info = {
                    'inference_time': speed_info.get('inference'),
                    'preprocess_time': speed_info.get('preprocess'), 
                    'postprocess_time': speed_info.get('postprocess')
                }
            
            # Process results from all images (typically just one)
            bench_detections = []
            all_results = []
            
            for image_result in api_result.get('images', []):
                for result in image_result.get('results', []):
                    # Handle the actual API response format
                    # The API returns 'class' as an integer and 'name' as the class name
                    class_id = result.get('class', 0)
                    class_name = result.get('name', f'class_{class_id}')
                    confidence = result.get('confidence', 0)
                    
                    # Convert API result to Pydantic model
                    box_data = UltralyticsBox(**result.get('box', {}))
                    segments_data = None
                    if result.get('segments'):
                        segments_data = UltralyticsSegments(**result.get('segments', {}))
                    
                    detection_item = UltralyticsDetectionItem(
                        **{"class": class_name},
                        class_id=class_id,
                        confidence=confidence,
                        box=box_data,
                        segments=segments_data
                    )
                    
                    all_results.append(detection_item)
                    
                    # Check if this is a bench detection
                    class_name_lower = class_name.lower()
                    
                    # Look for "bench" in the class name and check confidence
                    if 'bench' in class_name_lower and confidence >= self.confidence_threshold:
                        bench_detections.append(detection_item)
            
            has_bench = len(bench_detections) > 0
            max_confidence = max((d.confidence for d in bench_detections), default=0.0)
            
            # Convert API result to Pydantic model - handle the actual API response format
            try:
                full_response = UltralyticsApiResponse(**api_result)
            except Exception as e:
                logger.warning(f"Could not parse API response as Pydantic model: {e}")
                # Create a minimal response structure
                full_response = UltralyticsApiResponse(images=[])
            
            result_data = UltralyticsDetectionResult(
                image_path=image_path,
                success=True,
                has_bench=has_bench,
                bench_count=len(bench_detections),
                max_confidence=max_confidence,
                bench_detections=bench_detections,
                full_response=full_response,
                model_url=self.model_url or "unknown",
                confidence_threshold=self.confidence_threshold,
                iou_threshold=self.iou_threshold,
                image_size=self.image_size,
                inference_mode='api',
                inference_time=timing_info.get('inference_time'),
                preprocess_time=timing_info.get('preprocess_time'),
                postprocess_time=timing_info.get('postprocess_time')
            )
            
            if has_bench:
                logger.info(f"Bench detected in {image_path} - Count: {len(bench_detections)}, Max confidence: {max_confidence:.2f}")
                # Log segmentation info for first bench detection
                if bench_detections and bench_detections[0].segments:
                    segments = bench_detections[0].segments
                    logger.debug(f"Segmentation points: {len(segments.x)} coordinates")
            else:
                logger.debug(f"No bench detected in {image_path}")
            
            return result_data
            
        except Exception as e:
            logger.error(f"Error processing detection result for {image_path}: {e}")
            return self._create_error_result(image_path, f"Processing error: {e}")
    
    def _create_error_result(self, image_path: str, error: str) -> UltralyticsDetectionResult:
        """Create a standardized error result."""
        return UltralyticsDetectionResult(
            image_path=image_path,
            success=False,
            has_bench=False,
            bench_count=0,
            max_confidence=0.0,
            bench_detections=[],
            full_response=UltralyticsApiResponse(images=[]),
            model_url=str(self.local_model_path) if self.use_local else self.model_url or "unknown",
            confidence_threshold=self.confidence_threshold,
            iou_threshold=self.iou_threshold,
            image_size=self.image_size,
            inference_mode='local' if self.use_local else 'api',
            error=error
        )
    
    def batch_detect_benches(self, image_paths: List[str]) -> List[UltralyticsDetectionResult]:
        """
        Detect benches in multiple images.
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            List of UltralyticsDetectionResult objects
        """
        logger.info(f"Batch analyzing {len(image_paths)} images for benches with Ultralytics")
        
        results = []
        successful_detections = 0
        benches_found = 0
        total_bench_count = 0
        
        for i, image_path in enumerate(image_paths, 1):
            logger.debug(f"Processing image {i}/{len(image_paths)}: {image_path}")
            
            result = self.detect_benches_in_image(image_path)
            results.append(result)
            
            if result.success:
                successful_detections += 1
                if result.has_bench:
                    benches_found += 1
                    total_bench_count += result.bench_count
        
        logger.info(f"Batch analysis complete - {successful_detections}/{len(image_paths)} successful, "
                   f"{benches_found} images with benches detected, {total_bench_count} total bench instances")
        
        return results
    
    def get_model_info(self) -> Optional[Dict]:
        """
        Get information about the Ultralytics model.
        
        Returns:
            Model information dictionary or None if unavailable
        """
        try:
            return {
                'model_url': str(self.local_model_path) if self.use_local else self.model_url,
                'confidence_threshold': self.confidence_threshold,
                'iou_threshold': self.iou_threshold,
                'image_size': self.image_size,
                'supports_segmentation': True,
                'mode': 'local' if self.use_local else 'api',
                'api_endpoint': self.inference_url if not self.use_local else None
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

    def detect_benches_with_class_filter(self, image_path: str, target_classes: List[str] | None = None) -> UltralyticsDetectionResult:
        """
        Detect benches in an image with specific class filtering.
        
        Args:
            image_path: Path to the image file
            target_classes: List of class names to look for (defaults to bench-related terms)
            
        Returns:
            UltralyticsDetectionResult with filtered detection results
        """
        if target_classes is None:
            target_classes = ['bench', 'seat', 'chair']  # Default bench-related classes
            
        result = self.detect_benches_in_image(image_path)
        
        if not result.success:
            return result
        
        # Filter detections to only include target classes
        filtered_detections = []
        for detection in result.bench_detections:
            class_name = detection.class_name.lower()
            if any(target_class in class_name for target_class in target_classes):
                filtered_detections.append(detection)
        
        # Create new result with filtered detections
        filtered_result = UltralyticsDetectionResult(
            image_path=result.image_path,
            success=result.success,
            has_bench=len(filtered_detections) > 0,
            bench_count=len(filtered_detections),
            max_confidence=max((d.confidence for d in filtered_detections), default=0.0),
            bench_detections=filtered_detections,
            full_response=result.full_response,
            model_url=result.model_url,
            confidence_threshold=result.confidence_threshold,
            iou_threshold=result.iou_threshold,
            image_size=result.image_size,
            inference_mode=result.inference_mode,
            inference_time=result.inference_time,
            preprocess_time=result.preprocess_time,
            postprocess_time=result.postprocess_time,
            error=result.error
        )
        
        return filtered_result