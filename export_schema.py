#!/usr/bin/env python3
"""
Simple script to export FastAPI OpenAPI schema to JSON file.
This avoids the need to start the full server with all dependencies.
"""
import json
import os
from fastapi import FastAPI, HTTPException, Query, Path, Body
from fastapi.openapi.utils import get_openapi
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

# Create a minimal FastAPI app with the same structure as the main app
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
        {"name": "benches", "description": "Core bench discovery and listing operations"},
        {"name": "search", "description": "Search management and historical queries"},
        {"name": "images", "description": "Image serving and detection visualization"},
        {"name": "mapillary", "description": "Mapillary-specific operations and street imagery"},
        {"name": "statistics", "description": "Analytics and performance metrics"},
        {"name": "config", "description": "Application configuration and metadata"},
    ]
)

# Define the same Pydantic models as in the main application
class SortByEnum(str, Enum):
    distance = "distance"
    confidence = "confidence"
    images = "images"
    recent = "recent"

class SourceEnum(str, Enum):
    osm = "osm"
    mapillary = "mapillary"

class PaginationInfo(BaseModel):
    page: int = Field(..., ge=0, description="Current page number")
    page_size: int = Field(..., ge=1, le=50, description="Items per page")
    total_count: int = Field(..., ge=0, description="Total number of items")
    total_pages: int = Field(..., ge=0, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")

class WebBenchData(BaseModel):
    id: int = Field(..., description="Unique bench identifier")
    provider_id: Optional[str] = Field(None, description="External provider ID")
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude coordinate")
    lng: float = Field(..., ge=-180.0, le=180.0, description="Longitude coordinate")
    tags: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata tags")
    source: str = Field(..., description="Data source (osm or mapillary)")
    external_id: Optional[str] = Field(None, description="External system identifier")
    best_confidence: float = Field(..., ge=0.0, le=1.0, description="Highest detection confidence")
    roboflow_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Roboflow detection confidence")
    ultralytics_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Ultralytics detection confidence")
    mapillary_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Mapillary detection confidence")
    detection_type: str = Field(..., description="Primary detection method used")
    has_segmentation: bool = Field(..., description="Whether segmentation data is available")
    image_count: int = Field(..., ge=0, description="Number of associated images")
    image_filenames: List[str] = Field(default_factory=list, description="List of image filenames")
    image_ids: List[int] = Field(default_factory=list, description="List of image IDs")
    distance_meters: int = Field(..., ge=0, description="Distance from reference point in meters")
    distance_km: float = Field(..., ge=0.0, description="Distance from reference point in kilometers")

class BenchListResponse(BaseModel):
    benches: List[WebBenchData] = Field(..., description="List of bench data")
    pagination: PaginationInfo = Field(..., description="Pagination metadata")

class BboxBenchResponse(BaseModel):
    benches: List[WebBenchData] = Field(..., description="List of benches within bounding box")
    total_count: int = Field(..., ge=0, description="Total number of benches returned")
    bbox: Dict[str, float] = Field(..., description="Bounding box coordinates")
    query_info: Dict[str, Any] = Field(default_factory=dict, description="Query metadata")

class RandomBenchResponse(BaseModel):
    bench: WebBenchData = Field(..., description="Randomly selected bench")
    selection_info: Dict[str, Any] = Field(default_factory=dict, description="Selection metadata")

class SearchSummary(BaseModel):
    id: int = Field(..., description="Search identifier")
    query: str = Field(..., description="Search query term")
    start_lat: float = Field(..., ge=-90.0, le=90.0, description="Search center latitude")
    start_lng: float = Field(..., ge=-180.0, le=180.0, description="Search center longitude")
    search_radius: int = Field(..., ge=0, description="Search radius in meters")
    bench_count: int = Field(..., ge=0, description="Number of benches found")
    created_at: datetime = Field(..., description="When the search was created")

class SearchListResponse(BaseModel):
    searches: List[SearchSummary] = Field(..., description="List of historical searches")

class ImageResponse(BaseModel):
    id: int = Field(..., description="Image identifier")
    bench_id: int = Field(..., description="Associated bench ID")
    heading: int = Field(..., ge=0, le=360, description="Camera heading in degrees")
    filepath: Optional[str] = Field(None, description="File system path")
    filename: Optional[str] = Field(None, description="Image filename")
    file_size: Optional[int] = Field(None, ge=0, description="File size in bytes")
    capture_success: bool = Field(..., description="Whether capture was successful")
    capture_error: Optional[str] = Field(None, description="Error message if capture failed")
    created_at: datetime = Field(..., description="When the image was created")

class ImageListResponse(BaseModel):
    images: List[ImageResponse] = Field(..., description="List of images")

class SegmentationData(BaseModel):
    filename: str = Field(..., description="Image filename")
    detection_type: str = Field(..., description="Type of detection data available")
    bench_detections: List[Dict[str, Any]] = Field(default_factory=list, description="Segmentation detection data")
    image_shape: Optional[List[int]] = Field(None, description="Image dimensions [height, width]")
    segmentation_available: bool = Field(False, description="Whether segmentation data is available")
    roboflow_detections: List[Dict[str, Any]] = Field(default_factory=list, description="Roboflow detection data")
    bounding_box_available: bool = Field(False, description="Whether bounding box data is available")
    confidence_score: float = Field(0.0, ge=0.0, le=1.0, description="Detection confidence score")
    source: str = Field("unknown", description="Detection data source")

class ConfigResponse(BaseModel):
    default_start_lat: float = Field(..., description="Default starting latitude")
    default_start_lng: float = Field(..., description="Default starting longitude")
    default_min_confidence: float = Field(..., description="Default minimum confidence threshold")
    page_size: int = Field(..., description="Default page size")

class MapillarySearchRequest(BaseModel):
    center_lat: float = Field(..., ge=-90.0, le=90.0, description="Search center latitude")
    center_lng: float = Field(..., ge=-180.0, le=180.0, description="Search center longitude")
    radius_meters: int = Field(1000, ge=10, le=10000, description="Search radius in meters")
    limit: int = Field(1000, ge=1, le=5000, description="Maximum results to return")

class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")

# Define all the endpoints with their signatures (without implementations)
@app.get("/health", 
         summary="Health Check", 
         description="Check server and database status",
         response_model=Dict[str, str],
         tags=["config"])
async def health_check():
    """Check if the server is running and database is accessible."""
    pass

@app.get("/api/benches",
         summary="List Benches",
         description="Get paginated list of benches with high confidence detections",
         response_model=BenchListResponse,
         tags=["benches"])
async def get_benches(
    page: int = Query(0, ge=0, le=1000, description="Page number (0-based)"),
    page_size: int = Query(20, ge=1, le=50, description="Items per page"),
    min_confidence: float = Query(0.8, ge=0.0, le=1.0, description="Minimum detection confidence"),
    start_lat: float = Query(52.3613577, ge=-90.0, le=90.0, description="Starting latitude for distance sorting"),
    start_lng: float = Query(4.8666322, ge=-180.0, le=180.0, description="Starting longitude for distance sorting"),
    sort_by: SortByEnum = Query(SortByEnum.distance, description="Sort criteria"),
    source: Optional[SourceEnum] = Query(None, description="Filter by data source")
):
    """Retrieve a paginated list of benches with high confidence detections."""
    pass

@app.get("/api/benches/source/{source}",
         summary="List Benches by Source",
         description="Get benches filtered by specific data source",
         response_model=BenchListResponse,
         tags=["benches"])
async def get_benches_by_source(
    source: SourceEnum = Path(..., description="Data source filter"),
    page: int = Query(0, ge=0, le=1000, description="Page number (0-based)"),
    page_size: int = Query(20, ge=1, le=50, description="Items per page"),
    min_confidence: float = Query(0.8, ge=0.0, le=1.0, description="Minimum detection confidence"),
    start_lat: float = Query(52.3613577, ge=-90.0, le=90.0, description="Starting latitude"),
    start_lng: float = Query(4.8666322, ge=-180.0, le=180.0, description="Starting longitude"),
    sort_by: SortByEnum = Query(SortByEnum.distance, description="Sort criteria")
):
    """Get benches filtered by a specific data source."""
    pass

@app.get("/api/benches/random",
         summary="Get Random Bench",
         description="Get a randomly selected bench that meets the specified criteria",
         response_model=RandomBenchResponse,
         tags=["benches"])
async def get_random_bench(
    min_confidence: float = Query(0.8, ge=0.0, le=1.0, description="Minimum detection confidence"),
    source: Optional[SourceEnum] = Query(None, description="Filter by data source")
):
    """Get a randomly selected bench that meets the specified criteria."""
    pass

@app.get("/api/benches/bbox",
         summary="Get Benches in Bounding Box",
         description="Get benches within a geographic bounding box for map applications",
         response_model=BboxBenchResponse,
         tags=["benches"])
async def get_benches_in_bbox(
    north: float = Query(..., ge=-90.0, le=90.0, description="Northern latitude boundary"),
    south: float = Query(..., ge=-90.0, le=90.0, description="Southern latitude boundary"),
    east: float = Query(..., ge=-180.0, le=180.0, description="Eastern longitude boundary"),
    west: float = Query(..., ge=-180.0, le=180.0, description="Western longitude boundary"),
    min_confidence: float = Query(0.8, ge=0.0, le=1.0, description="Minimum detection confidence"),
    source: Optional[SourceEnum] = Query(None, description="Filter by data source"),
    sort_by: SortByEnum = Query(SortByEnum.distance, description="Sort criteria"),
    limit: int = Query(200, ge=1, le=500, description="Maximum number of results")
):
    """Get benches within a geographic bounding box."""
    pass

@app.get("/api/searches",
         summary="List Available Searches",
         description="Get list of completed search operations with bench counts",
         response_model=SearchListResponse,
         tags=["search"])
async def get_searches():
    """Get a list of completed search operations with metadata."""
    pass

@app.get("/api/config",
         summary="Get Application Configuration",
         description="Get default configuration values for the frontend application",
         response_model=ConfigResponse,
         tags=["config"])
async def get_config():
    """Get application configuration for frontend initialization."""
    pass

@app.get("/api/info",
         summary="Get API Information",
         description="Get comprehensive API information including capabilities and limits",
         response_model=Dict[str, Any],
         tags=["config"])
async def get_api_info():
    """Get detailed API information including capabilities and usage limits."""
    pass

@app.get("/images/{filename}",
         summary="Serve Bench Images",
         description="Serve bench images from the images directory",
         tags=["images"])
async def serve_image(filename: str = Path(..., description="Image filename")):
    """Serve bench images from the configured images directory."""
    pass

@app.get("/api/image/{image_id}/segmentation",
         summary="Get Detection Visualization Data",
         description="Get detection visualization data for a specific image",
         response_model=SegmentationData,
         tags=["images"])
async def get_image_segmentation(
    image_id: int = Path(..., ge=1, description="Image ID")
):
    """Get detection visualization data for a specific image."""
    pass

@app.get("/api/bench/{bench_id}/images",
         summary="Get Bench Images",
         description="Get all images for a specific bench with metadata",
         response_model=ImageListResponse,
         tags=["images"])
async def get_bench_images(
    bench_id: int = Path(..., ge=1, description="Bench ID")
):
    """Get all images associated with a specific bench."""
    pass

@app.post("/api/mapillary/search",
          summary="Search Mapillary for Benches",
          description="Search for bench detections using Mapillary API and store results",
          response_model=Dict[str, Any],
          tags=["mapillary"])
async def search_mapillary(
    search_request: MapillarySearchRequest = Body(..., description="Mapillary search parameters")
):
    """Search for bench detections using the Mapillary API."""
    pass

@app.get("/api/mapillary/stored",
         summary="Get Stored Mapillary Data",
         description="Get previously stored Mapillary bench detections from local database",
         response_model=Dict[str, Any],
         tags=["mapillary"])
async def get_stored_mapillary(
    center_lat: float = Query(..., ge=-90.0, le=90.0, description="Center latitude"),
    center_lng: float = Query(..., ge=-180.0, le=180.0, description="Center longitude"),
    radius_meters: int = Query(1000, ge=10, le=50000, description="Search radius in meters"),
    limit: int = Query(1000, ge=1, le=5000, description="Maximum number of results")
):
    """Get stored Mapillary bench detections from the local database."""
    pass

@app.get("/api/mapillary/statistics",
         summary="Get Mapillary Statistics",
         description="Get statistics about Mapillary bench detections",
         response_model=Dict[str, Any],
         tags=["mapillary"])
async def get_mapillary_statistics(
    center_lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Center latitude for area-specific stats"),
    center_lng: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Center longitude for area-specific stats"),
    radius_meters: Optional[int] = Query(None, ge=100, le=50000, description="Radius for area-specific stats")
):
    """Get comprehensive statistics about Mapillary bench detections."""
    pass

@app.put("/api/mapillary/refresh/{mapillary_image_id}",
         summary="Refresh Mapillary Image Detections",
         description="Refresh detections for a specific Mapillary image",
         response_model=Dict[str, Any],
         tags=["mapillary"])
async def refresh_mapillary_image(
    mapillary_image_id: str = Path(..., description="Mapillary image ID")
):
    """Refresh detection data for a specific Mapillary image."""
    pass

@app.get("/api/mapillary/config",
         summary="Get Mapillary Configuration",
         description="Get Mapillary integration configuration and status",
         response_model=Dict[str, Any],
         tags=["mapillary"])
async def get_mapillary_config():
    """Get Mapillary integration configuration and capabilities."""
    pass

@app.get("/api/statistics/source/{source}",
         summary="Get Statistics by Source",
         description="Get comprehensive statistics filtered by data source",
         response_model=Dict[str, Any],
         tags=["statistics"])
async def get_statistics_by_source(
    source: SourceEnum = Path(..., description="Data source"),
    center_lat: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Center latitude for area-specific stats"),
    center_lng: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Center longitude for area-specific stats"),
    radius_meters: Optional[int] = Query(None, ge=100, le=50000, description="Radius for area-specific stats")
):
    """Get comprehensive statistics filtered by data source."""
    pass

def export_openapi_schema():
    """Export the OpenAPI schema to a JSON file."""
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags
    )
    
    # Write to file
    output_file = "openapi.json"
    with open(output_file, "w") as f:
        json.dump(schema, f, indent=2)
    
    print(f"✅ OpenAPI schema exported to {output_file}")
    print(f"📄 Schema contains {len(schema.get('paths', {}))} endpoints")
    print(f"📦 Schema contains {len(schema.get('components', {}).get('schemas', {}))} model definitions")
    
    return schema

if __name__ == "__main__":
    export_openapi_schema()