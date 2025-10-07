"""
Configuration module for bench finder application.
Manages API keys and application settings.
"""
import os
from dotenv import load_dotenv

# Import term_image conditionally to avoid issues when running in background
try:
    from term_image.image import ITerm2Image
    from term_image.utils import get_terminal_name_version
    
    # Force iTerm2 image support for warp
    if get_terminal_name_version()[0] == "warp":
        ITerm2Image.is_supported = lambda *_: True
except (ImportError, ValueError, OSError) as e:
    # This can happen when running in background without a proper terminal
    # or when term_image is not available
    pass

# Load environment variables from .env file
load_dotenv()

# API Keys - These should be set as environment variables
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
ROBOFLOW_API_KEY = os.getenv('ROBOFLOW_API_KEY')
ULTRALYTICS_API_KEY = os.getenv('ULTRALYTICS_API_KEY')
MAPILLARY_ACCESS_TOKEN = os.getenv('MAPILLARY_ACCESS_TOKEN')

# Supabase configuration
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

# Application settings
SEARCH_RADIUS_METERS = 500  # Radius to search for benches around the starting point
STREETVIEW_SIZE = "640x640"  # Size of street view images
STREETVIEW_FOV = 90  # Field of view for street view images
STREETVIEW_HEADINGS = [0, 90, 180, 270]  # Headings to capture images from

# Roboflow model settings
ROBOFLOW_MODEL_ID = "bench-annotater/1"  # Legacy single model support
ROBOFLOW_CONFIDENCE_THRESHOLD = 0.5
ROBOFLOW_HIGH_CONFIDENCE_THRESHOLD = 0.90  # Stop capturing more images when this confidence is reached

# Multiple Roboflow models for fallback detection
ROBOFLOW_MODELS = [
    {
        'id': 'streetview-benches-m4bc5/1', 
        'name': 'streetview-benches-m4bc5',
        'confidence_threshold': 0.5,      
        'priority': 5  # Higher priority = tried first
    }
    # {
    #     'id': 'other2-csmve/3',
    #     'name': 'other2-csmve',
    #     'confidence_threshold': 0.7,
    #     'priority': 10  # Higher priority = tried first
    # }
    # {
    #     'id': 'bench-detector/1',
    #     'name': 'bench-detector',
    #     'confidence_threshold': 0.4,
    #     'priority': 1  # Higher priority = tried first
    # },
    # {
    #     'id': 'bench-annotater/1', 
    #     'name': 'bench-annotator',
    #     'confidence_threshold': 0.5,
    #     'priority': 2
    # }
]

# Ultralytics model settings
ULTRALYTICS_MODEL_URL = "https://hub.ultralytics.com/models/LANJV1QBekDh5wGntsli"
ULTRALYTICS_CONFIDENCE_THRESHOLD = 0.25
ULTRALYTICS_IOU_THRESHOLD = 0.45
ULTRALYTICS_IMAGE_SIZE = 640

# Ultralytics local inference settings
ULTRALYTICS_USE_LOCAL = os.getenv('ULTRALYTICS_USE_LOCAL', 'true').lower() == 'true'
ULTRALYTICS_LOCAL_MODEL = os.getenv('ULTRALYTICS_LOCAL_MODEL', 'yolo11n-seg.pt')
ULTRALYTICS_MODELS_DIR = os.path.join(os.path.dirname(__file__), 'models')

# Detection backend selection
DETECTION_BACKEND = os.getenv('DETECTION_BACKEND', 'multi').lower()  # 'roboflow', 'ultralytics', or 'multi'

# Database settings
DATABASE_PATH = "data/benches.db"
IMAGES_DIR = "images"

# Mapillary settings
MAPILLARY_IMAGE_SIZE = 2048  # Download high-resolution images
MAPILLARY_DOWNLOAD_IMAGES = True  # Whether to download images when finding benches
MAPILLARY_MAX_CHUNK_SIZE_METERS = 400  # Maximum size (in meters) of each search chunk for API efficiency
MAPILLARY_API_LIMIT_PER_REQUEST = 1000  # Maximum number of images per API request

# Overpass API settings
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OVERPASS_TIMEOUT = 25  # seconds

# Logging settings
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

def validate_config():
    """Validate that all required configuration is present."""
    errors = []
    
    if not GOOGLE_MAPS_API_KEY:
        errors.append("GOOGLE_MAPS_API_KEY environment variable is required")
    
    # Validate backend selection
    valid_backends = ['roboflow', 'ultralytics', 'multi']
    if DETECTION_BACKEND not in valid_backends:
        errors.append(f"DETECTION_BACKEND must be one of {valid_backends}, got: {DETECTION_BACKEND}")
    
    # Validate API keys for backends that will be used
    # For multi-model setup, we need at least one working backend
    if DETECTION_BACKEND == 'roboflow' and not ROBOFLOW_API_KEY:
        errors.append("ROBOFLOW_API_KEY environment variable is required when using Roboflow backend")
    
    if DETECTION_BACKEND == 'ultralytics' and not ULTRALYTICS_API_KEY and not ULTRALYTICS_USE_LOCAL:
        errors.append("ULTRALYTICS_API_KEY environment variable is required when using Ultralytics backend (or enable ULTRALYTICS_USE_LOCAL)")
    
    # For multi-model backend, warn if some backends are not available but don't error
    if DETECTION_BACKEND == 'multi':
        available_backends = []
        
        if ROBOFLOW_API_KEY:
            available_backends.append('roboflow')
        else:
            import logging
            logging.getLogger(__name__).warning("ROBOFLOW_API_KEY not set - Roboflow models will not be available for fallback")
            
        if ULTRALYTICS_API_KEY or ULTRALYTICS_USE_LOCAL:
            available_backends.append('ultralytics')
        else:
            import logging
            logging.getLogger(__name__).warning("ULTRALYTICS_API_KEY not set and local inference disabled - Ultralytics will not be available")
        
        if not available_backends:
            errors.append("Multi-model backend requires at least one working detection backend (Roboflow or Ultralytics)")
        else:
            import logging
            logging.getLogger(__name__).info(f"Multi-model detection will use: {', '.join(available_backends)}")
    
    # Mapillary validation (optional - only warn if not set)
    if not MAPILLARY_ACCESS_TOKEN:
        import logging
        logging.getLogger(__name__).warning("MAPILLARY_ACCESS_TOKEN not set - Mapillary integration will not be available")
    
    # Supabase validation (optional for social features - only warn if not set)
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        import logging
        logging.getLogger(__name__).warning("SUPABASE_URL or SUPABASE_ANON_KEY not set - Social features will not be available")
    
    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(f"- {error}" for error in errors))
    
    return True
