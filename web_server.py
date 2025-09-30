#!/usr/bin/env python3
"""
Web server for displaying bench finder results in an attractive infinite scrolling grid.
"""
import os
import math
import json
import sqlite3
from flask import Flask, render_template, jsonify, request, send_from_directory
from typing import List, Dict, Optional, Tuple
from database import BenchDatabase
from config import DATABASE_PATH, IMAGES_DIR

app = Flask(__name__)

# Configuration
DEFAULT_START_LAT = 52.3613577  # Amsterdam, Netherlands (matches actual data)
DEFAULT_START_LNG = 4.8666322
DEFAULT_MIN_CONFIDENCE = 0.8
PAGE_SIZE = 20


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


def get_high_confidence_benches(page: int = 0, page_size: int = PAGE_SIZE, 
                              min_confidence: float = DEFAULT_MIN_CONFIDENCE,
                              start_lat: float = DEFAULT_START_LAT, 
                              start_lng: float = DEFAULT_START_LNG) -> Dict:
    """
    Get benches with high confidence detections, including distance calculations.
    Supports both Roboflow and Ultralytics detection data.
    """
    try:
        db = BenchDatabase()
        with db._get_connection() as conn:
            # First, get benches using the original working query as base
            # Then enhance with Ultralytics data
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
            
            # Get total count
            count_query = f"SELECT COUNT(*) as total FROM ({base_query}) as combined"
            total_count = conn.execute(count_query, (min_confidence, min_confidence)).fetchone()['total']
            
            # Get detailed bench data
            query = """
                SELECT 
                    b.id, b.osm_id, b.osm_type, b.lat, b.lng, b.tags,
                    COALESCE(rf_data.max_confidence, 0) as roboflow_confidence,
                    COALESCE(ul_data.max_confidence, 0) as ultralytics_confidence,
                    COUNT(DISTINCT i.id) as image_count,
                    GROUP_CONCAT(DISTINCT i.filename) as image_filenames,
                    GROUP_CONCAT(DISTINCT i.id) as image_ids
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
                ORDER BY CASE 
                    WHEN COALESCE(rf_data.max_confidence, 0) >= COALESCE(ul_data.max_confidence, 0) 
                    THEN COALESCE(rf_data.max_confidence, 0)
                    ELSE COALESCE(ul_data.max_confidence, 0)
                END DESC, b.id
                LIMIT ? OFFSET ?
            """
            
            offset = page * page_size
            rows = conn.execute(query, (min_confidence, min_confidence, page_size, offset)).fetchall()
            
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
                best_confidence = max(roboflow_conf, ultralytics_conf)
                
                # Prefer Ultralytics when confidence is close (within 5%) or better
                if ultralytics_conf > 0 and ultralytics_conf >= roboflow_conf * 0.95:
                    detection_type = 'ultralytics'
                else:
                    detection_type = 'roboflow' if roboflow_conf > ultralytics_conf else 'ultralytics'
                
                bench_data = {
                    'id': row['id'],
                    'osm_id': row['osm_id'],
                    'osm_type': row['osm_type'],
                    'lat': row['lat'],
                    'lng': row['lng'],
                    'tags': tags,
                    'best_confidence': round(best_confidence, 3),
                    'roboflow_confidence': round(roboflow_conf, 3),
                    'ultralytics_confidence': round(ultralytics_conf, 3),
                    'detection_type': detection_type,
                    'has_segmentation': ultralytics_conf > 0,
                    'image_count': row['image_count'],
                    'image_filenames': image_filenames,
                    'image_ids': image_ids,
                    'distance_meters': round(distance),
                    'distance_km': round(distance / 1000, 2)
                }
                
                benches.append(bench_data)
            
            return {
                'benches': benches,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': total_count,
                    'total_pages': math.ceil(total_count / page_size),
                    'has_next': (page + 1) * page_size < total_count
                }
            }
            
    except Exception as e:
        print(f"Error getting high confidence benches: {e}")
        return {'benches': [], 'pagination': {'page': 0, 'total_count': 0, 'has_next': False}}


@app.route('/')
def index():
    """Serve the main page with the bench grid."""
    return render_template('index.html')


@app.route('/api/benches')
def api_benches():
    """API endpoint to get bench data with pagination."""
    page = request.args.get('page', 0, type=int)
    page_size = request.args.get('page_size', PAGE_SIZE, type=int)
    min_confidence = request.args.get('min_confidence', DEFAULT_MIN_CONFIDENCE, type=float)
    start_lat = request.args.get('start_lat', DEFAULT_START_LAT, type=float)
    start_lng = request.args.get('start_lng', DEFAULT_START_LNG, type=float)
    
    # Limit page size to prevent abuse
    page_size = min(page_size, 50)
    
    data = get_high_confidence_benches(page, page_size, min_confidence, start_lat, start_lng)
    return jsonify(data)


@app.route('/api/searches')
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
                searches.append({
                    'id': row['id'],
                    'query': row['query'],
                    'start_lat': row['start_lat'],
                    'start_lng': row['start_lng'],
                    'search_radius': row['search_radius'],
                    'bench_count': row['bench_count'],
                    'created_at': row['created_at']
                })
            
            return jsonify({'searches': searches})
            
    except Exception as e:
        print(f"Error getting searches: {e}")
        return jsonify({'searches': []})


@app.route('/images/<path:filename>')
def serve_image(filename):
    """Serve bench images."""
    images_path = os.path.join(os.path.dirname(__file__), IMAGES_DIR)
    return send_from_directory(images_path, filename)


@app.route('/api/image/<int:image_id>/segmentation')
def api_image_segmentation(image_id: int):
    """Get segmentation data for a specific image."""
    try:
        db = BenchDatabase()
        with db._get_connection() as conn:
            # Get Ultralytics detection data for this image
            query = """
                SELECT ud.bench_detections, ud.full_response, i.filename
                FROM ultralytics_detections ud
                JOIN images i ON ud.image_id = i.id
                WHERE ud.image_id = ? AND ud.has_bench = 1
                ORDER BY ud.max_confidence DESC
                LIMIT 1
            """
            
            row = conn.execute(query, (image_id,)).fetchone()
            
            if not row:
                return jsonify({'error': 'No segmentation data found for this image'}), 404
            
            # Parse JSON data
            bench_detections = json.loads(row['bench_detections']) if row['bench_detections'] else []
            full_response = json.loads(row['full_response']) if row['full_response'] else {}
            
            # Extract image dimensions from full response if available
            image_shape = None
            if 'images' in full_response and len(full_response['images']) > 0:
                image_shape = full_response['images'][0].get('shape', None)
            
            return jsonify({
                'filename': row['filename'],
                'bench_detections': bench_detections,
                'image_shape': image_shape,
                'segmentation_available': len(bench_detections) > 0
            })
            
    except Exception as e:
        print(f"Error getting segmentation data: {e}")
        return jsonify({'error': 'Failed to retrieve segmentation data'}), 500


@app.route('/api/bench/<int:bench_id>/images')
def api_bench_images(bench_id: int):
    """Get all images for a bench with heading information."""
    try:
        db = BenchDatabase()
        with db._get_connection() as conn:
            query = """
                SELECT i.id, i.heading, i.filename, i.filepath
                FROM images i
                WHERE i.bench_id = ? AND i.capture_success = 1
                ORDER BY i.heading
            """
            
            rows = conn.execute(query, (bench_id,)).fetchall()
            
            images = []
            for row in rows:
                images.append({
                    'id': row['id'],
                    'heading': row['heading'],
                    'filename': row['filename'],
                    'filepath': row['filepath']
                })
            
            return jsonify({'images': images})
            
    except Exception as e:
        print(f"Error getting bench images: {e}")
        return jsonify({'error': 'Failed to retrieve bench images'}), 500


@app.route('/api/config')
def api_config():
    """Get application configuration for the frontend."""
    return jsonify({
        'default_start_lat': DEFAULT_START_LAT,
        'default_start_lng': DEFAULT_START_LNG,
        'default_min_confidence': DEFAULT_MIN_CONFIDENCE,
        'page_size': PAGE_SIZE
    })


if __name__ == '__main__':
    # Ensure templates and static directories exist
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    print(f"Starting bench finder web server...")
    print(f"Database: {DATABASE_PATH}")
    print(f"Images directory: {IMAGES_DIR}")
    print(f"Server will be available at: http://localhost:8866")
    
    app.run(debug=True, host='0.0.0.0', port=8866)
