"""
Configuration module for bench finder application.
Manages API keys and application settings.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API Keys - These should be set as environment variables
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
ROBOFLOW_API_KEY = os.getenv('ROBOFLOW_API_KEY')
ULTRALYTICS_API_KEY = os.getenv('ULTRALYTICS_API_KEY')

# Application settings
SEARCH_RADIUS_METERS = 500  # Radius to search for benches around the starting point
STREETVIEW_SIZE = "640x640"  # Size of street view images
STREETVIEW_FOV = 90  # Field of view for street view images
STREETVIEW_HEADINGS = [0, 90, 180, 270]  # Headings to capture images from

# Roboflow model settings
ROBOFLOW_MODEL_ID = "bench-annotater/1"
ROBOFLOW_CONFIDENCE_THRESHOLD = 0.5
ROBOFLOW_HIGH_CONFIDENCE_THRESHOLD = 0.90  # Stop capturing more images when this confidence is reached

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
DETECTION_BACKEND = os.getenv('DETECTION_BACKEND', 'roboflow').lower()  # 'roboflow' or 'ultralytics'

# Database settings
DATABASE_PATH = "data/benches.db"
IMAGES_DIR = "images"

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
    if DETECTION_BACKEND not in ['roboflow', 'ultralytics']:
        errors.append(f"DETECTION_BACKEND must be 'roboflow' or 'ultralytics', got: {DETECTION_BACKEND}")
    
    # Validate backend-specific API keys
    if DETECTION_BACKEND == 'roboflow' and not ROBOFLOW_API_KEY:
        errors.append("ROBOFLOW_API_KEY environment variable is required when using Roboflow backend")
    
    if DETECTION_BACKEND == 'ultralytics' and not ULTRALYTICS_API_KEY:
        errors.append("ULTRALYTICS_API_KEY environment variable is required when using Ultralytics backend")
    
    if errors:
        raise ValueError("Configuration errors:\n" + "\n".join(f"- {error}" for error in errors))
    
    return True