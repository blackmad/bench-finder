# FastAPI Migration Guide

## Overview

The Bench Finder application has been migrated from Flask to FastAPI to provide:

- ✅ **Automatic OpenAPI Documentation** - Interactive API docs at `/docs` and `/redoc`
- ✅ **Type Safety** - Automatic request/response validation with Pydantic
- ✅ **Better Performance** - ASGI server with async support
- ✅ **Enhanced Developer Experience** - Rich error messages and IDE support
- ✅ **Production Ready** - Built-in support for multiple workers and deployment

## Quick Start

### Development Mode
```bash
# Start development server with auto-reload
./start_fastapi_server.sh dev --reload

# Or use uvicorn directly
python3 -m uvicorn fastapi_server:app --reload --host 0.0.0.0 --port 8866
```

### Production Mode
```bash
# Start production server
./start_fastapi_server.sh prod --workers 4

# Or use uvicorn directly
python3 -m uvicorn fastapi_server:app --host 0.0.0.0 --port 8866
```

### Installation

Make sure you have the FastAPI dependencies:

```bash
pip install -r requirements.txt
```

## API Documentation

Once the server is running, you can access:

- **Interactive API Documentation (Swagger UI)**: http://localhost:8866/docs
- **Alternative Documentation (ReDoc)**: http://localhost:8866/redoc
- **OpenAPI JSON Schema**: http://localhost:8866/openapi.json
- **Health Check**: http://localhost:8866/health
- **API Information**: http://localhost:8866/api/info

## Key Changes from Flask

### File Structure
```
bench_finder/
├── fastapi_server.py          # New FastAPI application
├── fastapi_schemas.py         # Enhanced Pydantic models
├── start_fastapi_server.sh    # Startup script
├── web_server.py             # Original Flask server (kept for reference)
└── mapillary_web_server.py   # Original Flask Mapillary server (kept for reference)
```

### Dependencies Updated
- ✅ Added: `uvicorn[standard]` - ASGI server
- ✅ Added: `python-multipart` - For file uploads
- 🔄 Kept: `fastapi` (already in requirements)
- 🔄 Kept: `pydantic` (already in requirements)
- ❌ Deprecated: `Flask` and `Werkzeug` (commented out)

### API Endpoints Migrated

All original Flask endpoints have been migrated with enhanced documentation:

#### Core Endpoints
| Endpoint | Method | Description | Status |
|----------|--------|-------------|---------|
| `/health` | GET | Health check with database status | ✅ Enhanced |
| `/api/config` | GET | Application configuration | ✅ Migrated |
| `/api/info` | GET | API capabilities and limits | ✅ New |

#### Bench Endpoints
| Endpoint | Method | Description | Status |
|----------|--------|-------------|---------|
| `/api/benches` | GET | List benches with pagination | ✅ Enhanced |
| `/api/benches/source/{source}` | GET | Filter benches by data source | ✅ Enhanced |
| `/api/benches/random` | GET | Get random bench | ✅ Enhanced |
| `/api/benches/bbox` | GET | Geographic bounding box search | ✅ Enhanced |

#### Image Endpoints
| Endpoint | Method | Description | Status |
|----------|--------|-------------|---------|
| `/images/{filename}` | GET | Serve bench images | ✅ Enhanced |
| `/api/image/{image_id}/segmentation` | GET | Detection visualization data | ✅ Enhanced |
| `/api/bench/{bench_id}/images` | GET | Get all images for a bench | ✅ Enhanced |

#### Search Endpoints
| Endpoint | Method | Description | Status |
|----------|--------|-------------|---------|
| `/api/searches` | GET | List historical searches | ✅ Migrated |

#### Mapillary Endpoints
| Endpoint | Method | Description | Status |
|----------|--------|-------------|---------|
| `/api/mapillary/search` | POST | Search Mapillary API | ✅ Enhanced |
| `/api/mapillary/stored` | GET | Get cached Mapillary data | ✅ Enhanced |
| `/api/mapillary/statistics` | GET | Mapillary analytics | ✅ Enhanced |
| `/api/mapillary/config` | GET | Mapillary configuration | ✅ Enhanced |
| `/api/mapillary/refresh/{image_id}` | PUT | Refresh image detections | ✅ Enhanced |

#### Statistics Endpoints
| Endpoint | Method | Description | Status |
|----------|--------|-------------|---------|
| `/api/statistics/source/{source}` | GET | Source-specific analytics | ✅ Enhanced |

## New Features

### Enhanced Request/Response Models
- **Comprehensive Validation** - All inputs validated with Pydantic
- **Rich Error Messages** - Detailed validation errors with suggestions
- **OpenAPI Integration** - Automatic schema generation
- **Type Hints** - Full IDE support and static analysis

### Better Error Handling
- **HTTP Status Codes** - Proper status codes for all scenarios
- **Structured Errors** - Consistent error response format
- **Debug Information** - Enhanced error details in development mode

### Performance Improvements
- **ASGI Server** - Better concurrent request handling
- **Async Support** - Ready for async database operations
- **Multiple Workers** - Production-ready scalability

### Documentation & Discovery
- **Interactive Docs** - Try API endpoints directly in browser
- **Schema Export** - OpenAPI JSON for client generation
- **Comprehensive Examples** - Request/response examples for all endpoints

## Configuration

### Environment Variables
```bash
# Server Configuration
HOST=0.0.0.0                    # Host to bind to
PORT=8866                       # Port to bind to
WORKERS=1                       # Number of worker processes
LOG_LEVEL=info                  # Log level (debug, info, warning, error)
RELOAD=false                    # Enable auto-reload (development only)

# Application Configuration
DATABASE_PATH=bench_finder.db   # Database file path
IMAGES_DIR=images               # Images directory
MAPILLARY_ACCESS_TOKEN=xxx      # Mapillary API token (optional)
MAPILLARY_DOWNLOAD_IMAGES=true  # Download images from Mapillary
```

### Production Deployment

#### Using systemd (Linux)
```ini
[Unit]
Description=Bench Finder FastAPI Server
After=network.target

[Service]
Type=exec
User=benchfinder
WorkingDirectory=/path/to/bench_finder
Environment=HOST=0.0.0.0
Environment=PORT=8866
Environment=WORKERS=4
Environment=LOG_LEVEL=info
ExecStart=/path/to/bench_finder/start_fastapi_server.sh prod
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

#### Using Docker
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8866
CMD ["python3", "-m", "uvicorn", "fastapi_server:app", "--host", "0.0.0.0", "--port", "8866"]
```

#### Using nginx Reverse Proxy
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8866;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Serve images directly (optional optimization)
    location /images/ {
        alias /path/to/bench_finder/images/;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }
}
```

## Development Workflow

### Starting Development Server
```bash
# Method 1: Using startup script (recommended)
./start_fastapi_server.sh dev --reload

# Method 2: Using uvicorn directly
python3 -m uvicorn fastapi_server:app --reload --host 0.0.0.0 --port 8866

# Method 3: Running the Python file directly
python3 fastapi_server.py
```

### API Development
1. **Define Models** - Add new Pydantic models in `fastapi_schemas.py`
2. **Add Endpoints** - Implement new endpoints in `fastapi_server.py`
3. **Test Interactively** - Use `/docs` for immediate testing
4. **Validate Schema** - Check `/openapi.json` for schema correctness

### Testing
```bash
# Test health endpoint
curl http://localhost:8866/health

# Test API endpoint with JSON
curl -X GET "http://localhost:8866/api/benches?page=0&page_size=10&min_confidence=0.8" \
     -H "accept: application/json"

# Test Mapillary search (POST)
curl -X POST "http://localhost:8866/api/mapillary/search" \
     -H "accept: application/json" \
     -H "Content-Type: application/json" \
     -d '{
       "center_lat": 52.3613577,
       "center_lng": 4.8666322,
       "radius_meters": 1000,
       "limit": 100
     }'
```

## Migration Checklist

### Completed ✅
- [x] Core FastAPI application setup
- [x] All Flask endpoints migrated
- [x] Enhanced Pydantic models with validation
- [x] Comprehensive OpenAPI documentation
- [x] Error handling and status codes
- [x] Image serving with security checks
- [x] Mapillary integration maintained
- [x] Configuration management
- [x] Health check endpoint
- [x] Production startup script
- [x] Development workflow tools

### Optional Future Enhancements 🔮
- [ ] Async database operations
- [ ] Authentication and rate limiting
- [ ] Caching layer (Redis)
- [ ] Background task queue
- [ ] Metrics and monitoring
- [ ] API versioning
- [ ] GraphQL endpoint
- [ ] WebSocket support for real-time updates

## Troubleshooting

### Common Issues

#### Import Errors
```
ImportError: No module named 'fastapi_schemas'
```
**Solution**: Ensure you're running from the correct directory and all files are present.

#### Port Already in Use
```
OSError: [Errno 48] Address already in use
```
**Solution**: Kill the existing process or use a different port:
```bash
# Find process using port 8866
lsof -i :8866

# Kill the process
kill -9 <PID>

# Or use different port
./start_fastapi_server.sh dev --port 8867
```

#### Database Connection Issues
```
sqlite3.OperationalError: no such table: benches
```
**Solution**: Ensure your database is properly initialized and the path is correct.

#### Mapillary Integration Not Working
```
Mapillary integration is not available
```
**Solution**: Set the `MAPILLARY_ACCESS_TOKEN` environment variable or check the mapillary_service initialization.

### Performance Issues
- **High Memory Usage**: Reduce the number of workers or implement database connection pooling
- **Slow Responses**: Add caching, optimize database queries, or use async operations
- **High CPU Usage**: Profile the application and optimize hot code paths

## Support and Resources

- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Pydantic Documentation**: https://docs.pydantic.dev/
- **Uvicorn Documentation**: https://www.uvicorn.org/
- **OpenAPI Specification**: https://swagger.io/specification/

For questions or issues with the migration, check:
1. The interactive API documentation at `/docs`
2. Server logs for detailed error messages
3. The health check endpoint for system status
4. This migration guide for common solutions