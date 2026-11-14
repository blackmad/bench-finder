# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bench Finder is an AI-powered bench detection and mapping system that:
- Searches for bench locations using OSM Overpass API and Mapillary
- Captures street view images from Google Street View and Mapillary
- Detects benches in images using AI models (Roboflow, Ultralytics YOLO)
- Stores results in SQLite (local) or PostgreSQL (cloud)
- Provides a FastAPI backend and React TypeScript frontend

**Tech Stack:**
- Backend: Python 3.12, FastAPI, SQLModel/SQLAlchemy, Ultralytics, OpenCV
- Frontend: React 19, TypeScript, Vite, Styled Components, Leaflet maps
- Package Management: `uv` (Python), `npm` (Frontend)
- Code Quality: Ruff (linting/formatting), Biome (frontend), pre-commit hooks

## Development Commands

### Python Backend

**Always activate the Python virtual environment before running commands** (see .cursor/rules/always-activate-venv.mdc)

```bash
# Setup environment
uv sync --dev              # Install dependencies
make dev-install           # Install dev dependencies + pre-commit hooks
./setup-dev.sh             # Complete development setup

# Development workflow
make run-server            # Start FastAPI server (port 8866)
make lint                  # Run ruff linting
make lint-fix              # Run ruff with auto-fix
make format                # Format code with ruff
make test                  # Run pytest
make test-cov              # Run tests with coverage
make dev                   # Lint, format, and test

# CLI commands
uv run bench-finder generate-candidates "Location" --radius 500
uv run bench-finder --help

# Database migrations
make db-migrate            # Run database migrations
uv run python -m bench_finder.migrate
```

### Frontend

```bash
cd frontend

# Development
npm install                # Install dependencies
npm run dev                # Start dev server (port 5173)
npm run dev:full           # Start API + frontend together
npm run build              # Build for production
npm run lint               # Run ESLint
npm run lint:biome         # Run Biome linting
npm run lint:hooks         # Check React hooks rules
npm run format             # Format with Biome
npm run check              # Run all Biome checks
npm run check:fix          # Fix all Biome issues

# API client generation
npm run generate-api       # Generate API client from running server
```

### Running Tests

```bash
# Backend tests
uv run pytest                                    # All tests
uv run pytest tests/test_specific.py            # Single test file
uv run pytest -k test_name                       # Test by name
uv run pytest -m "not slow"                      # Skip slow tests
uv run pytest --cov=bench_finder --cov-report=html  # With coverage

# Frontend tests
cd frontend && npm test
```

## Architecture

### Data Flow Pipeline

1. **Search Phase** (`bench_finder/generators/`)
   - User provides location query → Geocoded via `bench_finder/core/geocoder.py`
   - Search record created in `searches` table
   - Bench candidates found via:
     - `generators/overpass.py`: OSM Overpass API queries
     - `generators/mapillary.py`: Mapillary image search with bench detections
   - Candidates stored in `bench_candidates` table with status tracking

2. **Image Download Phase** (`bench_finder/services/image_download_service.py`)
   - For each candidate, captures street view images via:
     - `core/streetview.py`: Google Street View Static API (4 headings: 0°, 90°, 180°, 270°)
     - Mapillary API: Downloads existing Mapillary images
   - Images stored locally in `images/` or uploaded to Firebase Storage
   - Metadata stored in `images` table

3. **Detection Phase** (`bench_finder/clients/`)
   - AI detection runs on each image via:
     - `clients/roboflow_client.py`: Roboflow bench detection models
     - `clients/ultralytics_client.py`: YOLO segmentation models (local or API)
     - `clients/multi_model_client.py`: Orchestrates multiple models with fallback
   - Detection results stored in `detections` and `detection_items` tables
   - Individual bounding boxes/polygons stored with confidence scores

4. **Processing Phase** (`bench_finder/services/database.py`)
   - High-confidence candidates (>0.5) promoted to `processed_benches` table
   - Representative images selected based on best detection confidence
   - Reverse geocoding performed to get street addresses
   - Status updated: `pending` → `image_download_done` → `detection_done`

### Database Architecture

**SQLModel ORM** with two database backends:
- **SQLite**: Local development (`data/benches.db`)
- **PostgreSQL**: Cloud deployment (Cloud SQL)

**Core Tables:**
- `searches`: Search queries and metadata
- `bench_candidates`: Potential bench locations from OSM/Mapillary
- `processed_benches`: Confirmed benches with high-confidence detections
- `images`: Street view image metadata (filepath, heading, source)
- `detections`: AI detection results (model_id, confidence, source)
- `detection_items`: Individual bounding boxes/polygons
- `bench_reports`: User reports of bad detections
- `missing_bench_reports`: User reports of missing benches
- `reverse_geocodes`: Cached street addresses
- `bench_ratings`: User ratings
- `bench_comments`: User comments
- `bench_user_status`: User-specific bench status (visited, favorited)

**Key Relationships:**
```
searches → bench_candidates → images → detections → detection_items
                    ↓
               processed_benches (confirmed high-confidence)
```

See `DATABASE_MODEL.md` for complete schema documentation.

### Module Structure

**bench_finder/** - Main Python package
- `cli.py`: Typer CLI with Rich progress bars and tables
- `config.py`: Environment variables, API keys, model settings
- `detection.py`: Core detection logic orchestration
- `display.py`: Terminal image display utilities
- `utils.py`: Logging, retry logic, progress tracking

**bench_finder/core/** - Core functionality
- `geocoder.py`: Google Geocoding API wrapper
- `streetview.py`: Google Street View Static API client (supports panorama metadata)

**bench_finder/clients/** - External API clients
- `base_detection_client.py`: Abstract detection client interface
- `roboflow_client.py`: Roboflow API client with multiple model support
- `ultralytics_client.py`: Ultralytics Hub + local YOLO inference
- `multi_model_client.py`: Multi-model detection with fallback strategy
- `overpass_client.py`: OpenStreetMap Overpass API queries
- `mapillary_client.py`: Mapillary API v4 client

**bench_finder/generators/** - Bench candidate generators
- `bench_generator.py`: Abstract base generator
- `overpass.py`: OSM bench candidate generator
- `mapillary.py`: Mapillary bench candidate generator

**bench_finder/services/** - Business logic
- `database.py`: SQLite database operations (SQLModel ORM)
- `image_download_service.py`: Async image downloading with retry logic
- `image_storage.py`: Firebase Storage integration
- `mapillary_service.py`: Mapillary search and image processing

**bench_finder/models/** - Data models
- `unified_models.py`: SQLModel database models
- `enums.py`: Enums (DataSource, DetectionSource, BenchCandidateStatus, etc.)

**api/** - FastAPI web server
- `fastapi_server.py`: Main FastAPI app with OpenAPI docs
- `api_models.py`: Pydantic request/response models
- `auth.py`: Firebase authentication

**tools/** - Command-line utilities
- `fastapi_cli.py`: FastAPI testing CLI with image display
- `local_roboflow_detector.py`: Local Roboflow detector helper
- `remove_indoor_images.py`: Image cleanup helper

**frontend/** - React TypeScript frontend
- `src/api/`: Auto-generated API client (from OpenAPI)
- `src/components/`: React components
- `src/pages/`: Page components
- Uses Vite for dev server and builds
- Styled Components for styling
- React Leaflet for maps
- TanStack Query for data fetching

### Configuration Patterns

**Environment Variables** (`.env`):
- Required: `GOOGLE_MAPS_API_KEY`, `ROBOFLOW_API_KEY`
- Optional: `ULTRALYTICS_API_KEY`, `MAPILLARY_ACCESS_TOKEN`
- Database: `DATABASE_PATH` (SQLite) or `DATABASE_URL` (PostgreSQL)
- Firebase: `FIREBASE_CREDENTIALS_PATH` or `FIREBASE_CREDENTIALS_BASE64`
- Detection: `DETECTION_BACKEND` (roboflow/ultralytics/multi)

**Model Configuration** (`bench_finder/config.py`):
- `ROBOFLOW_MODELS`: List of models with priority/confidence thresholds
- `ULTRALYTICS_USE_LOCAL`: Use local YOLO model vs API
- `DETECTION_BACKEND`: Switch between detection backends
- `STREETVIEW_HEADINGS`: Camera angles for image capture

### API Patterns

**FastAPI Server** (`api/fastapi_server.py`):
- OpenAPI docs at `/docs` (Swagger UI)
- All endpoints return Pydantic models
- Error handling via HTTPException
- CORS enabled for frontend
- Static file serving for images
- Pagination and filtering support

**Key Endpoints:**
- `GET /api/benches`: List benches with pagination
- `GET /api/benches/bbox`: Search within bounding box
- `GET /api/benches/{id}`: Get bench details
- `POST /api/searches`: Create new search
- `GET /images/{filename}`: Serve images

**Authentication:**
- Firebase Auth integration (`api/auth.py`)
- JWT token validation
- User-specific endpoints (ratings, comments, status)

## Important Notes

### Always Activate venv
Per `.cursor/rules/always-activate-venv.mdc`: Always activate the Python virtual environment before running Python commands.

### Database Migrations
When adding/modifying database models:
1. Update models in `bench_finder/models/unified_models.py`
2. Add a numbered SQL file in `migrations/` (e.g., `004_add_thing.sql`) and apply it with `make db-migrate` (see `DATABASE_MODEL.md`)
3. Test migration locally before running on cloud database
4. Use SQLModel's `create_all()` for automatic schema updates in development

### Image Storage
- **Local development**: Images stored in `images/` directory
- **Production**: Images uploaded to Firebase Storage
- Path format: `{source}/{bench_id or candidate_id}/{heading}_{timestamp}.jpg`
- Supports both local paths and Firebase URLs

### Detection Strategy
**Multi-Model Approach** (`DETECTION_BACKEND=multi`):
1. Tries Roboflow models in priority order
2. Falls back to Ultralytics if all Roboflow models fail
3. Each model has configurable confidence threshold
4. Best detection across all models is selected

### Frontend-Backend Integration
- Frontend auto-generates API client from OpenAPI spec
- Run `npm run generate-api` after API changes
- API must be running on port 8866 for generation

### Testing
- Limited test coverage currently (`tests/` directory)
- Most testing done via CLI tools (`tools/fastapi_cli.py`)
- Add tests to `tests/` directory following pytest conventions
- Use markers: `@pytest.mark.slow`, `@pytest.mark.integration`

### Performance Considerations
- Database uses spatial indexes for location queries (see `SPATIAL_INDEXING.md`)
- Image downloads are async with concurrent processing
- Detection runs sequentially per image (GPU intensive)
- Pagination required for large result sets in API

### Code Quality
- Ruff configured with extensive rule set (see `pyproject.toml`)
- Pre-commit hooks enforce linting/formatting
- Biome for frontend linting/formatting
- Type hints required (mypy configured but not strictly enforced)

### Common Patterns
- **Retry Logic**: Use `@backoff.on_exception` for API calls
- **Progress Tracking**: Use Rich Progress bars for long operations
- **Logging**: Use `bench_finder.utils.setup_logging()` with structured logging
- **Error Handling**: Log errors with context, graceful degradation

## Documentation Files

- `docs/README.md`: Main project documentation
- `DATABASE_MODEL.md`: Complete database schema
- `DEVELOPMENT.md`: FastAPI development guide
- `PERFORMANCE_OPTIMIZATIONS_APPLIED.md`: Performance improvements
- `SPATIAL_INDEXING.md`: Database indexing strategy
- `docs/FIREBASE_AUTH_SETUP.md`: Firebase authentication setup
- `frontend/OPENAPI_INTEGRATION.md`: API client generation
- `frontend/PRE_COMMIT.md`: Frontend pre-commit setup
