# Bench Finder

An offline Python processing script that finds benches using multiple APIs and computer vision:

1. **Geocodes** a search query using Google Maps API
2. **Finds benches** near that location using OpenStreetMap Overpass API
3. **Captures Street View images** at multiple headings (0°, 90°, 180°, 270°) for each bench
4. **Detects benches** in images using Roboflow's `bench-annotater/1` model
5. **Stores results** in a SQLite database

## Features

- 🗺️ **Geocoding**: Convert addresses/locations to coordinates
- 🪑 **Bench Discovery**: Find benches using OpenStreetMap data
- 📸 **Street View Capture**: Multi-angle image capture for each bench
- 🤖 **AI Detection**: Computer vision bench detection with confidence scores
- 💾 **Data Storage**: Comprehensive SQLite database with full result tracking
- 🔄 **Retry Logic**: Robust error handling with exponential backoff
- 📊 **Progress Tracking**: Real-time progress reporting for long operations
- 🛠️ **Modular Design**: Clean separation of concerns for easy extension

## Project Structure

```
bench_finder/
├── bench_finder/          # Main Python package
│   ├── cli.py            # CLI interface using Typer
│   ├── config.py         # Configuration and settings
│   ├── core/             # Core functionality
│   │   ├── geocoder.py   # Google Geocoding API client
│   │   ├── streetview.py # Google Street View Static API client
│   │   └── clustering.py # Bench clustering algorithms
│   ├── clients/          # API client implementations
│   │   ├── overpass_client.py    # OpenStreetMap Overpass API
│   │   ├── roboflow_client.py    # Roboflow AI detection
│   │   ├── mapillary_client.py   # Mapillary API client
│   │   └── ultralytics_client.py # Ultralytics YOLO models
│   ├── generators/       # Data generation services
│   │   ├── bench_generator.py    # Base bench generator
│   │   ├── overpass.py           # OSM bench generation
│   │   └── mapillary.py          # Mapillary bench generation
│   ├── models/           # Data models and schemas
│   │   ├── unified_models.py     # Unified data models
│   │   ├── overpass_models.py    # OSM-specific models
│   │   └── mapillary_models.py   # Mapillary-specific models
│   ├── services/         # Business logic services
│   │   ├── database.py           # Database operations
│   │   ├── image_download_service.py # Image downloading
│   │   └── clustered_bench_service.py # Clustering service
│   └── tools/            # Utility tools
│       └── bench_detection_cli.py # Detection testing CLI
├── api/                  # FastAPI web server
│   ├── fastapi_server.py # Main FastAPI application
│   └── api_models.py     # API request/response models
├── frontend/             # React TypeScript frontend
│   ├── src/              # React source code
│   ├── package.json      # Node.js dependencies
│   └── vite.config.ts    # Vite configuration
├── tools/                # Command-line tools
│   ├── fastapi_cli.py    # FastAPI testing CLI
│   └── unified_bench_search_cli.py # Unified search CLI
├── bin/                  # Executable scripts
│   ├── bench_finder      # Main CLI entry point
│   └── start_fastapi     # FastAPI server startup
├── pyproject.toml        # Modern Python project configuration
├── Makefile             # Development commands
├── setup-dev.sh         # Development environment setup
├── data/                # Database storage directory
├── images/              # Captured and downloaded images
└── docs/                # Documentation
    └── README.md        # This file
```

## Setup

### Modern Development Setup (Recommended)

For development, we recommend using the modern Python tooling:

```bash
# One-command setup
./setup-dev.sh

# Or manual setup
uv sync --dev
uv run pre-commit install
```

This will:
- Install [uv](https://docs.astral.sh/uv/) for fast package management
- Set up a virtual environment with all dependencies
- Configure [Ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Install pre-commit hooks for code quality

See [DEVELOPMENT.md](../DEVELOPMENT.md) for detailed development setup instructions.

### Available Commands

```bash
# Development workflow
make help          # Show all available commands
make dev           # Complete development workflow
make quick         # Quick development cycle
make all-checks    # Run all quality checks

# Application commands
make run-server    # Start FastAPI development server
make run-cli       # Run the bench-finder CLI
```

### 2. Configure API Keys

Copy the example environment file and add your API keys:

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```bash
# Google Maps API Key (for Geocoding and Street View)
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here

# Roboflow API Key
ROBOFLOW_API_KEY=your_roboflow_api_key_here
```

### 3. Required API Keys

#### Google Maps API Key
- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Enable the following APIs:
  - Geocoding API
  - Street View Static API
- Create an API key with these services enabled

#### Roboflow API Key
- Sign up at [Roboflow](https://roboflow.com/)
- Get access to the `bench-annotater/1` model
- Obtain your API key from your account settings

## Usage

### Basic Usage

Find benches near a location:

```bash
# Using the CLI entry point
./bin/bench_finder generate-candidates "Central Park, New York"

# Or using uv run
uv run bench-finder generate-candidates "Central Park, New York"
```

### Advanced Options

```bash
# Specify custom search radius (in meters)
./bin/bench_finder generate-candidates "Golden Gate Park, San Francisco" --radius 1000

# Enable debug logging
./bin/bench_finder generate-candidates "Hyde Park, London" --log-level DEBUG

# Show help
./bin/bench_finder --help
```

### Web Interface

Start the FastAPI web server:

```bash
# Development mode with auto-reload
make run-server

# Or directly with uvicorn
uv run uvicorn api.fastapi_server:app --reload --host 0.0.0.0 --port 8866
```

Access the web interface at http://localhost:8866

### Example Output

```
2024-01-15 10:30:15 - INFO - BenchFinder starting with query: 'Central Park, New York'
2024-01-15 10:30:16 - INFO - Geocoded 'Central Park, New York' to coordinates: 40.7829, -73.9654
2024-01-15 10:30:18 - INFO - Found 12 benches within 500m
2024-01-15 10:30:19 - INFO - Starting Processing benches - 12 items
2024-01-15 10:32:45 - INFO - Processing benches: 12/12 (100%) - 0.5 items/s
2024-01-15 10:32:45 - INFO - ✅ Successfully processed 12 benches
2024-01-15 10:32:45 - INFO - 📊 Summary:
2024-01-15 10:32:45 - INFO -    • Search ID: 1
2024-01-15 10:32:45 - INFO -    • Benches found: 12
2024-01-15 10:32:45 - INFO -    • Images captured: 45/48
2024-01-15 10:32:45 - INFO -    • Images with benches detected: 23
2024-01-15 10:32:45 - INFO -    • Best confidence: 0.87
```

## Configuration

The application can be configured by modifying `config.py` or setting environment variables:

### Key Settings

- `SEARCH_RADIUS_METERS`: Default search radius (500m)
- `STREETVIEW_HEADINGS`: Camera headings for image capture (0°, 90°, 180°, 270°)
- `ROBOFLOW_CONFIDENCE_THRESHOLD`: Minimum confidence for bench detection (0.5)
- `STREETVIEW_SIZE`: Size of captured images (640x640)

## Database Schema

The SQLite database stores comprehensive results across four main tables:

### Tables

1. **searches** - Search queries and metadata
2. **benches** - OSM bench data and coordinates
3. **images** - Street View image capture results
4. **detections** - AI detection results with confidence scores

### Sample Queries

```sql
-- Get all successful detections with high confidence
SELECT s.query, b.lat, b.lng, d.max_confidence, i.filepath
FROM searches s
JOIN benches b ON s.id = b.search_id
JOIN images i ON b.id = i.bench_id
JOIN detections d ON i.id = d.image_id
WHERE d.has_bench = 1 AND d.max_confidence > 0.8;

-- Search statistics
SELECT
    s.query,
    s.bench_count,
    COUNT(i.id) as total_images,
    SUM(d.has_bench) as detections,
    MAX(d.max_confidence) as best_confidence
FROM searches s
LEFT JOIN benches b ON s.id = b.search_id
LEFT JOIN images i ON b.id = i.bench_id
LEFT JOIN detections d ON i.id = d.image_id
GROUP BY s.id;
```

## Architecture

The application follows a modular architecture with clear separation of concerns:

### Core Components

- **BenchFinder**: Main orchestrator class
- **Geocoder**: Google Geocoding API wrapper
- **OverpassClient**: OpenStreetMap data fetching
- **StreetViewClient**: Google Street View image capture
- **RoboflowClient**: AI-powered bench detection
- **BenchDatabase**: SQLite data persistence

### Design Patterns

- **Retry Logic**: Exponential backoff for API failures
- **Progress Tracking**: User feedback for long operations
- **Error Handling**: Graceful degradation and detailed logging
- **Configuration Management**: Centralized settings and validation

## Extending the Project

### Adding New Data Sources

To add additional data sources (e.g., other OSM amenities):

1. Extend `overpass_client.py` with new query methods
2. Update database schema in `database.py`
3. Modify the processing pipeline in `bench_finder.py`

### Different AI Models

To use different Roboflow models:

1. Update `ROBOFLOW_MODEL_ID` in `config.py`
2. Modify detection logic in `roboflow_client.py` if needed
3. Adjust confidence thresholds as appropriate

### Web Integration

For web deployment:

1. Extract core logic from CLI interface
2. Add REST API endpoints using Flask/FastAPI
3. Implement async processing for long-running operations
4. Add result caching and pagination

## Troubleshooting

### Common Issues

**API Key Errors**
- Ensure `.env` file exists with valid API keys
- Check API key permissions and quotas
- Verify Google APIs are enabled in Cloud Console

**No Benches Found**
- Try increasing search radius with `--radius`
- Check if location has Street View coverage
- Verify geocoding worked correctly (check logs)

**Detection Issues**
- Ensure images are being captured successfully
- Check Roboflow API key and model access
- Review confidence threshold settings

**Database Issues**
- Check write permissions in the `data/` directory
- Verify SQLite installation
- Look for database lock errors in logs

### Debug Mode

Enable detailed logging to troubleshoot issues:

```bash
./bench_finder.py "Your Location" --log-level DEBUG
```

## Performance Considerations

### API Rate Limits

- Google Maps APIs have usage quotas
- Roboflow has monthly inference limits
- Consider implementing rate limiting for production use

### Optimization Tips

- Use smaller image sizes to reduce API costs
- Implement local caching for repeat queries
- Batch process multiple locations
- Consider parallel processing for image analysis

## License

This project is provided as-is for educational and research purposes. Please ensure you comply with all API terms of service:

- [Google Maps Platform Terms](https://cloud.google.com/maps-platform/terms/)
- [OpenStreetMap Copyright](https://www.openstreetmap.org/copyright)
- [Roboflow Terms](https://roboflow.com/terms)

## Contributing

Contributions welcome! Areas for improvement:

- Additional image sources (satellite, other street view providers)
- More sophisticated detection models
- Web interface and visualization
- Performance optimizations
- Extended database analytics

## Future Enhancements

Potential future features that could be added to this async web project:

- **Real-time Processing**: WebSocket updates for long-running operations
- **Map Visualization**: Interactive maps showing bench locations and detection results
- **Batch Processing**: Queue system for processing multiple locations
- **API Endpoints**: REST API for integration with other applications
- **Result Analytics**: Statistical analysis and reporting dashboard
- **User Management**: Multi-user support with saved searches
- **Export Functions**: CSV/JSON export of results
- **Mobile App**: React Native/Flutter mobile client# Test commit
