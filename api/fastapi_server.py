#!/usr/bin/env python3
"""
FastAPI server for bench finder application with comprehensive OpenAPI documentation.
Migrated from Flask with improved type safety and automatic API documentation.
"""
import os
import math
import json
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any, Union
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, Path, Body, Request, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
import uvicorn

from bench_finder.services.database import BenchDatabase
from bench_finder.config import DATABASE_PATH, IMAGES_DIR
from bench_finder.services.clustered_bench_service import ClusteredBenchService
from bench_finder.models.schemas import (
    BenchListResponse, WebBenchData, PaginationInfo, SegmentationData,
    ImageListResponse, ImageResponse, ConfigResponse, SearchListResponse, SearchSummary,
    SourceSearchRequest, SourceStatistics, ClusteredBenchListResponse
)

# Configuration constants
DEFAULT_START_LAT = 52.3613577  # Amsterdam, Netherlands (matches actual data)
DEFAULT_START_LNG = 4.8666322
DEFAULT_MIN_CONFIDENCE = 0.8
PAGE_SIZE = 20

# Global mapillary service instance
mapillary_service = None


# Enhanced Pydantic models for FastAPI with OpenAPI documentation
class BenchQueryParams(BaseModel):
    """Query parameters for bench listing endpoints."""
    page: int = Field(0, ge=0, description="Page number (0-based)")
    page_size: int = Field(PAGE_SIZE, ge=1, le=50, description="Items per page (max 50)")
    min_confidence: float = Field(DEFAULT_MIN_CONFIDENCE, ge=0.0, le=1.0, description="Minimum detection confidence score")
    start_lat: float = Field(DEFAULT_START_LAT, ge=-90.0, le=90.0, description="Starting latitude for distance calculations")
    start_lng: float = Field(DEFAULT_START_LNG, ge=-180.0, le=180.0, description="Starting longitude for distance calculations")
    sort_by: str = Field("distance", pattern="^(distance|confidence|images|recent)$", description="Sort criteria")


class BboxQueryParams(BaseModel):
    """Query parameters for bounding box bench queries."""
    north: float = Field(..., ge=-90.0, le=90.0, description="Northern latitude boundary")
    south: float = Field(..., ge=-90.0, le=90.0, description="Southern latitude boundary")
    east: float = Field(..., ge=-180.0, le=180.0, description="Eastern longitude boundary")
    west: float = Field(..., ge=-180.0, le=180.0, description="Western longitude boundary")
    min_confidence: float = Field(DEFAULT_MIN_CONFIDENCE, ge=0.0, le=1.0, description="Minimum detection confidence score")
    source: Optional[str] = Field(None, pattern="^(osm|mapillary)$", description="Filter by data source")
    sort_by: str = Field("distance", pattern="^(distance|confidence|images|recent)$", description="Sort criteria")
    limit: int = Field(200, ge=1, le=500, description="Maximum number of results")


class MapillarySearchRequest(BaseModel):
    """Request model for Mapillary bench search."""
    center_lat: float = Field(..., ge=-90.0, le=90.0, description="Search center latitude")
    center_lng: float = Field(..., ge=-180.0, le=180.0, description="Search center longitude")
    radius_meters: int = Field(1000, ge=10, le=10000, description="Search radius in meters")
    limit: int = Field(1000, ge=1, le=5000, description="Maximum number of results to fetch")


class BboxBenchResponse(BaseModel):
    """Response model for bounding box bench queries."""
    benches: List[WebBenchData] = Field(..., description="List of benches within the bounding box")
    total_count: int = Field(..., ge=0, description="Total number of benches returned")
    bbox: Dict[str, float] = Field(..., description="The requested bounding box coordinates")


class RandomBenchResponse(BaseModel):
    """Response model for random bench queries."""
    bench: WebBenchData = Field(..., description="Randomly selected bench matching criteria")


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")


# Application lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown events."""
    # Startup
    global mapillary_service
    
    print("🚀 Starting Bench Finder FastAPI server...")
    print(f"📁 Database: {DATABASE_PATH}")
    print(f"🖼️  Images directory: {IMAGES_DIR}")
    
    # Try to initialize Mapillary service if token is available
    from bench_finder.config import MAPILLARY_ACCESS_TOKEN, MAPILLARY_DOWNLOAD_IMAGES
    if MAPILLARY_ACCESS_TOKEN:
        try:
            from bench_finder.services.mapillary_service import MapillaryBenchService
            mapillary_service = MapillaryBenchService(DATABASE_PATH, MAPILLARY_ACCESS_TOKEN, IMAGES_DIR)
            print(f"✅ Mapillary integration enabled (image downloading: {'ON' if MAPILLARY_DOWNLOAD_IMAGES else 'OFF'})")
        except Exception as e:
            print(f"⚠️ Mapillary integration failed: {e}")
            mapillary_service = None
    else:
        print("ℹ️ Mapillary integration disabled (no MAPILLARY_ACCESS_TOKEN)")
    
    # Ensure required directories exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
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
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for images
if os.path.exists(IMAGES_DIR):
    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")


# Global exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions with proper HTTP status."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"error": "Invalid input", "detail": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions gracefully."""
    print(f"Unexpected error on {request.url}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "detail": "An unexpected error occurred"}
    )


# Utility functions
def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Calculate the great circle distance between two points using Haversine formula.
    Returns distance in meters.
    """
    # Convert decimal degrees to radians
    lat1, lng1, lat2, lng2 = map(math.radians, [lat1, lng1, lat2, lng2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth's radius in meters
    r = 6371000
    return c * r


# Health check endpoint
@app.get("/health", 
         summary="Health Check", 
         description="Simple health check endpoint to verify server status",
         response_model=Dict[str, str],
         tags=["config"])
async def health_check():
    """Check if the server is running and database is accessible."""
    try:
        # Test database connection
        db = BenchDatabase()
        with db._get_connection() as conn:
            conn.execute("SELECT 1").fetchone()
        
        return {
            "status": "healthy",
            "database": "connected",
            "mapillary": "enabled" if mapillary_service else "disabled"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service unhealthy: {str(e)}"
        )


# Import the enhanced schemas
from .fastapi_schemas import (
    BenchListQuery, BboxQuery, RandomBenchQuery, BboxBenchResponse, 
    RandomBenchResponse, EnhancedErrorResponse, HealthCheckResponse,
    MapillarySearchRequest, StatisticsQuery
)


# Utility function for bench data processing (shared with Flask version)
def get_high_confidence_benches_filtered(page: int = 0, page_size: int = PAGE_SIZE, 
                                        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
                                        start_lat: float = DEFAULT_START_LAT, 
                                        start_lng: float = DEFAULT_START_LNG,
                                        source_filter: str = None,
                                        sort_by: str = 'distance') -> BenchListResponse:
    """
    Get benches with high confidence detections, with optional source filtering.
    Supports both Roboflow, Ultralytics, and Mapillary detection data.
    """
    try:
        db = BenchDatabase()
        with db._get_connection() as conn:
            # Base query for benches that meet confidence requirements
            base_query = """
                SELECT DISTINCT b.id
                FROM benches b
                JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                JOIN detections d ON i.id = d.image_id
                WHERE d.has_bench = 1 AND d.max_confidence >= ?
                
                UNION
                
                SELECT DISTINCT b.id
                FROM benches b
                JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                JOIN ultralytics_detections ud ON i.id = ud.image_id
                WHERE ud.has_bench = 1 AND ud.max_confidence >= ?
            """
            
            # Add source filter if specified
            source_condition = ""
            query_params = [min_confidence, min_confidence]
            
            if source_filter:
                source_condition = f" AND b.source = ?"
                query_params.append(source_filter)
            
            # Get total count with confidence filtering
            count_query = f"""
                SELECT COUNT(*) as total FROM (
                    SELECT b.id,
                           COALESCE(rf_data.max_confidence, 0) as roboflow_confidence,
                           COALESCE(ul_data.max_confidence, 0) as ultralytics_confidence,
                           COALESCE(mp_data.max_confidence, 0) as mapillary_confidence,
                           CASE 
                               WHEN COALESCE(rf_data.max_confidence, 0) >= COALESCE(ul_data.max_confidence, 0) AND COALESCE(rf_data.max_confidence, 0) >= COALESCE(mp_data.max_confidence, 0)
                               THEN COALESCE(rf_data.max_confidence, 0)
                               WHEN COALESCE(ul_data.max_confidence, 0) >= COALESCE(mp_data.max_confidence, 0)
                               THEN COALESCE(ul_data.max_confidence, 0)
                               ELSE COALESCE(mp_data.max_confidence, 0)
                           END as best_confidence
                    FROM benches b
                    JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                    LEFT JOIN (
                        SELECT image_id, MAX(max_confidence) as max_confidence
                        FROM detections 
                        WHERE has_bench = 1
                        GROUP BY image_id
                    ) rf_data ON i.id = rf_data.image_id
                    LEFT JOIN (
                        SELECT image_id, MAX(max_confidence) as max_confidence
                        FROM ultralytics_detections 
                        WHERE has_bench = 1
                        GROUP BY image_id
                    ) ul_data ON i.id = ul_data.image_id
                    LEFT JOIN (
                        SELECT image_id, MAX(max_confidence) as max_confidence
                        FROM detections 
                        WHERE has_bench = 1 AND source = 'mapillary'
                        GROUP BY image_id
                    ) mp_data ON i.id = mp_data.image_id
                    WHERE b.id IN ({base_query}){source_condition}
                    GROUP BY b.id
                    HAVING best_confidence >= ?
                ) as filtered_benches
            """
            count_params = query_params + [min_confidence]
            total_count = conn.execute(count_query, count_params).fetchone()['total']
            
            # Determine sorting clause
            if sort_by == 'confidence':
                order_clause = 'best_confidence DESC, b.id'
            elif sort_by == 'images':
                order_clause = 'image_count DESC, best_confidence DESC, b.id'
            elif sort_by == 'recent':
                order_clause = 'b.id DESC'  # Assuming higher IDs are more recent
            else:  # distance (default)
                # For distance sorting, we'll calculate distance in the query
                order_clause = f'((b.lat - {start_lat}) * (b.lat - {start_lat}) + (b.lng - {start_lng}) * (b.lng - {start_lng})) ASC, best_confidence DESC'
            
            # Get detailed bench data
            query = f"""
                SELECT 
                    b.id, b.provider_id, b.lat, b.lng, b.tags, b.source, b.external_id,
                    COALESCE(rf_data.max_confidence, 0) as roboflow_confidence,
                    COALESCE(ul_data.max_confidence, 0) as ultralytics_confidence,
                    COALESCE(mp_data.max_confidence, 0) as mapillary_confidence,
                    COUNT(DISTINCT i.id) as image_count,
                    GROUP_CONCAT(DISTINCT i.filename) as image_filenames,
                    GROUP_CONCAT(DISTINCT i.id) as image_ids,
                    CASE 
                        WHEN COALESCE(rf_data.max_confidence, 0) >= COALESCE(ul_data.max_confidence, 0) AND COALESCE(rf_data.max_confidence, 0) >= COALESCE(mp_data.max_confidence, 0)
                        THEN COALESCE(rf_data.max_confidence, 0)
                        WHEN COALESCE(ul_data.max_confidence, 0) >= COALESCE(mp_data.max_confidence, 0)
                        THEN COALESCE(ul_data.max_confidence, 0)
                        ELSE COALESCE(mp_data.max_confidence, 0)
                    END as best_confidence
                FROM benches b
                JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                LEFT JOIN (
                    SELECT image_id, MAX(max_confidence) as max_confidence
                    FROM detections 
                    WHERE has_bench = 1
                    GROUP BY image_id
                ) rf_data ON i.id = rf_data.image_id
                LEFT JOIN (
                    SELECT image_id, MAX(max_confidence) as max_confidence
                    FROM ultralytics_detections 
                    WHERE has_bench = 1
                    GROUP BY image_id
                ) ul_data ON i.id = ul_data.image_id
                LEFT JOIN (
                    SELECT image_id, MAX(max_confidence) as max_confidence
                    FROM detections 
                    WHERE has_bench = 1 AND source = 'mapillary'
                    GROUP BY image_id
                ) mp_data ON i.id = mp_data.image_id
                WHERE b.id IN ({base_query}){source_condition}
                GROUP BY b.id
                HAVING best_confidence >= ?
                ORDER BY {order_clause}
                LIMIT ? OFFSET ?
            """
            
            offset = page * page_size
            query_params_final = query_params + [min_confidence, page_size, offset]
            rows = conn.execute(query, query_params_final).fetchall()
            
            # Process results
            benches = []
            for row in rows:
                # Parse tags if available
                tags = {}
                if row['tags']:
                    try:
                        tags = json.loads(row['tags'])
                    except json.JSONDecodeError:
                        pass
                
                # Calculate distance
                distance = calculate_distance(start_lat, start_lng, row['lat'], row['lng'])
                
                # Get image filenames and IDs
                image_filenames = row['image_filenames'].split(',') if row['image_filenames'] else []
                image_ids = [int(x) for x in row['image_ids'].split(',') if x] if row['image_ids'] else []
                
                # Determine best confidence and detection type
                roboflow_conf = row['roboflow_confidence'] or 0
                ultralytics_conf = row['ultralytics_confidence'] or 0
                mapillary_conf = row['mapillary_confidence'] or 0
                best_confidence = max(roboflow_conf, ultralytics_conf, mapillary_conf)
                
                # Determine detection type based on source and confidence
                if row['source'] == 'mapillary':
                    detection_type = 'mapillary'
                elif ultralytics_conf > 0 and ultralytics_conf >= roboflow_conf * 0.95:
                    detection_type = 'ultralytics'
                else:
                    detection_type = 'roboflow' if roboflow_conf > ultralytics_conf else 'ultralytics'
                
                bench_data = WebBenchData(
                    id=row['id'],
                    provider_id=row['provider_id'],
                    lat=row['lat'],
                    lng=row['lng'],
                    tags=tags,
                    source=row['source'] or 'osm',
                    external_id=row['external_id'],
                    best_confidence=round(best_confidence, 3),
                    roboflow_confidence=round(roboflow_conf, 3),
                    ultralytics_confidence=round(ultralytics_conf, 3),
                    mapillary_confidence=round(mapillary_conf, 3),
                    detection_type=detection_type,
                    has_segmentation=ultralytics_conf > 0 or mapillary_conf > 0,
                    image_count=row['image_count'],
                    image_filenames=image_filenames,
                    image_ids=image_ids,
                    distance_meters=round(distance),
                    distance_km=round(distance / 1000, 2)
                )
                
                benches.append(bench_data)
            
            pagination = PaginationInfo(
                page=page,
                page_size=page_size,
                total_count=total_count,
                total_pages=math.ceil(total_count / page_size),
                has_next=(page + 1) * page_size < total_count
            )
            
            return BenchListResponse(benches=benches, pagination=pagination)
            
    except Exception as e:
        print(f"Error getting high confidence benches: {e}")
        return BenchListResponse(
            benches=[],
            pagination=PaginationInfo(page=0, page_size=page_size, total_count=0, total_pages=0, has_next=False)
        )


# BENCH ENDPOINTS
@app.get("/api/benches",
         summary="List Benches",
         description="Get paginated list of benches with high confidence detections, sorted by various criteria",
         response_model=Union[BenchListResponse, ClusteredBenchListResponse],
         responses={
             400: {"model": EnhancedErrorResponse, "description": "Invalid query parameters"},
             500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
         },
         tags=["benches"])
async def get_benches(
    page: int = Query(0, ge=0, le=1000, description="Page number (0-based)"),
    page_size: int = Query(PAGE_SIZE, ge=1, le=50, description="Items per page (max 50)"),
    min_confidence: float = Query(DEFAULT_MIN_CONFIDENCE, ge=0.0, le=1.0, description="Minimum detection confidence"),
    start_lat: float = Query(DEFAULT_START_LAT, ge=-90.0, le=90.0, description="Starting latitude for distance sorting"),
    start_lng: float = Query(DEFAULT_START_LNG, ge=-180.0, le=180.0, description="Starting longitude for distance sorting"),
    sort_by: str = Query("distance", pattern="^(distance|confidence|images|recent)$", description="Sort criteria"),
    source: Optional[str] = Query(None, pattern="^(osm|mapillary)$", description="Filter by data source"),
    clustered: bool = Query(True, description="Return clustered results when available (default: True)")
):
    """
    Retrieve a paginated list of benches with high confidence detections.
    
    This endpoint returns benches that have been detected with confidence scores above the specified threshold.
    Results can be filtered by data source and sorted by various criteria including distance from a reference point,
    detection confidence, number of images, or creation date.
    
    **Clustering:**
    When `clustered=True` (default), returns clustered bench data that groups nearby benches together.
    Each cluster includes a representative bench and the list of all benches in the cluster.
    When `clustered=False`, returns individual benches as before.
    
    **Sorting Options:**
    - `distance`: Sort by distance from start_lat/start_lng (default)
    - `confidence`: Sort by highest detection confidence first
    - `images`: Sort by number of images per bench (or benches per cluster when clustered)
    - `recent`: Sort by most recently added benches
    
    **Data Sources:**
    - `osm`: OpenStreetMap data with computer vision detections
    - `mapillary`: Street-level imagery from Mapillary with AI detections
    """
    try:
        # Check if clustering is requested and available
        if clustered:
            clustered_service = ClusteredBenchService()
            if clustered_service.is_clustering_available():
                # Return clustered results
                return clustered_service.get_clustered_benches_filtered(
                    page=page,
                    page_size=page_size,
                    min_confidence=min_confidence,
                    start_lat=start_lat,
                    start_lng=start_lng,
                    source_filter=source,
                    sort_by=sort_by
                )
        
        # Fall back to individual bench results
        result = get_high_confidence_benches_filtered(
            page=page,
            page_size=page_size,
            min_confidence=min_confidence,
            start_lat=start_lat,
            start_lng=start_lng,
            source_filter=source,
            sort_by=sort_by
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve benches: {str(e)}"
        )


@app.get("/api/benches/source/{source}",
         summary="List Benches by Source",
         description="Get benches filtered by specific data source (OSM or Mapillary)",
         response_model=BenchListResponse,
         responses={
             400: {"model": EnhancedErrorResponse, "description": "Invalid source or parameters"},
             500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
         },
         tags=["benches"])
async def get_benches_by_source(
    source: str = Path(..., pattern="^(osm|mapillary)$", description="Data source filter"),
    page: int = Query(0, ge=0, le=1000, description="Page number (0-based)"),
    page_size: int = Query(PAGE_SIZE, ge=1, le=50, description="Items per page (max 50)"),
    min_confidence: float = Query(DEFAULT_MIN_CONFIDENCE, ge=0.0, le=1.0, description="Minimum detection confidence"),
    start_lat: float = Query(DEFAULT_START_LAT, ge=-90.0, le=90.0, description="Starting latitude for distance sorting"),
    start_lng: float = Query(DEFAULT_START_LNG, ge=-180.0, le=180.0, description="Starting longitude for distance sorting"),
    sort_by: str = Query("distance", pattern="^(distance|confidence|images|recent)$", description="Sort criteria")
):
    """
    Get benches filtered by a specific data source.
    
    This endpoint allows filtering benches by their original data source:
    - **OSM**: Traditional OpenStreetMap bench data with AI-enhanced detection
    - **Mapillary**: Benches detected from street-level imagery using computer vision
    
    For Mapillary data, this may use cached results or real-time queries depending on availability.
    """
    try:
        # For Mapillary, use the service if available
        if source == 'mapillary' and mapillary_service:
            # Use Mapillary service for stored benches
            benches_data = mapillary_service.get_stored_benches(
                center_lat=start_lat,
                center_lng=start_lng,
                radius_meters=2000,  # Larger radius for stored data
                limit=page_size
            )
            
            # Create pagination info
            pagination = PaginationInfo(
                page=page,
                page_size=len(benches_data),
                total_count=len(benches_data),
                total_pages=1,
                has_next=False
            )
            
            return BenchListResponse(benches=benches_data, pagination=pagination)
        
        # For OSM or if Mapillary service is not available
        result = get_high_confidence_benches_filtered(
            page=page,
            page_size=page_size,
            min_confidence=min_confidence,
            start_lat=start_lat,
            start_lng=start_lng,
            source_filter=source,
            sort_by=sort_by
        )
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get benches for source {source}: {str(e)}"
        )


@app.get("/api/benches/random",
         summary="Get Random Bench",
         description="Get a randomly selected bench that meets the specified criteria",
         response_model=RandomBenchResponse,
         responses={
             404: {"model": EnhancedErrorResponse, "description": "No benches found matching criteria"},
             500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
         },
         tags=["benches"])
async def get_random_bench(
    min_confidence: float = Query(DEFAULT_MIN_CONFIDENCE, ge=0.0, le=1.0, description="Minimum detection confidence"),
    source: Optional[str] = Query(None, pattern="^(osm|mapillary)$", description="Filter by data source")
):
    """
    Get a randomly selected bench that meets the specified criteria.
    
    This is useful for exploring the dataset or providing "discover" functionality
    in user interfaces. The randomization is performed at the database level
    for efficiency.
    """
    try:
        db = BenchDatabase()
        with db._get_connection() as conn:
            # Base query to get all qualifying bench IDs
            base_query = """
                SELECT DISTINCT b.id
                FROM benches b
                JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                JOIN detections d ON i.id = d.image_id
                WHERE d.has_bench = 1 AND d.max_confidence >= ?
                
                UNION
                
                SELECT DISTINCT b.id
                FROM benches b
                JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                JOIN ultralytics_detections ud ON i.id = ud.image_id
                WHERE ud.has_bench = 1 AND ud.max_confidence >= ?
            """
            
            # Add source filter if specified
            source_condition = ""
            query_params = [min_confidence, min_confidence]
            
            if source:
                source_condition = f" AND b.source = ?"
                query_params.append(source)
            
            # Get random bench ID
            random_query = f"""
                SELECT b.id
                FROM benches b
                WHERE b.id IN ({base_query}){source_condition}
                ORDER BY RANDOM()
                LIMIT 1
            """
            
            row = conn.execute(random_query, query_params).fetchone()
            
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No benches found matching the specified criteria"
                )
            
            bench_id = row['id']
            
            # Get detailed bench data for this random bench
            result = get_high_confidence_benches_filtered(
                page=0, 
                page_size=50,  # Get more to find our specific bench
                min_confidence=min_confidence,
                start_lat=DEFAULT_START_LAT,
                start_lng=DEFAULT_START_LNG,
                source_filter=source
            )
            
            # Find the specific bench in the results
            selected_bench = None
            for bench in result.benches:
                if bench.id == bench_id:
                    selected_bench = bench
                    break
            
            if not selected_bench:
                # Fallback: get bench details directly
                detail_query = """
                    SELECT 
                        b.id, b.provider_id, b.lat, b.lng, b.tags, b.source, b.external_id,
                        COUNT(DISTINCT i.id) as image_count,
                        GROUP_CONCAT(DISTINCT i.filename) as image_filenames,
                        GROUP_CONCAT(DISTINCT i.id) as image_ids
                    FROM benches b
                    JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                    WHERE b.id = ?
                    GROUP BY b.id
                """
                
                bench_row = conn.execute(detail_query, (bench_id,)).fetchone()
                
                if bench_row:
                    tags = {}
                    if bench_row['tags']:
                        try:
                            tags = json.loads(bench_row['tags'])
                        except json.JSONDecodeError:
                            pass
                    
                    image_filenames = bench_row['image_filenames'].split(',') if bench_row['image_filenames'] else []
                    image_ids = [int(x) for x in bench_row['image_ids'].split(',') if x] if bench_row['image_ids'] else []
                    
                    selected_bench = WebBenchData(
                        id=bench_row['id'],
                        provider_id=bench_row['provider_id'],
                        lat=bench_row['lat'],
                        lng=bench_row['lng'],
                        tags=tags,
                        source=bench_row['source'] or 'osm',
                        external_id=bench_row['external_id'],
                        best_confidence=min_confidence,  # Approximate
                        roboflow_confidence=0,
                        ultralytics_confidence=0,
                        mapillary_confidence=0,
                        detection_type='unknown',
                        has_segmentation=False,
                        image_count=bench_row['image_count'],
                        image_filenames=image_filenames,
                        image_ids=image_ids,
                        distance_meters=0,
                        distance_km=0
                    )
            
            if not selected_bench:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve random bench details"
                )
            
            return RandomBenchResponse(
                bench=selected_bench,
                selection_info={
                    "selected_from_pool": True,
                    "selection_criteria": {
                        "min_confidence": min_confidence,
                        "source_filter": source
                    }
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get random bench: {str(e)}"
        )


@app.get("/api/benches/bbox",
         summary="Get Benches in Bounding Box",
         description="Get benches within a geographic bounding box for map applications",
         response_model=Union[BboxBenchResponse, ClusteredBenchListResponse],
         responses={
             400: {"model": EnhancedErrorResponse, "description": "Invalid bounding box parameters"},
             500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
         },
         tags=["benches"])
async def get_benches_in_bbox(
    north: float = Query(..., ge=-90.0, le=90.0, description="Northern latitude boundary"),
    south: float = Query(..., ge=-90.0, le=90.0, description="Southern latitude boundary"),
    east: float = Query(..., ge=-180.0, le=180.0, description="Eastern longitude boundary"),
    west: float = Query(..., ge=-180.0, le=180.0, description="Western longitude boundary"),
    min_confidence: float = Query(DEFAULT_MIN_CONFIDENCE, ge=0.0, le=1.0, description="Minimum detection confidence"),
    source: Optional[str] = Query(None, pattern="^(osm|mapillary)$", description="Filter by data source"),
    sort_by: str = Query("distance", pattern="^(distance|confidence|images|recent)$", description="Sort criteria"),
    limit: int = Query(200, ge=1, le=500, description="Maximum number of results"),
    clustered: bool = Query(True, description="Return clustered results when available (default: True)")
):
    """
    Get benches within a geographic bounding box.
    
    This endpoint is optimized for map applications that need to display benches
    within a specific viewport. The bounding box is defined by north/south latitude
    boundaries and east/west longitude boundaries.
    
    **Clustering:**
    When `clustered=True` (default), returns clustered bench data for map display.
    This reduces visual clutter by grouping nearby benches together.
    
    **Geographic Validation:**
    - North must be greater than South
    - East must be greater than West
    - All coordinates must be within valid lat/lng ranges
    
    **Performance Notes:**
    - Results are limited to prevent excessive data transfer
    - Distance sorting uses the bounding box center as reference point
    """
    try:
        # Validate bounding box first
        if north <= south:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="North boundary must be greater than south boundary"
            )
        
        if east <= west:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="East boundary must be greater than west boundary"
            )
        
        # Check if clustering is requested and available
        if clustered:
            clustered_service = ClusteredBenchService()
            if clustered_service.is_clustering_available():
                # Return clustered results for bbox
                return clustered_service.get_clustered_benches_in_bbox(
                    north=north,
                    south=south,
                    east=east,
                    west=west,
                    min_confidence=min_confidence,
                    source_filter=source,
                    sort_by=sort_by,
                    limit=limit
                )
        
        # Fall back to individual bench results
        
        db = BenchDatabase()
        with db._get_connection() as conn:
            # Base query for benches within bounding box
            base_query = """
                SELECT DISTINCT b.id
                FROM benches b
                JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                JOIN detections d ON i.id = d.image_id
                WHERE d.has_bench = 1 AND d.max_confidence >= ?
                  AND b.lat BETWEEN ? AND ?
                  AND b.lng BETWEEN ? AND ?
                
                UNION
                
                SELECT DISTINCT b.id
                FROM benches b
                JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                JOIN ultralytics_detections ud ON i.id = ud.image_id
                WHERE ud.has_bench = 1 AND ud.max_confidence >= ?
                  AND b.lat BETWEEN ? AND ?
                  AND b.lng BETWEEN ? AND ?
            """
            
            # Add source filter if specified
            source_condition = ""
            query_params = [min_confidence, south, north, west, east, min_confidence, south, north, west, east]
            
            if source:
                source_condition = f" AND b.source = ?"
                query_params.append(source)
            
            # Determine sorting clause for bbox
            center_lat = (north + south) / 2
            center_lng = (east + west) / 2
            
            if sort_by == 'confidence':
                bbox_order_clause = 'best_confidence DESC, b.id'
            elif sort_by == 'images':
                bbox_order_clause = 'image_count DESC, best_confidence DESC, b.id'
            elif sort_by == 'recent':
                bbox_order_clause = 'b.id DESC'
            else:  # distance (default)
                bbox_order_clause = f'((b.lat - {center_lat}) * (b.lat - {center_lat}) + (b.lng - {center_lng}) * (b.lng - {center_lng})) ASC, best_confidence DESC'
            
            # Get detailed bench data within bbox
            query = f"""
                SELECT 
                    b.id, b.provider_id, b.lat, b.lng, b.tags, b.source, b.external_id,
                    COALESCE(rf_data.max_confidence, 0) as roboflow_confidence,
                    COALESCE(ul_data.max_confidence, 0) as ultralytics_confidence,
                    COALESCE(mp_data.max_confidence, 0) as mapillary_confidence,
                    COUNT(DISTINCT i.id) as image_count,
                    GROUP_CONCAT(DISTINCT i.filename) as image_filenames,
                    GROUP_CONCAT(DISTINCT i.id) as image_ids,
                    CASE 
                        WHEN COALESCE(rf_data.max_confidence, 0) >= COALESCE(ul_data.max_confidence, 0) AND COALESCE(rf_data.max_confidence, 0) >= COALESCE(mp_data.max_confidence, 0)
                        THEN COALESCE(rf_data.max_confidence, 0)
                        WHEN COALESCE(ul_data.max_confidence, 0) >= COALESCE(mp_data.max_confidence, 0)
                        THEN COALESCE(ul_data.max_confidence, 0)
                        ELSE COALESCE(mp_data.max_confidence, 0)
                    END as best_confidence
                FROM benches b
                JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                LEFT JOIN (
                    SELECT image_id, MAX(max_confidence) as max_confidence
                    FROM detections 
                    WHERE has_bench = 1
                    GROUP BY image_id
                ) rf_data ON i.id = rf_data.image_id
                LEFT JOIN (
                    SELECT image_id, MAX(max_confidence) as max_confidence
                    FROM ultralytics_detections 
                    WHERE has_bench = 1
                    GROUP BY image_id
                ) ul_data ON i.id = ul_data.image_id
                LEFT JOIN (
                    SELECT image_id, MAX(max_confidence) as max_confidence
                    FROM detections 
                    WHERE has_bench = 1 AND source = 'mapillary'
                    GROUP BY image_id
                ) mp_data ON i.id = mp_data.image_id
                WHERE b.id IN ({base_query}){source_condition}
                GROUP BY b.id
                HAVING best_confidence >= ?
                ORDER BY {bbox_order_clause}
                LIMIT ?
            """
            
            final_params = query_params + [min_confidence, limit]
            rows = conn.execute(query, final_params).fetchall()
            
            # Process results similar to get_high_confidence_benches_filtered
            benches = []
            
            for row in rows:
                # Parse tags if available
                tags = {}
                if row['tags']:
                    try:
                        tags = json.loads(row['tags'])
                    except json.JSONDecodeError:
                        pass
                
                # Calculate distance from center
                distance = calculate_distance(center_lat, center_lng, row['lat'], row['lng'])
                
                # Get image filenames and IDs
                image_filenames = row['image_filenames'].split(',') if row['image_filenames'] else []
                image_ids = [int(x) for x in row['image_ids'].split(',') if x] if row['image_ids'] else []
                
                # Determine best confidence and detection type
                roboflow_conf = row['roboflow_confidence'] or 0
                ultralytics_conf = row['ultralytics_confidence'] or 0
                mapillary_conf = row['mapillary_confidence'] or 0
                best_confidence = max(roboflow_conf, ultralytics_conf, mapillary_conf)
                
                # Determine detection type based on source and confidence
                if row['source'] == 'mapillary':
                    detection_type = 'mapillary'
                elif ultralytics_conf > 0 and ultralytics_conf >= roboflow_conf * 0.95:
                    detection_type = 'ultralytics'
                else:
                    detection_type = 'roboflow' if roboflow_conf > ultralytics_conf else 'ultralytics'
                
                bench_data = WebBenchData(
                    id=row['id'],
                    provider_id=row['provider_id'],
                    lat=row['lat'],
                    lng=row['lng'],
                    tags=tags,
                    source=row['source'] or 'osm',
                    external_id=row['external_id'],
                    best_confidence=round(best_confidence, 3),
                    roboflow_confidence=round(roboflow_conf, 3),
                    ultralytics_confidence=round(ultralytics_conf, 3),
                    mapillary_confidence=round(mapillary_conf, 3),
                    detection_type=detection_type,
                    has_segmentation=ultralytics_conf > 0 or mapillary_conf > 0,
                    image_count=row['image_count'],
                    image_filenames=image_filenames,
                    image_ids=image_ids,
                    distance_meters=round(distance),
                    distance_km=round(distance / 1000, 2)
                )
                
                benches.append(bench_data)
            
            return BboxBenchResponse(
                benches=benches,
                total_count=len(benches),
                bbox={
                    "north": north,
                    "south": south,
                    "east": east,
                    "west": west
                },
                query_info={
                    "center_lat": center_lat,
                    "center_lng": center_lng,
                    "area_km2": round(calculate_distance(south, west, north, east) / 1000000, 2),
                    "sort_by": sort_by,
                    "source_filter": source,
                    "min_confidence": min_confidence
                }
            )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get benches in bounding box: {str(e)}"
        )


# SEARCH AND CONFIGURATION ENDPOINTS
@app.get("/api/searches",
         summary="List Available Searches",
         description="Get list of completed search operations with bench counts",
         response_model=SearchListResponse,
         responses={
             500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
         },
         tags=["search"])
async def get_searches():
    """
    Get a list of completed search operations with metadata.
    
    This endpoint returns historical search data that can be used to:
    - Display previous search locations in the UI
    - Show search statistics and bench counts
    - Enable users to revisit successful search areas
    
    Only completed searches with associated bench data are returned.
    """
    try:
        db = BenchDatabase()
        with db._get_connection() as conn:
            query = """
                SELECT id, query, start_lat, start_lng, search_radius, created_at, status,
                       (SELECT COUNT(*) FROM benches WHERE search_id = s.id) as bench_count
                FROM searches s
                WHERE status = 'completed'
                ORDER BY created_at DESC
            """
            rows = conn.execute(query).fetchall()
            
            searches = []
            for row in rows:
                search = SearchSummary(
                    id=row['id'],
                    query=row['query'],
                    start_lat=row['start_lat'],
                    start_lng=row['start_lng'],
                    search_radius=row['search_radius'],
                    bench_count=row['bench_count'],
                    created_at=row['created_at']
                )
                searches.append(search)
            
            return SearchListResponse(searches=searches)
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve searches: {str(e)}"
        )


@app.get("/api/config",
         summary="Get Application Configuration",
         description="Get default configuration values for the frontend application",
         response_model=ConfigResponse,
         tags=["config"])
async def get_config():
    """
    Get application configuration for frontend initialization.
    
    This endpoint provides default values that the frontend can use for:
    - Initial map center coordinates
    - Default confidence thresholds
    - Pagination settings
    - API version information
    
    These values are used to initialize the user interface with sensible defaults
    based on the available data in the system.
    """
    return ConfigResponse(
        default_start_lat=DEFAULT_START_LAT,
        default_start_lng=DEFAULT_START_LNG,
        default_min_confidence=DEFAULT_MIN_CONFIDENCE,
        page_size=PAGE_SIZE
    )


@app.get("/api/info",
         summary="Get API Information",
         description="Get comprehensive API information including capabilities and limits",
         response_model=Dict[str, Any],
         tags=["config"])
async def get_api_info():
    """
    Get detailed API information including capabilities and usage limits.
    
    This endpoint provides comprehensive metadata about the API including:
    - Supported data sources and detection models
    - Available features and endpoints
    - Usage limits and performance constraints
    - Version information
    """
    return {
        "name": "Bench Finder API",
        "version": "2.0.0",
        "description": "A comprehensive API for discovering and analyzing public benches using computer vision",
        "supported_sources": ["osm", "mapillary"],
        "supported_detection_models": ["roboflow", "ultralytics", "mapillary"],
        "features": [
            "spatial_search",
            "confidence_filtering",
            "multi_source_data",
            "image_analysis",
            "detection_visualization",
            "statistics_analytics",
            "bbox_queries",
            "random_discovery"
        ],
        "limits": {
            "max_page_size": 50,
            "max_bbox_results": 500,
            "max_search_radius": 10000,
            "max_mapillary_limit": 5000
        },
        "endpoints": {
            "benches": "/api/benches",
            "bench_by_source": "/api/benches/source/{source}",
            "random_bench": "/api/benches/random",
            "bbox_search": "/api/benches/bbox",
            "searches": "/api/searches",
            "config": "/api/config",
            "health": "/health",
            "docs": "/docs",
            "redoc": "/redoc"
        },
        "mapillary_enabled": mapillary_service is not None,
        "documentation_urls": {
            "openapi_json": "/openapi.json",
            "swagger_ui": "/docs",
            "redoc": "/redoc"
        }
    }


# IMAGE AND DETECTION ENDPOINTS
@app.get("/images/{filename}",
         summary="Serve Bench Images",
         description="Serve bench images from the images directory",
         response_class=FileResponse,
         responses={
             404: {"model": EnhancedErrorResponse, "description": "Image not found"},
             500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
         },
         tags=["images"])
async def serve_image(filename: str = Path(..., description="Image filename")):
    """
    Serve bench images from the configured images directory.
    
    This endpoint serves static image files that have been captured and processed
    as part of the bench detection pipeline. Images are served directly from
    the filesystem for optimal performance.
    
    **Security Notes:**
    - Only files within the configured images directory are served
    - Path traversal attacks are prevented by FastAPI's path validation
    - File existence is validated before serving
    """
    try:
        images_path = os.path.abspath(IMAGES_DIR)
        file_path = os.path.join(images_path, filename)
        
        # Security check: ensure the resolved path is within the images directory
        if not os.path.abspath(file_path).startswith(images_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image not found"
            )
        
        if not os.path.exists(file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image '{filename}' not found"
            )
        
        return FileResponse(
            file_path,
            media_type="image/jpeg",  # Assuming JPEG images, could be made dynamic
            headers={"Cache-Control": "public, max-age=3600"}  # Cache for 1 hour
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to serve image: {str(e)}"
        )


@app.get("/api/image/{image_id}/segmentation",
         summary="Get Detection Visualization Data",
         description="Get detection visualization data for a specific image (segmentation and bounding boxes)",
         response_model=SegmentationData,
         responses={
             404: {"model": EnhancedErrorResponse, "description": "Image or detection data not found"},
             500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
         },
         tags=["images"])
async def get_image_segmentation(
    image_id: int = Path(..., ge=1, description="Image ID")
):
    """
    Get detection visualization data for a specific image.
    
    This endpoint returns detection data that can be used to visualize:
    - **Segmentation polygons** from Ultralytics YOLO models
    - **Bounding boxes** from Roboflow models
    - **Combined visualizations** when both are available
    
    The response includes the original image filename, detection coordinates,
    confidence scores, and metadata needed for accurate visualization overlay.
    
    **Detection Types:**
    - `segmentation`: Polygon-based detection outlines
    - `bounding_box`: Rectangular detection regions
    - `both`: Combined segmentation and bounding box data
    """
    try:
        db = BenchDatabase()
        with db._get_connection() as conn:
            # Get image filename first
            image_query = "SELECT filename FROM images WHERE id = ?"
            image_row = conn.execute(image_query, (image_id,)).fetchone()
            
            if not image_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Image with ID {image_id} not found"
                )
            
            filename = image_row['filename']
            
            # Initialize result data
            bench_detections = []
            roboflow_detections = []
            image_shape = None
            max_confidence = 0.0
            detection_sources = []
            
            # Try to get Ultralytics segmentation data
            ultralytics_query = """
                SELECT ud.bench_detections, ud.full_response, ud.max_confidence
                FROM ultralytics_detections ud
                WHERE ud.image_id = ? AND ud.has_bench = 1
                ORDER BY ud.max_confidence DESC
                LIMIT 1
            """
            
            ultralytics_row = conn.execute(ultralytics_query, (image_id,)).fetchone()
            
            if ultralytics_row:
                bench_detections = json.loads(ultralytics_row['bench_detections']) if ultralytics_row['bench_detections'] else []
                full_response = json.loads(ultralytics_row['full_response']) if ultralytics_row['full_response'] else {}
                
                # Extract image dimensions from full response if available
                if 'images' in full_response and len(full_response['images']) > 0:
                    image_shape = full_response['images'][0].get('shape', None)
                
                max_confidence = max(max_confidence, ultralytics_row['max_confidence'] or 0.0)
                detection_sources.append('ultralytics')
            
            # Try to get Roboflow bounding box data
            roboflow_query = """
                SELECT d.detections, d.max_confidence
                FROM detections d
                WHERE d.image_id = ? AND d.has_bench = 1
                ORDER BY d.max_confidence DESC
                LIMIT 1
            """
            
            roboflow_row = conn.execute(roboflow_query, (image_id,)).fetchone()
            
            if roboflow_row:
                roboflow_detections = json.loads(roboflow_row['detections']) if roboflow_row['detections'] else []
                max_confidence = max(max_confidence, roboflow_row['max_confidence'] or 0.0)
                detection_sources.append('roboflow')
            
            # Check if we have any detection data
            if not bench_detections and not roboflow_detections:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No detection data found for image ID {image_id}"
                )
            
            # Determine detection type
            if bench_detections and roboflow_detections:
                detection_type = 'both'
                source = 'both'
            elif bench_detections:
                detection_type = 'segmentation'
                source = 'ultralytics'
            else:
                detection_type = 'bounding_box'
                source = 'roboflow'
            
            return SegmentationData(
                filename=filename,
                detection_type=detection_type,
                bench_detections=bench_detections,
                image_shape=image_shape,
                segmentation_available=len(bench_detections) > 0,
                roboflow_detections=roboflow_detections,
                bounding_box_available=len(roboflow_detections) > 0,
                confidence_score=max_confidence,
                source=source
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve detection data: {str(e)}"
        )


@app.get("/api/bench/{bench_id}/images",
         summary="Get Bench Images",
         description="Get all images for a specific bench with metadata",
         response_model=ImageListResponse,
         responses={
             404: {"model": EnhancedErrorResponse, "description": "Bench not found"},
             500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
         },
         tags=["images"])
async def get_bench_images(
    bench_id: int = Path(..., ge=1, description="Bench ID")
):
    """
    Get all images associated with a specific bench.
    
    This endpoint returns comprehensive image metadata including:
    - Image filenames and file paths
    - Capture headings (camera direction)
    - File sizes and capture status
    - Error information for failed captures
    
    Images are sorted by heading to provide a consistent viewing order
    representing different viewpoints around the bench.
    
    **Use Cases:**
    - Image gallery displays
    - 360-degree bench viewing
    - Debugging capture issues
    - Metadata analysis
    """
    try:
        db = BenchDatabase()
        with db._get_connection() as conn:
            # Verify bench exists
            bench_check_query = "SELECT id FROM benches WHERE id = ?"
            bench_exists = conn.execute(bench_check_query, (bench_id,)).fetchone()
            
            if not bench_exists:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Bench with ID {bench_id} not found"
                )
            
            # Get all images for the bench
            query = """
                SELECT i.id, i.bench_id, i.heading, i.filename, i.filepath, i.file_size,
                       i.capture_success, i.capture_error, i.created_at
                FROM images i
                WHERE i.bench_id = ? AND i.capture_success = 1
                ORDER BY i.heading
            """
            
            rows = conn.execute(query, (bench_id,)).fetchall()
            
            images = []
            for row in rows:
                image = ImageResponse(
                    id=row['id'],
                    bench_id=row['bench_id'],
                    heading=row['heading'],
                    filepath=row['filepath'],
                    filename=row['filename'],
                    file_size=row['file_size'],
                    capture_success=bool(row['capture_success']),
                    capture_error=row['capture_error'],
                    created_at=row['created_at']
                )
                images.append(image)
            
            return ImageListResponse(images=images)
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve bench images: {str(e)}"
        )


# MAPILLARY ENDPOINTS
@app.post("/api/mapillary/search",
          summary="Search Mapillary for Benches",
          description="Search for bench detections using Mapillary API and store results in database",
          response_model=Dict[str, Any],
          responses={
              400: {"model": EnhancedErrorResponse, "description": "Invalid request parameters"},
              503: {"model": EnhancedErrorResponse, "description": "Mapillary service not available"},
              500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
          },
          tags=["mapillary"])
async def search_mapillary(
    search_request: MapillarySearchRequest = Body(..., description="Mapillary search parameters")
):
    """
    Search for bench detections using the Mapillary API.
    
    This endpoint performs real-time searches against Mapillary's street-level imagery database
    to find benches detected by their AI models. Results are stored in the local database
    for future retrieval and analysis.
    
    **Process:**
    1. Query Mapillary API for images within the specified area
    2. Filter for images with bench detections
    3. Download detection metadata and optionally images
    4. Store results in local database with proper attribution
    
    **Requirements:**
    - Valid Mapillary API token configured
    - Mapillary service properly initialized
    - Sufficient API quota for the requested search area
    
    **Limits:**
    - Search radius: 10m - 10km
    - Result limit: 1 - 5000 images
    - API rate limits apply per Mapillary's terms
    """
    if not mapillary_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mapillary integration is not available. Please configure MAPILLARY_ACCESS_TOKEN."
        )
    
    try:
        # Perform the search using the Mapillary service
        result = mapillary_service.search_and_store_benches(
            center_lat=search_request.center_lat,
            center_lng=search_request.center_lng,
            radius_meters=search_request.radius_meters,
            limit=search_request.limit
        )
        
        # Convert result to dict for JSON response
        return result.model_dump()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mapillary search failed: {str(e)}"
        )


@app.get("/api/mapillary/stored",
         summary="Get Stored Mapillary Data",
         description="Get previously stored Mapillary bench detections from local database",
         response_model=Dict[str, Any],
         responses={
             400: {"model": EnhancedErrorResponse, "description": "Invalid query parameters"},
             503: {"model": EnhancedErrorResponse, "description": "Mapillary service not available"},
             500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
         },
         tags=["mapillary"])
async def get_stored_mapillary(
    center_lat: float = Query(..., ge=-90.0, le=90.0, description="Center latitude"),
    center_lng: float = Query(..., ge=-180.0, le=180.0, description="Center longitude"),
    radius_meters: int = Query(1000, ge=10, le=50000, description="Search radius in meters"),
    limit: int = Query(1000, ge=1, le=5000, description="Maximum number of results")
):
    """
    Get stored Mapillary bench detections from the local database.
    
    This endpoint retrieves previously cached Mapillary data without making new API calls.
    It's useful for:
    - Displaying known bench locations from Mapillary
    - Avoiding repeated API calls for the same area
    - Analyzing historical detection data
    
    **Data Sources:**
    - Previously executed Mapillary searches
    - Cached detection results and metadata
    - Associated image URLs and detection confidence scores
    
    **Performance:**
    - Fast response times (local database query)
    - No API rate limit consumption
    - Supports larger radius searches than live API
    """
    if not mapillary_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mapillary integration is not available"
        )
    
    try:
        # Get stored detections from the service
        images = mapillary_service.get_stored_benches(
            center_lat=center_lat,
            center_lng=center_lng,
            radius_meters=radius_meters,
            limit=limit
        )
        
        # Format response similar to Flask version
        result = {
            'images': [img.model_dump() for img in images],
            'total_images': len(images),
            'total_detections': sum(len(img.image_filenames) for img in images if hasattr(img, 'image_filenames'))
        }
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stored Mapillary data: {str(e)}"
        )


@app.get("/api/mapillary/statistics",
         summary="Get Mapillary Statistics",
         description="Get statistics about Mapillary bench detections",
         response_model=Dict[str, Any],
         responses={
             503: {"model": EnhancedErrorResponse, "description": "Mapillary service not available"},
             500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
         },
         tags=["mapillary"])
async def get_mapillary_statistics(
    center_lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Center latitude for area-specific stats"),
    center_lng: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Center longitude for area-specific stats"),
    radius_meters: Optional[int] = Query(None, ge=100, le=50000, description="Radius for area-specific stats")
):
    """
    Get comprehensive statistics about Mapillary bench detections.
    
    This endpoint provides analytics about the Mapillary data in the system:
    - **Global Statistics**: Total benches, detections, coverage area
    - **Area-Specific Statistics**: Stats for a specific geographic region
    - **Quality Metrics**: Average confidence scores, detection density
    - **Coverage Analysis**: Geographic distribution and data completeness
    
    **Use Cases:**
    - Data quality assessment
    - Coverage planning for new searches
    - Performance monitoring and reporting
    - Research and analysis workflows
    """
    if not mapillary_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mapillary integration is not available"
        )
    
    try:
        # Get statistics from the Mapillary service
        stats = mapillary_service.get_detection_statistics(
            center_lat=center_lat,
            center_lng=center_lng,
            radius_meters=radius_meters
        )
        
        return stats.model_dump()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get Mapillary statistics: {str(e)}"
        )


@app.put("/api/mapillary/refresh/{mapillary_image_id}",
         summary="Refresh Mapillary Image Detections",
         description="Refresh detections for a specific Mapillary image",
         response_model=Dict[str, Any],
         responses={
             404: {"model": EnhancedErrorResponse, "description": "Image not found or no detections available"},
             503: {"model": EnhancedErrorResponse, "description": "Mapillary service not available"},
             500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
         },
         tags=["mapillary"])
async def refresh_mapillary_image(
    mapillary_image_id: str = Path(..., description="Mapillary image ID")
):
    """
    Refresh detection data for a specific Mapillary image.
    
    This endpoint re-fetches detection data for a single image from Mapillary's API.
    It's useful for:
    - Updating detection data after Mapillary model improvements
    - Fixing corrupted or incomplete detection records
    - Refreshing confidence scores and metadata
    
    **Process:**
    1. Query Mapillary API for latest detection data
    2. Update local database with new information
    3. Return updated detection results
    
    **Rate Limiting:**
    Use sparingly as each call consumes API quota.
    """
    if not mapillary_service:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mapillary integration is not available"
        )
    
    try:
        # Refresh detections for the specific image
        result = mapillary_service.refresh_detections_for_image(mapillary_image_id)
        
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Image '{mapillary_image_id}' not found or no detections available"
            )
        
        return result.model_dump()
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh detections: {str(e)}"
        )


@app.get("/api/mapillary/config",
         summary="Get Mapillary Configuration",
         description="Get Mapillary integration configuration and status",
         response_model=Dict[str, Any],
         tags=["mapillary"])
async def get_mapillary_config():
    """
    Get Mapillary integration configuration and capabilities.
    
    This endpoint provides information about:
    - Integration status (enabled/disabled)
    - Default search parameters
    - Supported detection types
    - API limits and constraints
    """
    return {
        'mapillary_enabled': mapillary_service is not None,
        'default_radius_meters': 1000,
        'default_limit': 1000,
        'supported_detection_types': ['object--bench'],
        'max_radius_meters': 10000,
        'max_limit': 5000,
        'features': {
            'search_and_store': mapillary_service is not None,
            'stored_data_retrieval': mapillary_service is not None,
            'statistics': mapillary_service is not None,
            'image_refresh': mapillary_service is not None
        }
    }


# REPORTING ENDPOINTS
@app.post("/api/benches/{bench_id}/report",
          summary="Report Bad Bench Detection",
          description="Report a bad bench detection with optional description and image data",
          response_model=Dict[str, Any],
          responses={
              400: {"model": EnhancedErrorResponse, "description": "Invalid bench ID or request data"},
              404: {"model": EnhancedErrorResponse, "description": "Bench not found"},
              500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
          },
          tags=["reporting"])
async def report_bad_bench(
    bench_id: int = Path(..., gt=0, description="Bench ID to report"),
    request: Request,
    report_type: str = Body("bad_detection", description="Type of report"),
    description: Optional[str] = Body(None, description="Optional description of the issue"),
    image_id: Optional[int] = Body(None, description="Specific image ID being reported"),
    user_location_lat: Optional[float] = Body(None, description="User's GPS latitude"),
    user_location_lng: Optional[float] = Body(None, description="User's GPS longitude")
):
    """
    Report a bad bench detection.
    
    This endpoint allows users to report issues with bench detections, such as:
    - **bad_detection**: AI incorrectly identified a bench where there isn't one
    - **incorrect_location**: Bench location is wrong
    - **poor_image_quality**: Image quality makes detection unreliable
    - **other**: Other issues (requires description)
    
    **Process:**
    1. Validate bench exists in database
    2. Store report with metadata (user agent, IP, timestamp)
    3. Optionally copy the reported image for review
    4. Return confirmation of successful report
    
    **Privacy:**
    Only basic metadata is stored for spam prevention and debugging.
    """
    try:
        from bench_finder.models.models import BenchReport, Bench, Image
        from bench_finder.services.database import BenchDatabase
        import shutil
        import os
        from datetime import datetime
        
        db = BenchDatabase()
        
        with db._get_connection() as conn:
            # Verify bench exists
            bench_row = conn.execute(
                "SELECT id, provider_id, lat, lng, source FROM benches WHERE id = ?", 
                [bench_id]
            ).fetchone()
            
            if not bench_row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Bench with ID {bench_id} not found"
                )
            
            # Verify image exists if provided
            reported_image_filename = None
            if image_id:
                image_row = conn.execute(
                    "SELECT id, filename, filepath FROM images WHERE id = ? AND bench_id = ?",
                    [image_id, bench_id]
                ).fetchone()
                
                if image_row and image_row['filename']:
                    # Copy the image for review purposes
                    source_path = os.path.join(IMAGES_DIR, image_row['filename'])
                    if os.path.exists(source_path):
                        # Create reports directory if it doesn't exist
                        reports_dir = os.path.join(IMAGES_DIR, 'reports')
                        os.makedirs(reports_dir, exist_ok=True)
                        
                        # Create unique filename for the report
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        reported_image_filename = f"report_{bench_id}_{timestamp}_{image_row['filename']}"
                        dest_path = os.path.join(reports_dir, reported_image_filename)
                        
                        try:
                            shutil.copy2(source_path, dest_path)
                        except Exception as e:
                            print(f"Warning: Failed to copy reported image: {e}")
                            reported_image_filename = None
            
            # Get client information
            user_agent = request.headers.get('user-agent', '')
            client_host = request.client.host if request.client else None
            
            # Insert report
            result = conn.execute(
                """
                INSERT INTO bench_reports (
                    bench_id, image_id, report_type, description, user_agent, ip_address,
                    user_location_lat, user_location_lng, reported_image_filename,
                    metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    bench_id, image_id, report_type, description, user_agent, client_host,
                    user_location_lat, user_location_lng, reported_image_filename,
                    json.dumps({
                        'bench_source': bench_row['source'],
                        'bench_provider_id': bench_row['provider_id'],
                        'timestamp': datetime.now().isoformat()
                    }),
                    datetime.now()
                ]
            )
            
            report_id = result.lastrowid
            conn.commit()
            
            return {
                'success': True,
                'report_id': report_id,
                'message': 'Thank you for your report. It will be reviewed by our team.',
                'bench_id': bench_id,
                'report_type': report_type,
                'created_at': datetime.now().isoformat()
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit report: {str(e)}"
        )


@app.post("/api/missing-benches",
          summary="Report Missing Bench",
          description="Report a missing bench at a specific location with optional photo",
          response_model=Dict[str, Any],
          responses={
              400: {"model": EnhancedErrorResponse, "description": "Invalid location or request data"},
              413: {"model": EnhancedErrorResponse, "description": "Image file too large"},
              500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
          },
          tags=["reporting"])
async def report_missing_bench(
    request: Request,
    lat: float = Body(..., ge=-90.0, le=90.0, description="Bench latitude"),
    lng: float = Body(..., ge=-180.0, le=180.0, description="Bench longitude"),
    description: Optional[str] = Body(None, description="Description of the bench"),
    location_method: str = Body("gps", description="How location was determined (gps, map_click)"),
    user_location_lat: Optional[float] = Body(None, description="User's GPS latitude"),
    user_location_lng: Optional[float] = Body(None, description="User's GPS longitude"),
    accuracy_meters: Optional[float] = Body(None, description="GPS accuracy in meters"),
    image_data: Optional[str] = Body(None, description="Base64 encoded image data")
):
    """
    Report a missing bench at a specific location.
    
    This endpoint allows users to report benches that exist in real life but are not
    in the system. It supports two location methods:
    
    **GPS Location ("RIGHT HERE" mode):**
    - Uses the user's current GPS coordinates
    - Includes accuracy information
    - Best for reporting benches at user's current location
    
    **Map Click ("MAP VIEW" mode):**
    - User clicks on a map to specify location
    - More precise for distant locations
    - Allows planning and remote reporting
    
    **Photo Upload:**
    - Optional base64-encoded image of the bench
    - Helps verify the report during review
    - Images are resized and compressed automatically
    
    **Process:**
    1. Validate location coordinates
    2. Process and store uploaded image (if provided)
    3. Store report with metadata
    4. Return confirmation with report ID
    """
    try:
        from bench_finder.models.models import MissingBenchReport
        from bench_finder.services.database import BenchDatabase
        import base64
        import os
        from PIL import Image
        from datetime import datetime
        import io
        
        db = BenchDatabase()
        
        # Process uploaded image if provided
        uploaded_image_filename = None
        if image_data:
            try:
                # Decode base64 image
                if ',' in image_data:
                    header, image_data = image_data.split(',', 1)
                
                image_bytes = base64.b64decode(image_data)
                
                # Check file size (max 10MB)
                if len(image_bytes) > 10 * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Image file too large. Maximum size is 10MB."
                    )
                
                # Process with PIL
                image = Image.open(io.BytesIO(image_bytes))
                
                # Convert to RGB if necessary
                if image.mode in ('RGBA', 'P'):
                    image = image.convert('RGB')
                
                # Resize if too large (max 2048px on longest side)
                max_size = 2048
                if max(image.size) > max_size:
                    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # Save processed image
                missing_reports_dir = os.path.join(IMAGES_DIR, 'missing_reports')
                os.makedirs(missing_reports_dir, exist_ok=True)
                
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # Include milliseconds
                uploaded_image_filename = f"missing_{timestamp}_{lat}_{lng}.jpg"
                image_path = os.path.join(missing_reports_dir, uploaded_image_filename)
                
                image.save(image_path, 'JPEG', quality=85, optimize=True)
                
            except Exception as e:
                print(f"Warning: Failed to process uploaded image: {e}")
                uploaded_image_filename = None
        
        # Get client information
        user_agent = request.headers.get('user-agent', '')
        client_host = request.client.host if request.client else None
        
        with db._get_connection() as conn:
            # Insert missing bench report
            result = conn.execute(
                """
                INSERT INTO missing_bench_reports (
                    lat, lng, description, user_agent, ip_address,
                    user_location_lat, user_location_lng, location_method,
                    uploaded_image_filename, accuracy_meters, metadata, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    lat, lng, description, user_agent, client_host,
                    user_location_lat, user_location_lng, location_method,
                    uploaded_image_filename, accuracy_meters,
                    json.dumps({
                        'timestamp': datetime.now().isoformat(),
                        'has_image': uploaded_image_filename is not None
                    }),
                    datetime.now()
                ]
            )
            
            report_id = result.lastrowid
            conn.commit()
            
            return {
                'success': True,
                'report_id': report_id,
                'message': 'Thank you for reporting this missing bench. It will be reviewed by our team.',
                'location': {'lat': lat, 'lng': lng},
                'location_method': location_method,
                'has_image': uploaded_image_filename is not None,
                'created_at': datetime.now().isoformat()
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit missing bench report: {str(e)}"
        )


# STATISTICS ENDPOINTS
@app.get("/api/statistics/source/{source}",
         summary="Get Statistics by Source",
         description="Get comprehensive statistics filtered by data source",
         response_model=Dict[str, Any],
         responses={
             400: {"model": EnhancedErrorResponse, "description": "Invalid source parameter"},
             500: {"model": EnhancedErrorResponse, "description": "Internal server error"}
         },
         tags=["statistics"])
async def get_statistics_by_source(
    source: str = Path(..., pattern="^(osm|mapillary)$", description="Data source"),
    center_lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Center latitude for area-specific stats"),
    center_lng: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Center longitude for area-specific stats"),
    radius_meters: Optional[int] = Query(None, ge=100, le=50000, description="Radius for area-specific stats")
):
    """
    Get comprehensive statistics filtered by data source.
    
    This endpoint provides detailed analytics about bench data from specific sources:
    
    **OSM Statistics:**
    - Total benches from OpenStreetMap
    - Detection success rates
    - Geographic distribution
    - Data quality metrics
    
    **Mapillary Statistics:**
    - Street imagery detection results
    - Confidence score distributions
    - Coverage areas and detection density
    - API usage and cache statistics
    
    **Area Filtering:**
    When center coordinates and radius are provided, statistics are calculated
    only for the specified geographic area.
    """
    try:
        if source == 'mapillary' and mapillary_service:
            # Use Mapillary service for comprehensive stats
            stats = mapillary_service.get_detection_statistics(
                center_lat=center_lat,
                center_lng=center_lng,
                radius_meters=radius_meters,
                source='mapillary'
            )
            return stats.model_dump()
        
        # For OSM or when Mapillary service is not available, return basic stats
        # This would be implemented with direct database queries
        db = BenchDatabase()
        with db._get_connection() as conn:
            # Basic statistics query for the specified source
            base_query = """
                SELECT 
                    COUNT(DISTINCT b.id) as total_benches,
                    COUNT(DISTINCT i.id) as total_images,
                    COUNT(DISTINCT d.id) + COUNT(DISTINCT ud.id) as total_detections,
                    AVG(COALESCE(d.max_confidence, ud.max_confidence, 0)) as avg_confidence
                FROM benches b
                LEFT JOIN images i ON b.id = i.bench_id AND i.capture_success = 1
                LEFT JOIN detections d ON i.id = d.image_id AND d.has_bench = 1
                LEFT JOIN ultralytics_detections ud ON i.id = ud.image_id AND ud.has_bench = 1
                WHERE b.source = ?
            """
            
            query_params = [source]
            
            # Add geographic filtering if provided
            if center_lat is not None and center_lng is not None and radius_meters is not None:
                # Simple radius filter (can be enhanced with proper geographic calculations)
                lat_range = radius_meters / 111000  # Rough conversion to degrees
                lng_range = radius_meters / (111000 * math.cos(math.radians(center_lat)))
                
                base_query += """
                    AND b.lat BETWEEN ? AND ?
                    AND b.lng BETWEEN ? AND ?
                """
                query_params.extend([
                    center_lat - lat_range, center_lat + lat_range,
                    center_lng - lng_range, center_lng + lng_range
                ])
            
            row = conn.execute(base_query, query_params).fetchone()
            
            return {
                'source': source,
                'total_benches': row['total_benches'] or 0,
                'total_images': row['total_images'] or 0, 
                'total_detections': row['total_detections'] or 0,
                'avg_confidence': round(row['avg_confidence'] or 0, 3),
                'area_filtered': center_lat is not None and center_lng is not None,
                'area_center': {
                    'lat': center_lat,
                    'lng': center_lng,
                    'radius_meters': radius_meters
                } if center_lat is not None else None
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics for source {source}: {str(e)}"
        )


if __name__ == "__main__":
    print("🚀 Starting Bench Finder FastAPI server with uvicorn...")
    print("📚 API documentation will be available at: http://localhost:8866/docs")
    print("🔄 Alternative docs at: http://localhost:8866/redoc")
    
    uvicorn.run(
        "fastapi_server:app",
        host="0.0.0.0",
        port=8866,
        reload=True,
        log_level="info"
    )