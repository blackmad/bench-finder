# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys: GOOGLE_MAPS_API_KEY, ROBOFLOW_API_KEY, ULTRALYTICS_API_KEY
```

### Running the Application
```bash
# Basic bench finding
./bench_finder.py "Central Park, New York"

# With custom radius
./bench_finder.py "Golden Gate Park, San Francisco" --radius 1000

# With debug logging
./bench_finder.py "Hyde Park, London" --log-level DEBUG

# Start web server (port 8866)
python web_server.py
```

### Testing and Development
```bash
# Run specific tests
python test_mapillary.py
python test_ultralytics_modes.py
python test_web_ui.py
python test_fixed_query.py

# Debug database queries
python debug_query.py

# Database migration
python migrate_database.py

# Example usage with specific backends
python example_ultralytics_usage.py
```

### Database Operations
```bash
# SQLite database location
ls -la data/benches.db

# Connect to database for manual queries
sqlite3 data/benches.db
```

## Code Architecture

### Core Pipeline (bench_finder.py)
The main `BenchFinder` class orchestrates a 5-step pipeline:
1. **Geocoding**: Convert location queries to coordinates using Google Maps API
2. **Discovery**: Find nearby benches using OpenStreetMap Overpass API  
3. **Image Capture**: Take Street View images at 4 headings (0°, 90°, 180°, 270°)
4. **Detection**: Use AI models (Roboflow or Ultralytics) to detect benches in images
5. **Storage**: Save all results to SQLite database with full metadata

### Detection Backends
The system supports two AI detection backends configured via `DETECTION_BACKEND`:
- **Roboflow**: Cloud-based bench detection using `bench-annotater/1` model
- **Ultralytics**: YOLO-based segmentation with local or cloud inference

### Database Architecture (models.py)
SQLAlchemy ORM with five main tables:
- **searches**: Query metadata and status tracking
- **benches**: Bench locations from OSM or Mapillary sources
- **images**: Street View image capture results with headings
- **detections**: Roboflow detection results with confidence scores
- **ultralytics_detections**: Segmentation data with full response metadata

### Web Interface (web_server.py)
Flask web server with API endpoints:
- `/api/benches`: Paginated bench data with confidence filtering
- `/api/searches`: Available search starting points
- `/api/image/<id>/segmentation`: Segmentation overlay data
- `/api/mapillary/search`: Mapillary API integration for crowd-sourced detections

### API Client Architecture
Modular client design with retry logic and error handling:
- `geocoder.py`: Google Geocoding API wrapper
- `overpass_client.py`: OpenStreetMap Overpass API client
- `streetview.py`: Google Street View Static API client
- `roboflow_client.py`: Roboflow AI detection client
- `ultralytics_client.py`: Ultralytics YOLO client with segmentation support
- `mapillary_client.py`: Mapillary API for crowd-sourced bench detections

### Mapillary Integration (mapillary_service.py)
The `MapillaryBenchService` integrates crowd-sourced bench detections:
- Searches Mapillary's detection API for bench objects
- Stores detections as benches with `source='mapillary'`
- Provides unified interface with OSM-based benches
- Includes segmentation geometry data from detections

## Key Configuration

### Environment Variables (.env)
Required API keys for external services:
- `GOOGLE_MAPS_API_KEY`: Geocoding and Street View access
- `ROBOFLOW_API_KEY`: AI bench detection (if using Roboflow backend)
- `ULTRALYTICS_API_KEY`: YOLO detection service (if using Ultralytics backend)
- `DETECTION_BACKEND`: Choose 'roboflow' or 'ultralytics'
- `ULTRALYTICS_USE_LOCAL`: Enable local YOLO inference
- `MAPILLARY_ACCESS_TOKEN`: For Mapillary crowd-sourced detection integration

### Core Settings (config.py)
- `SEARCH_RADIUS_METERS`: Default search radius (500m)
- `STREETVIEW_HEADINGS`: Camera angles for multi-angle capture [0, 90, 180, 270]
- `ROBOFLOW_CONFIDENCE_THRESHOLD`: Minimum detection confidence (0.5)
- `ULTRALYTICS_CONFIDENCE_THRESHOLD`: YOLO detection threshold (0.25)
- `DATABASE_PATH`: SQLite database location ("data/benches.db")

## Data Flow Patterns

### Error Handling Strategy
- Retry logic with exponential backoff for API failures
- Graceful degradation: continue processing other benches if one fails
- Comprehensive error logging with context preservation
- Failed operations stored in database for analysis

### Progress Tracking
- Real-time progress reporting for long operations
- Processing statistics: images captured, detections performed, confidence scores
- Status tracking: pending → completed/failed search states

### Dual Detection Backend Support
When working with detection logic:
- Check `self.detection_backend` to determine active backend
- Roboflow results stored in `detections` table
- Ultralytics results stored in `ultralytics_detections` table with full segmentation data
- Backend selection affects database storage, API calls, and result processing

### Multi-Source Bench Data
The system handles benches from multiple sources:
- **OSM benches**: From OpenStreetMap via Overpass API queries
- **Mapillary benches**: From crowd-sourced object detection data
- Source tracking via `bench.source` field enables filtering and statistics
- External ID tracking for deduplication and reference management