#!/usr/bin/env python3
"""
Web server for displaying bench finder results in an attractive infinite scrolling grid.
"""

import contextlib
import json
import math
import os
from typing import Optional

from config import (
    DATABASE_PATH,
    IMAGES_DIR,
    MAPILLARY_ACCESS_TOKEN,
    MAPILLARY_DOWNLOAD_IMAGES,
)
from database import BenchDatabase
from flask import Flask, jsonify, render_template, request, send_from_directory
from schemas import (
    BenchListResponse,
    ConfigResponse,
    ImageListResponse,
    ImageResponse,
    PaginationInfo,
    SearchListResponse,
    SearchSummary,
    SegmentationData,
    SourceSearchRequest,
    WebBenchData,
)
from services.mapillary_service import (
    get_mapillary_service,
    initialize_mapillary_service,
)

from models.enums import DataSource, DetectionSource


app = Flask(__name__)

# Configuration
DEFAULT_START_LAT = 52.3613577  # Amsterdam, Netherlands (matches actual data)
DEFAULT_START_LNG = 4.8666322
DEFAULT_MIN_CONFIDENCE = 0.8
PAGE_SIZE = 20


if MAPILLARY_ACCESS_TOKEN:
    try:
        initialize_mapillary_service(DATABASE_PATH, MAPILLARY_ACCESS_TOKEN, IMAGES_DIR)
        print(
            f"✅ Mapillary integration enabled (image downloading: {'ON' if MAPILLARY_DOWNLOAD_IMAGES else 'OFF'})"
        )
    except Exception as e:
        print(f"⚠️ Mapillary integration failed: {e}")
else:
    print("Info: Mapillary integration disabled (no MAPILLARY_ACCESS_TOKEN)")


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
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    # Earth's radius in meters
    r = 6371000
    return c * r


def get_high_confidence_benches_filtered(
    page: int = 0,
    page_size: int = PAGE_SIZE,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    start_lat: float = DEFAULT_START_LAT,
    start_lng: float = DEFAULT_START_LNG,
    source_filter: Optional[str] = None,
    sort_by: str = "distance",
) -> BenchListResponse:
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
                source_condition = " AND b.source = ?"
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
            count_params = [*query_params, min_confidence]
            total_count = conn.execute(count_query, count_params).fetchone()["total"]

            # Determine sorting clause
            if sort_by == "confidence":
                order_clause = "best_confidence DESC, b.id"
            elif sort_by == "images":
                order_clause = "image_count DESC, best_confidence DESC, b.id"
            elif sort_by == "recent":
                order_clause = "b.id DESC"  # Assuming higher IDs are more recent
            else:  # distance (default)
                # For distance sorting, we'll calculate distance in the query
                order_clause = f"((b.lat - {start_lat}) * (b.lat - {start_lat}) + (b.lng - {start_lng}) * (b.lng - {start_lng})) ASC, best_confidence DESC"

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
            query_params_final = [*query_params, min_confidence, page_size, offset]
            rows = conn.execute(query, query_params_final).fetchall()

            # Process results (same logic as original function)
            benches = []
            for row in rows:
                # Parse tags if available
                tags = {}
                if row["tags"]:
                    with contextlib.suppress(json.JSONDecodeError):
                        tags = json.loads(row["tags"])

                # Calculate distance
                distance = calculate_distance(
                    start_lat, start_lng, row["lat"], row["lng"]
                )

                # Get image filenames and IDs
                image_filenames = (
                    row["image_filenames"].split(",") if row["image_filenames"] else []
                )
                image_ids = (
                    [int(x) for x in row["image_ids"].split(",") if x]
                    if row["image_ids"]
                    else []
                )

                # Determine best confidence and detection type
                roboflow_conf = row["roboflow_confidence"] or 0
                ultralytics_conf = row["ultralytics_confidence"] or 0
                mapillary_conf = row["mapillary_confidence"] or 0
                best_confidence = max(roboflow_conf, ultralytics_conf, mapillary_conf)

                # Determine detection type based on source and confidence
                if row["source"] == DataSource.MAPILLARY:
                    detection_type = DetectionSource.MAPILLARY
                elif ultralytics_conf > 0 and ultralytics_conf >= roboflow_conf * 0.95:
                    detection_type = DetectionSource.ULTRALYTICS
                else:
                    detection_type = (
                        DetectionSource.ROBOFLOW
                        if roboflow_conf > ultralytics_conf
                        else DetectionSource.ULTRALYTICS
                    )

                bench_data = WebBenchData(
                    id=row["id"],
                    provider_id=row["provider_id"],
                    lat=row["lat"],
                    lng=row["lng"],
                    tags=tags,
                    source=row["source"] or DataSource.OSM,
                    external_id=row["external_id"],
                    best_confidence=round(best_confidence, 3),
                    roboflow_confidence=round(roboflow_conf, 3),
                    ultralytics_confidence=round(ultralytics_conf, 3),
                    mapillary_confidence=round(mapillary_conf, 3),
                    detection_type=detection_type,
                    has_segmentation=ultralytics_conf > 0 or mapillary_conf > 0,
                    image_count=row["image_count"],
                    image_filenames=image_filenames,
                    image_ids=image_ids,
                    distance_meters=round(distance),
                    distance_km=round(distance / 1000, 2),
                )

                benches.append(bench_data)

            pagination = PaginationInfo(
                page=page,
                page_size=page_size,
                total_count=total_count,
                total_pages=math.ceil(total_count / page_size),
                has_next=(page + 1) * page_size < total_count,
            )

            return BenchListResponse(benches=benches, pagination=pagination)

    except Exception as e:
        print(f"Error getting filtered benches: {e}")
        return BenchListResponse(
            benches=[],
            pagination=PaginationInfo(
                page=0,
                page_size=page_size,
                total_count=0,
                total_pages=0,
                has_next=False,
            ),
        )


def get_high_confidence_benches(
    page: int = 0,
    page_size: int = PAGE_SIZE,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    start_lat: float = DEFAULT_START_LAT,
    start_lng: float = DEFAULT_START_LNG,
) -> BenchListResponse:
    """
    Get benches with high confidence detections, including distance calculations.
    Supports both Roboflow and Ultralytics detection data.
    """
    try:
        db = BenchDatabase()
        with db._get_connection() as conn:
            # First, get benches using the original working query as base
            # Then enhance with Ultralytics data

            # Get total count with confidence filtering
            count_query = """
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
                    WHERE b.id IN (
                        SELECT DISTINCT b2.id
                        FROM benches b2
                        JOIN images i2 ON b2.id = i2.bench_id AND i2.capture_success = 1
                        JOIN detections d2 ON i2.id = d2.image_id
                        WHERE d2.has_bench = 1 AND d2.max_confidence >= ?

                        UNION

                        SELECT DISTINCT b2.id
                        FROM benches b2
                        JOIN images i2 ON b2.id = i2.bench_id AND i2.capture_success = 1
                        JOIN ultralytics_detections ud2 ON i2.id = ud2.image_id
                        WHERE ud2.has_bench = 1 AND ud2.max_confidence >= ?
                    )
                    GROUP BY b.id
                    HAVING best_confidence >= ?
                ) as filtered_benches
            """
            total_count = conn.execute(
                count_query, (min_confidence, min_confidence, min_confidence)
            ).fetchone()["total"]

            # Get detailed bench data
            query = """
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
                WHERE b.id IN (
                    SELECT DISTINCT b2.id
                    FROM benches b2
                    JOIN images i2 ON b2.id = i2.bench_id AND i2.capture_success = 1
                    JOIN detections d2 ON i2.id = d2.image_id
                    WHERE d2.has_bench = 1 AND d2.max_confidence >= ?

                    UNION

                    SELECT DISTINCT b2.id
                    FROM benches b2
                    JOIN images i2 ON b2.id = i2.bench_id AND i2.capture_success = 1
                    JOIN ultralytics_detections ud2 ON i2.id = ud2.image_id
                    WHERE ud2.has_bench = 1 AND ud2.max_confidence >= ?
                )
                GROUP BY b.id
                HAVING best_confidence >= ?
                ORDER BY best_confidence DESC, b.id
                LIMIT ? OFFSET ?
            """

            offset = page * page_size
            rows = conn.execute(
                query,
                (min_confidence, min_confidence, min_confidence, page_size, offset),
            ).fetchall()

            benches = []
            for row in rows:
                # Parse tags if available
                tags = {}
                if row["tags"]:
                    with contextlib.suppress(json.JSONDecodeError):
                        tags = json.loads(row["tags"])

                # Calculate distance
                distance = calculate_distance(
                    start_lat, start_lng, row["lat"], row["lng"]
                )

                # Get image filenames and IDs
                image_filenames = (
                    row["image_filenames"].split(",") if row["image_filenames"] else []
                )
                image_ids = (
                    [int(x) for x in row["image_ids"].split(",") if x]
                    if row["image_ids"]
                    else []
                )

                # Determine best confidence and detection type
                roboflow_conf = row["roboflow_confidence"] or 0
                ultralytics_conf = row["ultralytics_confidence"] or 0
                mapillary_conf = row["mapillary_confidence"] or 0
                best_confidence = max(roboflow_conf, ultralytics_conf, mapillary_conf)

                # Determine detection type based on source and confidence
                if row["source"] == DataSource.MAPILLARY:
                    detection_type = DetectionSource.MAPILLARY
                elif ultralytics_conf > 0 and ultralytics_conf >= roboflow_conf * 0.95:
                    detection_type = DetectionSource.ULTRALYTICS
                else:
                    detection_type = (
                        DetectionSource.ROBOFLOW
                        if roboflow_conf > ultralytics_conf
                        else DetectionSource.ULTRALYTICS
                    )

                bench_data = WebBenchData(
                    id=row["id"],
                    provider_id=row["provider_id"],
                    lat=row["lat"],
                    lng=row["lng"],
                    tags=tags,
                    source=row["source"] or DataSource.OSM,
                    external_id=row["external_id"],
                    best_confidence=round(best_confidence, 3),
                    roboflow_confidence=round(roboflow_conf, 3),
                    ultralytics_confidence=round(ultralytics_conf, 3),
                    mapillary_confidence=round(mapillary_conf, 3),
                    detection_type=detection_type,
                    has_segmentation=ultralytics_conf > 0 or mapillary_conf > 0,
                    image_count=row["image_count"],
                    image_filenames=image_filenames,
                    image_ids=image_ids,
                    distance_meters=round(distance),
                    distance_km=round(distance / 1000, 2),
                )

                benches.append(bench_data)

            pagination = PaginationInfo(
                page=page,
                page_size=page_size,
                total_count=total_count,
                total_pages=math.ceil(total_count / page_size),
                has_next=(page + 1) * page_size < total_count,
            )

            return BenchListResponse(benches=benches, pagination=pagination)

    except Exception as e:
        print(f"Error getting high confidence benches: {e}")
        return BenchListResponse(
            benches=[],
            pagination=PaginationInfo(
                page=0,
                page_size=page_size,
                total_count=0,
                total_pages=0,
                has_next=False,
            ),
        )


@app.route("/")
def index():
    """Serve the main page with the bench grid."""
    return render_template("index.html")


@app.route("/api/benches")
def api_benches():
    """API endpoint to get bench data with pagination."""
    page = request.args.get("page", 0, type=int)
    page_size = request.args.get("page_size", PAGE_SIZE, type=int)
    min_confidence = request.args.get(
        "min_confidence", DEFAULT_MIN_CONFIDENCE, type=float
    )
    start_lat = request.args.get("start_lat", DEFAULT_START_LAT, type=float)
    start_lng = request.args.get("start_lng", DEFAULT_START_LNG, type=float)
    sort_by = request.args.get("sort_by", "distance")

    # Limit page size to prevent abuse
    page_size = min(page_size, 50)

    result = get_high_confidence_benches_filtered(
        page, page_size, min_confidence, start_lat, start_lng, None, sort_by
    )
    return jsonify(result.model_dump())


@app.route("/api/searches")
def api_searches():
    """API endpoint to get available search starting points."""
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
                    id=row["id"],
                    query=row["query"],
                    start_lat=row["start_lat"],
                    start_lng=row["start_lng"],
                    search_radius=row["search_radius"],
                    bench_count=row["bench_count"],
                    created_at=row["created_at"],
                )
                searches.append(search)

            result = SearchListResponse(searches=searches)
            return jsonify(result.model_dump())

    except Exception as e:
        print(f"Error getting searches: {e}")
        return jsonify(SearchListResponse(searches=[]).model_dump())


@app.route("/images/<path:filename>")
def serve_image(filename):
    """Serve bench images."""
    images_path = os.path.join(os.path.dirname(__file__), IMAGES_DIR)
    return send_from_directory(images_path, filename)


@app.route("/api/image/<int:image_id>/segmentation")
def api_image_segmentation(image_id: int):
    """Get detection visualization data for a specific image (both segmentation and bounding boxes)."""
    try:
        db = BenchDatabase()
        with db._get_connection() as conn:
            # Get image filename first
            image_query = "SELECT filename FROM images WHERE id = ?"
            image_row = conn.execute(image_query, (image_id,)).fetchone()

            if not image_row:
                return jsonify({"error": "Image not found"}), 404

            filename = image_row["filename"]

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
                bench_detections = (
                    json.loads(ultralytics_row["bench_detections"])
                    if ultralytics_row["bench_detections"]
                    else []
                )
                full_response = (
                    json.loads(ultralytics_row["full_response"])
                    if ultralytics_row["full_response"]
                    else {}
                )

                # Extract image dimensions from full response if available
                if "images" in full_response and len(full_response["images"]) > 0:
                    image_shape = full_response["images"][0].get("shape", None)

                max_confidence = max(
                    max_confidence, ultralytics_row["max_confidence"] or 0.0
                )
                detection_sources.append(DetectionSource.ULTRALYTICS)

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
                roboflow_detections = (
                    json.loads(roboflow_row["detections"])
                    if roboflow_row["detections"]
                    else []
                )
                max_confidence = max(
                    max_confidence, roboflow_row["max_confidence"] or 0.0
                )
                detection_sources.append(DetectionSource.ROBOFLOW)

            # Check if we have any detection data
            if not bench_detections and not roboflow_detections:
                return jsonify({"error": "No detection data found for this image"}), 404

            # Determine detection type
            if bench_detections and roboflow_detections:
                detection_type = "both"
                source = "both"
            elif bench_detections:
                detection_type = "segmentation"
                source = DetectionSource.ULTRALYTICS
            else:
                detection_type = "bounding_box"
                source = DetectionSource.ROBOFLOW

            result = SegmentationData(
                filename=filename,
                detection_type=detection_type,
                bench_detections=bench_detections,
                image_shape=image_shape,
                segmentation_available=len(bench_detections) > 0,
                roboflow_detections=roboflow_detections,
                bounding_box_available=len(roboflow_detections) > 0,
                confidence_score=max_confidence,
                source=source,
            )
            return jsonify(result.model_dump())

    except Exception as e:
        print(f"Error getting detection data: {e}")
        return jsonify({"error": "Failed to retrieve detection data"}), 500


@app.route("/api/bench/<int:bench_id>/images")
def api_bench_images(bench_id: int):
    """Get all images for a bench with heading information."""
    try:
        db = BenchDatabase()
        with db._get_connection() as conn:
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
                    id=row["id"],
                    bench_id=row["bench_id"],
                    heading=row["heading"],
                    filepath=row["filepath"],
                    filename=row["filename"],
                    file_size=row["file_size"],
                    capture_success=bool(row["capture_success"]),
                    capture_error=row["capture_error"],
                    created_at=row["created_at"],
                )
                images.append(image)

            result = ImageListResponse(images=images)
            return jsonify(result.model_dump())

    except Exception as e:
        print(f"Error getting bench images: {e}")
        return jsonify({"error": "Failed to retrieve bench images"}), 500


@app.route("/api/config")
def api_config():
    """Get application configuration for the frontend."""
    config = ConfigResponse(
        default_start_lat=DEFAULT_START_LAT,
        default_start_lng=DEFAULT_START_LNG,
        default_min_confidence=DEFAULT_MIN_CONFIDENCE,
        page_size=PAGE_SIZE,
    )
    return jsonify(config.model_dump())


@app.route("/api/mapillary/search", methods=["POST"])
def api_mapillary_search():
    """Search for bench detections using Mapillary API and store in database."""
    if not get_mapillary_service():
        return jsonify({"error": "Mapillary integration not available"}), 503

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "JSON body required"}), 400

        # Validate required fields
        if "center_lat" not in data or "center_lng" not in data:
            return jsonify({"error": "center_lat and center_lng are required"}), 400

        search_request = SourceSearchRequest(
            center_lat=data["center_lat"],
            center_lng=data["center_lng"],
            radius_meters=data.get("radius_meters", 1000),
            limit=data.get("limit", 1000),
            source=DataSource.MAPILLARY,
        )

        # Search and store bench detections
        result = get_mapillary_service().search_and_store_benches(
            center_lat=search_request.center_lat,
            center_lng=search_request.center_lng,
            radius_meters=search_request.radius_meters,
            limit=search_request.limit,
        )

        return jsonify(result.model_dump())

    except Exception as e:
        return jsonify({"error": f"Search failed: {e!s}"}), 500


@app.route("/api/benches/source/<source>")
def api_benches_by_source(source: str):
    """Get benches filtered by source (osm or mapillary)."""
    try:
        page = request.args.get("page", 0, type=int)
        page_size = request.args.get("page_size", PAGE_SIZE, type=int)
        min_confidence = request.args.get(
            "min_confidence", DEFAULT_MIN_CONFIDENCE, type=float
        )
        start_lat = request.args.get("start_lat", DEFAULT_START_LAT, type=float)
        start_lng = request.args.get("start_lng", DEFAULT_START_LNG, type=float)
        sort_by = request.args.get("sort_by", "distance")

        # Limit page size to prevent abuse
        page_size = min(page_size, 50)

        # For Mapillary, use the service if available
        if source == DataSource.MAPILLARY and get_mapillary_service():
            benches = get_mapillary_service().get_stored_benches(
                center_lat=start_lat,
                center_lng=start_lng,
                radius_meters=2000,  # Larger radius for stored data
                limit=page_size,
                source=DataSource.MAPILLARY,
            )

            pagination = PaginationInfo(
                page=page,
                page_size=len(benches),
                total_count=len(benches),
                total_pages=1,
                has_next=False,
            )

            result = BenchListResponse(benches=benches, pagination=pagination)
            return jsonify(result.model_dump())

        # For OSM, modify the query to filter by source
        result = get_high_confidence_benches_filtered(
            page, page_size, min_confidence, start_lat, start_lng, source, sort_by
        )
        return jsonify(result.model_dump())

    except Exception as e:
        return jsonify({"error": f"Failed to get benches: {e!s}"}), 500


@app.route("/api/benches/random")
def api_random_bench():
    """Get a random high-confidence bench respecting current filters."""
    try:
        min_confidence = request.args.get(
            "min_confidence", DEFAULT_MIN_CONFIDENCE, type=float
        )
        source_filter = request.args.get("source")

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

            if source_filter:
                source_condition = " AND b.source = ?"
                query_params.append(source_filter)

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
                return jsonify({"error": "No benches found matching criteria"}), 404

            bench_id = row["id"]

            # Get detailed bench data for this random bench
            result = get_high_confidence_benches_filtered(
                page=0,
                page_size=1,
                min_confidence=min_confidence,
                start_lat=DEFAULT_START_LAT,
                start_lng=DEFAULT_START_LNG,
                source_filter=source_filter,
            )

            # Filter the results to just this bench
            random_bench = None
            for bench in result.benches:
                if bench.id == bench_id:
                    random_bench = bench
                    break

            if not random_bench:
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
                    if bench_row["tags"]:
                        with contextlib.suppress(json.JSONDecodeError):
                            tags = json.loads(bench_row["tags"])

                    image_filenames = (
                        bench_row["image_filenames"].split(",")
                        if bench_row["image_filenames"]
                        else []
                    )
                    image_ids = (
                        [int(x) for x in bench_row["image_ids"].split(",") if x]
                        if bench_row["image_ids"]
                        else []
                    )

                    random_bench = WebBenchData(
                        id=bench_row["id"],
                        provider_id=bench_row["provider_id"],
                        lat=bench_row["lat"],
                        lng=bench_row["lng"],
                        tags=tags,
                        source=bench_row["source"] or DataSource.OSM,
                        external_id=bench_row["external_id"],
                        best_confidence=min_confidence,  # Approximate
                        roboflow_confidence=0,
                        ultralytics_confidence=0,
                        mapillary_confidence=0,
                        detection_type="unknown",
                        has_segmentation=False,
                        image_count=bench_row["image_count"],
                        image_filenames=image_filenames,
                        image_ids=image_ids,
                        distance_meters=0,
                        distance_km=0,
                    )

            if not random_bench:
                return jsonify({"error": "Failed to get random bench details"}), 500

            return jsonify({"bench": random_bench.model_dump()})

    except Exception as e:
        print(f"Error getting random bench: {e}")
        return jsonify({"error": "Failed to get random bench"}), 500


@app.route("/api/benches/bbox")
def api_benches_in_bbox():
    """Get benches within a bounding box for map view."""
    try:
        # Bounding box parameters
        north = request.args.get("north", type=float)
        south = request.args.get("south", type=float)
        east = request.args.get("east", type=float)
        west = request.args.get("west", type=float)

        # Filter parameters
        min_confidence = request.args.get(
            "min_confidence", DEFAULT_MIN_CONFIDENCE, type=float
        )
        source_filter = request.args.get("source")
        sort_by = request.args.get("sort_by", "distance")
        limit = request.args.get(
            "limit", 200, type=int
        )  # Reasonable limit for map display

        if None in [north, south, east, west]:
            return jsonify(
                {"error": "All bbox parameters (north, south, east, west) are required"}
            ), 400

        # Limit to prevent abuse
        limit = min(limit, 500)

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
            query_params = [
                min_confidence,
                south,
                north,
                west,
                east,
                min_confidence,
                south,
                north,
                west,
                east,
            ]

            if source_filter:
                source_condition = " AND b.source = ?"
                query_params.append(source_filter)

            # Determine sorting clause for bbox
            center_lat = (north + south) / 2
            center_lng = (east + west) / 2

            if sort_by == "confidence":
                bbox_order_clause = "best_confidence DESC, b.id"
            elif sort_by == "images":
                bbox_order_clause = "image_count DESC, best_confidence DESC, b.id"
            elif sort_by == "recent":
                bbox_order_clause = "b.id DESC"  # Assuming higher IDs are more recent
            else:  # distance (default)
                # For distance sorting, we'll calculate distance from bbox center
                bbox_order_clause = f"((b.lat - {center_lat}) * (b.lat - {center_lat}) + (b.lng - {center_lng}) * (b.lng - {center_lng})) ASC, best_confidence DESC"

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

            final_params = [*query_params, min_confidence, limit]
            rows = conn.execute(query, final_params).fetchall()

            # Process results similar to get_high_confidence_benches_filtered
            benches = []

            for row in rows:
                # Parse tags if available
                tags = {}
                if row["tags"]:
                    with contextlib.suppress(json.JSONDecodeError):
                        tags = json.loads(row["tags"])

                # Calculate distance from center
                distance = calculate_distance(
                    center_lat, center_lng, row["lat"], row["lng"]
                )

                # Get image filenames and IDs
                image_filenames = (
                    row["image_filenames"].split(",") if row["image_filenames"] else []
                )
                image_ids = (
                    [int(x) for x in row["image_ids"].split(",") if x]
                    if row["image_ids"]
                    else []
                )

                # Determine best confidence and detection type
                roboflow_conf = row["roboflow_confidence"] or 0
                ultralytics_conf = row["ultralytics_confidence"] or 0
                mapillary_conf = row["mapillary_confidence"] or 0
                best_confidence = max(roboflow_conf, ultralytics_conf, mapillary_conf)

                # Determine detection type based on source and confidence
                if row["source"] == DataSource.MAPILLARY:
                    detection_type = DetectionSource.MAPILLARY
                elif ultralytics_conf > 0 and ultralytics_conf >= roboflow_conf * 0.95:
                    detection_type = DetectionSource.ULTRALYTICS
                else:
                    detection_type = (
                        DetectionSource.ROBOFLOW
                        if roboflow_conf > ultralytics_conf
                        else DetectionSource.ULTRALYTICS
                    )

                bench_data = WebBenchData(
                    id=row["id"],
                    provider_id=row["provider_id"],
                    lat=row["lat"],
                    lng=row["lng"],
                    tags=tags,
                    source=row["source"] or DataSource.OSM,
                    external_id=row["external_id"],
                    best_confidence=round(best_confidence, 3),
                    roboflow_confidence=round(roboflow_conf, 3),
                    ultralytics_confidence=round(ultralytics_conf, 3),
                    mapillary_confidence=round(mapillary_conf, 3),
                    detection_type=detection_type,
                    has_segmentation=ultralytics_conf > 0 or mapillary_conf > 0,
                    image_count=row["image_count"],
                    image_filenames=image_filenames,
                    image_ids=image_ids,
                    distance_meters=round(distance),
                    distance_km=round(distance / 1000, 2),
                )

                benches.append(bench_data)

            return jsonify(
                {
                    "benches": [bench.model_dump() for bench in benches],
                    "total_count": len(benches),
                    "bbox": {
                        "north": north,
                        "south": south,
                        "east": east,
                        "west": west,
                    },
                }
            )

    except Exception as e:
        print(f"Error getting benches in bbox: {e}")
        return jsonify({"error": "Failed to get benches in bounding box"}), 500


@app.route("/api/statistics/source/<source>")
def api_statistics_by_source(source: str):
    """Get statistics filtered by source."""
    try:
        center_lat = request.args.get("center_lat", type=float)
        center_lng = request.args.get("center_lng", type=float)
        radius_meters = request.args.get("radius_meters", type=int)

        if source == DataSource.MAPILLARY and get_mapillary_service():
            stats = get_mapillary_service().get_detection_statistics(
                center_lat=center_lat,
                center_lng=center_lng,
                radius_meters=radius_meters,
                source=DataSource.MAPILLARY,
            )
            return jsonify(stats.model_dump())

        # For OSM, we'd need to implement similar logic
        # For now, return a basic response
        return jsonify(
            {
                "source": source,
                "total_benches": 0,
                "total_detections": 0,
                "avg_detections_per_bench": 0,
                "unique_locations": 0,
                "coverage_area_km2": 0,
            }
        )

    except Exception as e:
        return jsonify({"error": f"Failed to get statistics: {e!s}"}), 500


if __name__ == "__main__":
    # Ensure templates and static directories exist
    os.makedirs("templates", exist_ok=True)
    os.makedirs("static", exist_ok=True)

    print("Starting bench finder web server...")
    print(f"Database: {DATABASE_PATH}")
    print(f"Images directory: {IMAGES_DIR}")
    print("Server will be available at: http://localhost:8866")

    app.run(debug=True, host="0.0.0.0", port=8866)
