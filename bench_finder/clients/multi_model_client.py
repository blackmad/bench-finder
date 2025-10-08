"""
Multi-model detection client that implements fallback detection logic.
Tries Ultralytics first, then falls back to multiple Roboflow models.
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .ultralytics_client import UltralyticsClient
from .roboflow_client import RoboflowClient
from ..models.schemas import StandardDetectionResult, DetectionItem, BoundingBox
from ..config import (
    ROBOFLOW_MODELS, 
    ROBOFLOW_API_KEY,
    ULTRALYTICS_API_KEY,
    ULTRALYTICS_USE_LOCAL
)

logger = logging.getLogger(__name__)


def _convert_ultralytics_to_standard(ultralytics_result: Dict, image_path: str) -> StandardDetectionResult:
    """Convert Ultralytics result to StandardDetectionResult."""
    detections = []
    
    if ultralytics_result.get('has_bench') and ultralytics_result.get('bench_detections'):
        for detection in ultralytics_result['bench_detections']:
            if 'bbox' in detection:
                bbox_data = detection['bbox']
                # Ultralytics bbox format: [x1, y1, x2, y2]
                bbox = BoundingBox(
                    x1=bbox_data[0],
                    y1=bbox_data[1], 
                    x2=bbox_data[2],
                    y2=bbox_data[3]
                )
                
                detection_item = DetectionItem(
                    confidence=detection.get('confidence', 0.0),
                    bbox=bbox,
                    class_name="bench",
                    segmentation=detection.get('masks')  # Keep segmentation if available
                )
                detections.append(detection_item)
    
    return StandardDetectionResult(
        image_path=image_path,
        success=ultralytics_result.get('success', False),
        has_bench=ultralytics_result.get('has_bench', False),
        bench_count=ultralytics_result.get('bench_count', 0),
        max_confidence=ultralytics_result.get('max_confidence', 0.0),
        detections=detections,
        winning_backend='ultralytics',
        winning_model='ultralytics',
        error=ultralytics_result.get('error')
    )


def _convert_roboflow_to_standard(roboflow_result: Dict, image_path: str) -> StandardDetectionResult:
    """Convert Roboflow result to StandardDetectionResult."""
    detections = []
    
    if roboflow_result.get('has_bench') and roboflow_result.get('detections'):
        for detection in roboflow_result['detections']:
            # Roboflow format: center coordinates + width/height
            if 'x' in detection and 'y' in detection and 'width' in detection and 'height' in detection:
                x_center = detection['x']
                y_center = detection['y']
                width = detection['width']
                height = detection['height']
                
                # Convert to corner coordinates
                x1 = x_center - width / 2
                y1 = y_center - height / 2
                x2 = x_center + width / 2
                y2 = y_center + height / 2
                
                bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)
                
                detection_item = DetectionItem(
                    confidence=detection.get('confidence', 0.0),
                    bbox=bbox,
                    class_name=detection.get('class', 'bench')
                )
                detections.append(detection_item)
    
    return StandardDetectionResult(
        image_path=image_path,
        success=roboflow_result.get('success', False),
        has_bench=roboflow_result.get('has_bench', False),
        bench_count=roboflow_result.get('bench_count', 0),
        max_confidence=roboflow_result.get('max_confidence', 0.0),
        detections=detections,
        winning_backend='roboflow',
        winning_model=roboflow_result.get('winning_model', 'unknown'),
        error=roboflow_result.get('error')
    )


@dataclass
class DetectionAttempt:
    """Represents a single model detection attempt."""
    model_type: str  # 'ultralytics', 'roboflow'
    model_id: str
    success: bool
    has_bench: bool
    confidence: float
    error: Optional[str] = None


class MultiModelRoboflowClient:
    """Enhanced Roboflow client that tries multiple models."""
    
    def __init__(self, models_config: List[Dict]):
        """Initialize with multiple model configurations.
        
        Args:
            models_config: List of model configuration dictionaries
        """
        if not ROBOFLOW_API_KEY:
            raise ValueError("ROBOFLOW_API_KEY is required for Roboflow models")
        
        # Sort models by priority (lower number = higher priority)
        self.models_config = sorted(models_config, key=lambda x: x.get('priority', 999))
        self.api_key = ROBOFLOW_API_KEY
        logger.info(f"Initialized MultiModelRoboflowClient with {len(self.models_config)} models")
        
        # Log model order
        for i, model in enumerate(self.models_config, 1):
            logger.info(f"  {i}. {model['name']} ({model['id']}) - threshold: {model['confidence_threshold']}")
    
    def detect_benches_in_image(self, image_path: str) -> Tuple[Dict, List[DetectionAttempt]]:
        """
        Try detecting benches using multiple Roboflow models until one succeeds.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Tuple of (best_result, all_attempts)
        """
        attempts = []
        best_result = None
        
        logger.debug(f"Trying {len(self.models_config)} Roboflow models for {image_path}")
        
        for model_config in self.models_config:
            model_id = model_config['id']
            model_name = model_config['name']
            confidence_threshold = model_config['confidence_threshold']
            
            logger.debug(f"Trying Roboflow model: {model_name} ({model_id})")
            
            try:
                # Create a temporary RoboflowClient for this specific model
                temp_client = RoboflowClient(model_id=model_id)
                temp_client.confidence_threshold = confidence_threshold
                
                # Attempt detection
                result = temp_client.detect_benches_in_image(image_path)
                
                # Record the attempt
                attempt = DetectionAttempt(
                    model_type='roboflow',
                    model_id=model_id,
                    success=result.success,
                    has_bench=result.has_bench,
                    confidence=result.max_confidence,
                    error=result.error
                )
                attempts.append(attempt)
                
                # If this model detected a bench, use it as the result
                if result.success and result.has_bench:
                    logger.info(f"✅ Bench detected by {model_name}: confidence {result.max_confidence:.2f}")
                    # Convert Pydantic model to dict and add metadata
                    best_result = result.model_dump()
                    best_result['winning_model'] = model_name
                    best_result['winning_model_id'] = model_id
                    best_result['model_attempts'] = len(attempts)
                    break
                elif result.success:
                    logger.debug(f"❌ No bench detected by {model_name}")
                else:
                    logger.debug(f"❌ {model_name} failed: {result.error or 'Unknown error'}")
                    
            except Exception as e:
                logger.error(f"Error with Roboflow model {model_name} - id {model_id}: {e}")
                attempt = DetectionAttempt(
                    model_type='roboflow',
                    model_id=model_id,
                    success=False,
                    has_bench=False,
                    confidence=0.0,
                    error=str(e)
                )
                attempts.append(attempt)
                continue
        
        # If no model detected a bench, return the last result or create an error result
        if best_result is None:
            if attempts:
                # Use the last attempt's result, but mark it as the "best" available
                last_attempt = attempts[-1]
                best_result = {
                    'image_path': image_path,
                    'success': False,
                    'has_bench': False,
                    'bench_count': 0,
                    'max_confidence': 0.0,
                    'detections': [],
                    'error': f"No bench detected by any of {len(self.models_config)} Roboflow models",
                    'winning_model': 'none',
                    'winning_model_id': 'none',
                    'model_attempts': len(attempts)
                }
            else:
                best_result = {
                    'image_path': image_path,
                    'success': False,
                    'has_bench': False,
                    'bench_count': 0,
                    'max_confidence': 0.0,
                    'detections': [],
                    'error': "All Roboflow models failed",
                    'winning_model': 'none',
                    'winning_model_id': 'none',
                    'model_attempts': 0
                }
        
        return best_result, attempts


class MultiModelDetectionClient:
    """
    Multi-model detection client that implements fallback logic:
    1. Try Ultralytics first
    2. If no bench detected, try multiple Roboflow models in priority order
    3. Stop as soon as any model detects a bench
    """
    
    def __init__(self, enable_ultralytics: bool = True, enable_roboflow_fallback: bool = True):
        """
        Initialize the multi-model detection client.
        
        Args:
            enable_ultralytics: Whether to try Ultralytics first
            enable_roboflow_fallback: Whether to use Roboflow fallback models
        """
        self.enable_ultralytics = enable_ultralytics
        self.enable_roboflow_fallback = enable_roboflow_fallback
        self.all_attempts: List[DetectionAttempt] = []  # Track all detection attempts for analysis
        
        # Initialize Ultralytics client if enabled and API key available
        self.ultralytics_client = None
        if enable_ultralytics:
            try:
                if ULTRALYTICS_API_KEY or ULTRALYTICS_USE_LOCAL:
                    self.ultralytics_client = UltralyticsClient()
                    logger.info("✅ Ultralytics client initialized")
                else:
                    logger.warning("⚠️  Ultralytics disabled: no API key or local inference not enabled")
                    self.enable_ultralytics = False
            except Exception as e:
                logger.error(f"❌ Failed to initialize Ultralytics client: {e}")
                self.enable_ultralytics = False
        
        # Initialize Roboflow fallback client if enabled
        self.roboflow_client = None
        if enable_roboflow_fallback:
            try:
                if ROBOFLOW_API_KEY and ROBOFLOW_MODELS:
                    self.roboflow_client = MultiModelRoboflowClient(ROBOFLOW_MODELS)
                    logger.info("✅ Multi-model Roboflow client initialized")
                else:
                    logger.warning("⚠️  Roboflow fallback disabled: no API key or models configured")
                    self.enable_roboflow_fallback = False
            except Exception as e:
                logger.error(f"❌ Failed to initialize Roboflow client: {e}")
                self.enable_roboflow_fallback = False
        
        if not self.enable_ultralytics and not self.enable_roboflow_fallback:
            raise ValueError("At least one detection backend must be enabled and properly configured")
        
        logger.info(f"MultiModelDetectionClient ready - Ultralytics: {self.enable_ultralytics}, Roboflow: {self.enable_roboflow_fallback}")
    
    def detect_benches_in_image(self, image_path: str) -> StandardDetectionResult:
        """
        Detect benches using fallback logic: Ultralytics first, then Roboflow models.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            StandardDetectionResult with enhanced metadata
        """
        detection_attempts = []
        final_result = None
        
        logger.debug(f"🔍 Starting multi-model detection for {image_path}")
        
        # Step 1: Try Ultralytics first
        if self.enable_ultralytics and self.ultralytics_client:
            logger.debug("🚀 Trying Ultralytics first...")
            try:
                ultralytics_result_dict: Dict = self.ultralytics_client.detect_benches_in_image(image_path)
                
                attempt = DetectionAttempt(
                    model_type='ultralytics',
                    model_id='ultralytics',
                    success=ultralytics_result_dict.get('success', False),
                    has_bench=ultralytics_result_dict.get('has_bench', False),
                    confidence=ultralytics_result_dict.get('max_confidence', 0.0),
                    error=ultralytics_result_dict.get('error')
                )
                detection_attempts.append(attempt)
                
                if ultralytics_result_dict.get('success') and ultralytics_result_dict.get('has_bench'):
                    logger.info(f"✅ Ultralytics detected bench: confidence {ultralytics_result_dict.get('max_confidence', 0):.2f}")
                    # Convert to standard format
                    final_result = _convert_ultralytics_to_standard(ultralytics_result_dict, image_path)
                    final_result.fallback_used = False
                    final_result.total_attempts = 1
                elif ultralytics_result_dict.get('success'):
                    logger.debug("❌ Ultralytics: No bench detected, trying fallback models...")
                else:
                    logger.debug(f"❌ Ultralytics failed: {ultralytics_result_dict.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"❌ Ultralytics detection failed: {e}")
                attempt = DetectionAttempt(
                    model_type='ultralytics',
                    model_id='ultralytics',
                    success=False,
                    has_bench=False,
                    confidence=0.0,
                    error=str(e)
                )
                detection_attempts.append(attempt)
        
        # Step 2: If Ultralytics didn't detect a bench, try Roboflow fallback models
        if final_result is None and self.enable_roboflow_fallback and self.roboflow_client:
            logger.debug("🔄 Falling back to Roboflow models...")
            try:
                roboflow_result_dict, roboflow_attempts = self.roboflow_client.detect_benches_in_image(image_path)
                detection_attempts.extend(roboflow_attempts)
                
                if roboflow_result_dict.get('success') and roboflow_result_dict.get('has_bench'):
                    logger.info(f"✅ Fallback successful: {roboflow_result_dict.get('winning_model')} detected bench")
                    # Convert to standard format
                    final_result = _convert_roboflow_to_standard(roboflow_result_dict, image_path)
                    final_result.fallback_used = True
                    final_result.total_attempts = len(detection_attempts)
                else:
                    logger.debug("❌ All fallback models failed to detect bench")
                    
            except Exception as e:
                logger.error(f"❌ Roboflow fallback failed: {e}")
        
        # Step 3: If no model detected a bench, create a comprehensive failure result
        if final_result is None:
            logger.debug("❌ All detection models failed")
            final_result = StandardDetectionResult(
                image_path=image_path,
                success=False,
                has_bench=False,
                bench_count=0,
                max_confidence=0.0,
                detections=[],
                winning_backend='none',
                winning_model='none',
                fallback_used=len(detection_attempts) > 1,
                total_attempts=len(detection_attempts),
                error=f"No bench detected by any model ({len(detection_attempts)} attempts)"
            )
        
        # Add detection attempt metadata to the result
        final_result.detection_attempts = [
            {
                'model_type': attempt.model_type,
                'model_id': attempt.model_id,
                'success': attempt.success,
                'has_bench': attempt.has_bench,
                'confidence': attempt.confidence,
                'error': attempt.error
            }
            for attempt in detection_attempts
        ]
        
        # Store attempts for analysis
        self.all_attempts.extend(detection_attempts)
        
        return final_result
    
    def get_detection_stats(self) -> Dict:
        """Get statistics about detection attempts across all processed images."""
        if not self.all_attempts:
            return {'total_attempts': 0, 'no_data': True}
        
        stats: Dict[str, float | int] = {
            'total_attempts': len(self.all_attempts),
            'ultralytics_attempts': len([a for a in self.all_attempts if a.model_type == 'ultralytics']),
            'roboflow_attempts': len([a for a in self.all_attempts if a.model_type == 'roboflow']),
            'successful_attempts': len([a for a in self.all_attempts if a.success and a.has_bench]),
            'ultralytics_successes': len([a for a in self.all_attempts if a.model_type == 'ultralytics' and a.success and a.has_bench]),
            'roboflow_successes': len([a for a in self.all_attempts if a.model_type == 'roboflow' and a.success and a.has_bench])
        }
        
        # Calculate success rates
        if stats['ultralytics_attempts'] > 0:
            stats['ultralytics_success_rate'] = float(stats['ultralytics_successes']) / float(stats['ultralytics_attempts'])
        
        if stats['roboflow_attempts'] > 0:
            stats['roboflow_success_rate'] = float(stats['roboflow_successes']) / float(stats['roboflow_attempts'])
        
        return stats
    
    def reset_stats(self):
        """Reset detection attempt statistics."""
        self.all_attempts = []