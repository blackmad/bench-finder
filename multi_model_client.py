"""
Multi-model detection client that implements fallback detection logic.
Tries Ultralytics first, then falls back to multiple Roboflow models.
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from ultralytics_client import UltralyticsClient
from roboflow_client import RoboflowClient
from config import (
    ROBOFLOW_MODELS, 
    ROBOFLOW_API_KEY,
    ULTRALYTICS_API_KEY,
    ULTRALYTICS_USE_LOCAL
)

logger = logging.getLogger(__name__)


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
                temp_client = RoboflowClient()
                temp_client.model_id = model_id
                temp_client.confidence_threshold = confidence_threshold
                temp_client.base_url = f"https://detect.roboflow.com/{model_id}"
                
                # Attempt detection
                result = temp_client.detect_benches_in_image(image_path)
                
                # Record the attempt
                attempt = DetectionAttempt(
                    model_type='roboflow',
                    model_id=model_id,
                    success=result.get('success', False),
                    has_bench=result.get('has_bench', False),
                    confidence=result.get('max_confidence', 0.0),
                    error=result.get('error')
                )
                attempts.append(attempt)
                
                # If this model detected a bench, use it as the result
                if result.get('success') and result.get('has_bench'):
                    logger.info(f"✅ Bench detected by {model_name}: confidence {result.get('max_confidence', 0):.2f}")
                    best_result = result
                    # Add model information to the result
                    best_result['winning_model'] = model_name
                    best_result['winning_model_id'] = model_id
                    best_result['model_attempts'] = len(attempts)
                    break
                elif result.get('success'):
                    logger.debug(f"❌ No bench detected by {model_name}")
                else:
                    logger.debug(f"❌ {model_name} failed: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                logger.error(f"Error with Roboflow model {model_name}: {e}")
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
        self.all_attempts = []  # Track all detection attempts for analysis
        
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
    
    def detect_benches_in_image(self, image_path: str) -> Dict:
        """
        Detect benches using fallback logic: Ultralytics first, then Roboflow models.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Detection result dictionary with enhanced metadata
        """
        detection_attempts = []
        final_result = None
        
        logger.debug(f"🔍 Starting multi-model detection for {image_path}")
        
        # Step 1: Try Ultralytics first
        if self.enable_ultralytics and self.ultralytics_client:
            logger.debug("🚀 Trying Ultralytics first...")
            try:
                ultralytics_result = self.ultralytics_client.detect_benches_in_image(image_path)
                
                attempt = DetectionAttempt(
                    model_type='ultralytics',
                    model_id='ultralytics',
                    success=ultralytics_result.get('success', False),
                    has_bench=ultralytics_result.get('has_bench', False),
                    confidence=ultralytics_result.get('max_confidence', 0.0),
                    error=ultralytics_result.get('error')
                )
                detection_attempts.append(attempt)
                
                if ultralytics_result.get('success') and ultralytics_result.get('has_bench'):
                    logger.info(f"✅ Ultralytics detected bench: confidence {ultralytics_result.get('max_confidence', 0):.2f}")
                    final_result = ultralytics_result
                    final_result['winning_backend'] = 'ultralytics'
                    final_result['winning_model'] = 'ultralytics'
                    final_result['fallback_used'] = False
                    final_result['total_attempts'] = 1
                elif ultralytics_result.get('success'):
                    logger.debug("❌ Ultralytics: No bench detected, trying fallback models...")
                else:
                    logger.debug(f"❌ Ultralytics failed: {ultralytics_result.get('error', 'Unknown error')}")
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
                roboflow_result, roboflow_attempts = self.roboflow_client.detect_benches_in_image(image_path)
                detection_attempts.extend(roboflow_attempts)
                
                if roboflow_result.get('success') and roboflow_result.get('has_bench'):
                    logger.info(f"✅ Fallback successful: {roboflow_result.get('winning_model')} detected bench")
                    final_result = roboflow_result
                    final_result['winning_backend'] = 'roboflow'
                    final_result['fallback_used'] = True
                    final_result['total_attempts'] = len(detection_attempts)
                else:
                    logger.debug("❌ All fallback models failed to detect bench")
                    
            except Exception as e:
                logger.error(f"❌ Roboflow fallback failed: {e}")
        
        # Step 3: If no model detected a bench, create a comprehensive failure result
        if final_result is None:
            logger.debug("❌ All detection models failed")
            final_result = {
                'image_path': image_path,
                'success': False,
                'has_bench': False,
                'bench_count': 0,
                'max_confidence': 0.0,
                'detections': [],
                'bench_detections': [],
                'error': f"No bench detected by any model ({len(detection_attempts)} attempts)",
                'winning_backend': 'none',
                'winning_model': 'none',
                'fallback_used': len(detection_attempts) > 1,
                'total_attempts': len(detection_attempts)
            }
        
        # Add detection attempt metadata to the result
        final_result['detection_attempts'] = [
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
        
        stats = {
            'total_attempts': len(self.all_attempts),
            'ultralytics_attempts': len([a for a in self.all_attempts if a.model_type == 'ultralytics']),
            'roboflow_attempts': len([a for a in self.all_attempts if a.model_type == 'roboflow']),
            'successful_attempts': len([a for a in self.all_attempts if a.success and a.has_bench]),
            'ultralytics_successes': len([a for a in self.all_attempts if a.model_type == 'ultralytics' and a.success and a.has_bench]),
            'roboflow_successes': len([a for a in self.all_attempts if a.model_type == 'roboflow' and a.success and a.has_bench])
        }
        
        # Calculate success rates
        if stats['ultralytics_attempts'] > 0:
            stats['ultralytics_success_rate'] = stats['ultralytics_successes'] / stats['ultralytics_attempts']
        
        if stats['roboflow_attempts'] > 0:
            stats['roboflow_success_rate'] = stats['roboflow_successes'] / stats['roboflow_attempts']
        
        return stats
    
    def reset_stats(self):
        """Reset detection attempt statistics."""
        self.all_attempts = []