#!/usr/bin/env python3
"""
Mapillary web server for displaying bench detections from Mapillary API.
"""

import os

from config import DATABASE_PATH
from flask import Flask, jsonify, render_template, request
from mapillary_service import create_mapillary_service
from schemas import MapillarySearchRequest


app = Flask(__name__)

# Configuration
MAPILLARY_ACCESS_TOKEN = os.getenv("MAPILLARY_ACCESS_TOKEN")
if not MAPILLARY_ACCESS_TOKEN:
    raise ValueError("MAPILLARY_ACCESS_TOKEN environment variable is required")

# Initialize Mapillary service
mapillary_service = create_mapillary_service(DATABASE_PATH, MAPILLARY_ACCESS_TOKEN)


@app.route("/mapillary")
def mapillary_index():
    """Serve the Mapillary bench finder page."""
    return render_template("mapillary_index.html")


@app.route("/api/mapillary/search", methods=["POST"])
def api_mapillary_search():
    """
    Search for bench detections using Mapillary API and store in database.

    POST body: {
        "center_lat": float,
        "center_lng": float,
        "radius_meters": int (optional, default 1000),
        "limit": int (optional, default 1000)
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        # Validate required fields
        if "center_lat" not in data or "center_lng" not in data:
            return jsonify({"error": "center_lat and center_lng are required"}), 400

        search_request = MapillarySearchRequest(
            center_lat=data["center_lat"],
            center_lng=data["center_lng"],
            radius_meters=data.get("radius_meters", 1000),
            limit=data.get("limit", 1000),
        )

        # Search and store bench detections
        result = mapillary_service.search_and_store_benches(
            center_lat=search_request.center_lat,
            center_lng=search_request.center_lng,
            radius_meters=search_request.radius_meters,
            limit=search_request.limit,
        )

        return jsonify(result.model_dump())

    except Exception:
        return jsonify({"error": f"Search failed: {e!s}"}), 500


@app.route("/api/mapillary/stored")
def api_mapillary_stored():
    """
    Get stored Mapillary bench detections from database.

    Query params:
        center_lat: float
        center_lng: float
        radius_meters: int (optional, default 1000)
        limit: int (optional, default 1000)
    """
    try:
        center_lat = request.args.get("center_lat", type=float)
        center_lng = request.args.get("center_lng", type=float)

        if center_lat is None or center_lng is None:
            return jsonify(
                {"error": "center_lat and center_lng parameters are required"}
            ), 400

        radius_meters = request.args.get("radius_meters", 1000, type=int)
        limit = request.args.get("limit", 1000, type=int)

        # Get stored detections
        images = mapillary_service.get_stored_benches(
            center_lat=center_lat,
            center_lng=center_lng,
            radius_meters=radius_meters,
            limit=limit,
        )

        # Convert to dict format for JSON response
        result = {
            "images": [img.model_dump() for img in images],
            "total_images": len(images),
            "total_detections": sum(len(img.detections) for img in images),
        }

        return jsonify(result)

    except Exception:
        return jsonify({"error": f"Failed to get stored detections: {e!s}"}), 500


@app.route("/api/mapillary/statistics")
def api_mapillary_statistics():
    """
    Get statistics about Mapillary bench detections.

    Query params (all optional):
        center_lat: float - for area-specific stats
        center_lng: float - for area-specific stats
        radius_meters: int - for area-specific stats
    """
    try:
        center_lat = request.args.get("center_lat", type=float)
        center_lng = request.args.get("center_lng", type=float)
        radius_meters = request.args.get("radius_meters", type=int)

        # Get statistics
        stats = mapillary_service.get_detection_statistics(
            center_lat=center_lat, center_lng=center_lng, radius_meters=radius_meters
        )

        return jsonify(stats.model_dump())

    except Exception:
        return jsonify({"error": f"Failed to get statistics: {e!s}"}), 500


@app.route("/api/mapillary/refresh/<mapillary_image_id>")
def api_mapillary_refresh(mapillary_image_id: str):
    """
    Refresh detections for a specific Mapillary image.

    Path param:
        mapillary_image_id: Mapillary image ID
    """
    try:
        result = mapillary_service.refresh_detections_for_image(mapillary_image_id)

        if result is None:
            return jsonify({"error": "Image not found or no detections available"}), 404

        return jsonify(result.model_dump())

    except Exception:
        return jsonify({"error": f"Failed to refresh detections: {e!s}"}), 500


@app.route("/api/mapillary/config")
def api_mapillary_config():
    """Get Mapillary configuration."""
    return jsonify(
        {
            "mapillary_enabled": True,
            "default_radius_meters": 1000,
            "default_limit": 1000,
            "supported_detection_types": ["object--bench"],
        }
    )


if __name__ == "__main__":
    # Ensure templates directory exists
    os.makedirs("templates", exist_ok=True)

    print("Starting Mapillary bench finder web server...")
    print(f"Database: {DATABASE_PATH}")
    print(f"Mapillary integration: {'✓' if MAPILLARY_ACCESS_TOKEN else '✗'}")
    print("Server will be available at: http://localhost:8867")

    app.run(debug=True, host="0.0.0.0", port=8867)
