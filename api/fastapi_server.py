#!/usr/bin/env python3
"""
FastAPI server for bench finder application with comprehensive OpenAPI documentation.
Migrated from Flask with improved type safety and automatic API documentation.
"""

import logging
import os
import traceback
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from bench_finder.config import DATABASE_PATH, DATABASE_URL, IMAGES_DIR
from bench_finder.services.database import BenchDatabase

from .api_models import (  # noqa: F401 - BboxBenchResponse re-exported for backwards compat
    BboxBenchResponse,
    ErrorResponse,
)
from .routes import benches, health, images, reporting, searches, users


logger = logging.getLogger(__name__)


# Application lifecycle management
@asynccontextmanager
async def lifespan(_app: FastAPI) -> None:
    """Manage application lifecycle - startup and shutdown events."""
    # Startup

    print("🚀 Starting Bench Finder FastAPI server...")
    # Display the actual database connection being used
    if DATABASE_URL and DATABASE_URL.startswith("postgresql"):
        db_type = "PostgreSQL (Supabase)"
        db_info = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
        print(f"📁 Database: {db_type} - {db_info}")
    elif DATABASE_URL:
        db_type = "Database (via URL)"
        print(f"📁 Database: {db_type} - {DATABASE_URL[:50]}...")
    else:
        print(f"📁 Database: SQLite - {DATABASE_PATH}")
    print(f"🖼️  Images directory: {IMAGES_DIR}")

    # Configure logging for better error visibility
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),  # Console output
        ],
    )

    # Set uvicorn loggers to show more detail
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    # Initialize database once and store in app.state for reuse
    print("🔌 Initializing database connection pool...")
    _app.state.db = BenchDatabase()
    print("✅ Database connection pool initialized")

    # Ensure required directories exist
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    print("✅ Server initialization complete")

    yield

    # Shutdown
    print("🛑 Shutting down Bench Finder server...")


# Create FastAPI application
app = FastAPI(
    title="Bench Finder API",
    description="""
    A comprehensive API for discovering and analyzing public benches using computer vision.

    This API provides access to bench detection data from multiple sources:
    - **OpenStreetMap (OSM)**: Crowdsourced geographic data
    - **Mapillary**: Street-level imagery with AI-powered object detection
    - **Custom Detection Models**: Roboflow and Ultralytics YOLO models

    ## Features

    - 🔍 **Search & Discovery**: Find benches by location, confidence, and source
    - 📊 **Advanced Analytics**: Get detailed statistics and detection metadata
    - 🗺️ **Spatial Queries**: Bounding box searches for map applications
    - 🖼️ **Image Analysis**: Access detection visualizations and segmentation data
    - 📱 **Web Interface**: Full-featured frontend with infinite scroll and filtering

    ## Data Sources

    - **OSM**: Traditional geographic data with bench locations
    - **Mapillary**: AI-detected benches from street imagery with confidence scores
    - **Multi-Model Detection**: Combines Roboflow and Ultralytics for higher accuracy

    ## Authentication

    Most endpoints are public, but Mapillary integration requires proper API token configuration.
    """,
    version="2.0.0",
    contact={
        "name": "Bench Finder Project",
        "url": "https://github.com/your-username/bench_finder",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        {
            "name": "benches",
            "description": "Core bench discovery and listing operations",
        },
        {
            "name": "search",
            "description": "Search management and historical queries",
        },
        {
            "name": "images",
            "description": "Image serving and detection visualization",
        },
        {
            "name": "mapillary",
            "description": "Mapillary-specific operations and street imagery",
        },
        {
            "name": "reporting",
            "description": "User reporting for bad detections and missing benches",
        },
        {
            "name": "statistics",
            "description": "Analytics and performance metrics",
        },
        {
            "name": "config",
            "description": "Application configuration and metadata",
        },
    ],
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handlers
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler that logs full stacktraces for debugging."""
    logger.error(f"🚨 Unhandled exception in {request.method} {request.url}:")
    logger.error(f"Exception type: {type(exc).__name__}")
    logger.error(f"Exception message: {exc!s}")
    logger.error("Full stacktrace:")
    logger.error(traceback.format_exc())

    print(f"🚨 Unhandled exception in {request.method} {request.url}:")
    print(f"Exception type: {type(exc).__name__}")
    print(f"Exception message: {exc!s}")
    print("Full stacktrace:")
    traceback.print_exc()

    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": str(exc) if str(exc) else "An unexpected error occurred",
            "type": type(exc).__name__,
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle ValueError exceptions with proper HTTP status and stacktrace logging."""
    logger.warning(f"🚨 ValueError in {request.method} {request.url}:")
    logger.warning(f"Exception type: {type(exc).__name__}")
    logger.warning(f"Exception message: {exc!s}")
    logger.warning("Full stacktrace:")
    logger.warning(traceback.format_exc())

    print(f"🚨 ValueError in {request.method} {request.url}:")
    print(f"Exception type: {type(exc).__name__}")
    print(f"Exception message: {exc!s}")
    print("Full stacktrace:")
    traceback.print_exc()

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(error="Invalid input", detail=str(exc)).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTPException with stacktrace logging for 400-level errors."""
    if 400 <= exc.status_code < 500:
        logger.warning(
            f"🚨 HTTPException {exc.status_code} in {request.method} {request.url}:"
        )
        logger.warning(f"Exception type: {type(exc).__name__}")
        logger.warning(f"Exception message: {exc.detail!s}")
        logger.warning("Full stacktrace:")
        logger.warning(traceback.format_exc())

        print(f"🚨 HTTPException {exc.status_code} in {request.method} {request.url}:")
        print(f"Exception type: {type(exc).__name__}")
        print(f"Exception message: {exc.detail!s}")
        print("Full stacktrace:")
        traceback.print_exc()

    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error="HTTP Error", detail=str(exc.detail)).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle Pydantic validation errors with stacktrace logging."""
    logger.warning(f"🚨 ValidationError in {request.method} {request.url}:")
    logger.warning(f"Exception type: {type(exc).__name__}")
    logger.warning(f"Exception message: {exc!s}")
    logger.warning("Full stacktrace:")
    logger.warning(traceback.format_exc())

    print(f"🚨 ValidationError in {request.method} {request.url}:")
    print(f"Exception type: {type(exc).__name__}")
    print(f"Exception message: {exc!s}")
    print("Full stacktrace:")
    traceback.print_exc()

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="Validation Error", detail=f"Request validation failed: {exc!s}"
        ).model_dump(),
    )


# Mount static files for images
if os.path.exists(IMAGES_DIR):
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

# Include route modules
app.include_router(health.router)
app.include_router(benches.router)
app.include_router(searches.router)
app.include_router(images.router)
app.include_router(reporting.router)
app.include_router(users.router)


if __name__ == "__main__":
    print("🚀 Starting Bench Finder FastAPI server with uvicorn...")
    print("📚 API documentation will be available at: http://localhost:8866/docs")
    print("🔄 Alternative docs at: http://localhost:8866/redoc")
    print("🔄 Auto-reload enabled - server will restart on Python file changes")

    uvicorn.run(
        "api.fastapi_server:app",
        host="0.0.0.0",
        port=8866,
        reload=True,
        log_level="info",
        access_log=True,
        reload_dirs=["api", "bench_finder"],
        reload_includes=["*.py"],
        reload_excludes=["*.pyc", "__pycache__", "*.log"],
    )
