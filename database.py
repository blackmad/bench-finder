"""
SQLite database operations for storing bench data, images, and detection results.
"""
import sqlite3
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


class BenchDatabase:
    """SQLite database manager for bench finder application."""
    
    def __init__(self, db_path: str = None):
        """
        Initialize database connection and create tables if needed.
        
        Args:
            db_path: Path to SQLite database file (defaults to config DATABASE_PATH)
        """
        self.db_path = db_path or DATABASE_PATH
        
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize database
        self._create_tables()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Allow dict-like access to rows
        return conn
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        try:
            with self._get_connection() as conn:
                # Searches table - stores the original search queries
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS searches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        query TEXT NOT NULL,
                        start_lat REAL NOT NULL,
                        start_lng REAL NOT NULL,
                        search_radius INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        status TEXT DEFAULT 'pending'
                    )
                ''')
                
                # Benches table - stores OSM bench data
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS benches (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        search_id INTEGER NOT NULL,
                        osm_id INTEGER NOT NULL,
                        osm_type TEXT NOT NULL,
                        lat REAL NOT NULL,
                        lng REAL NOT NULL,
                        tags TEXT,  -- JSON string of OSM tags
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (search_id) REFERENCES searches (id),
                        UNIQUE (search_id, osm_id, osm_type)
                    )
                ''')
                
                # Images table - stores street view image metadata
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS images (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        bench_id INTEGER NOT NULL,
                        heading INTEGER NOT NULL,
                        filepath TEXT,
                        filename TEXT,
                        file_size INTEGER,
                        capture_success BOOLEAN NOT NULL,
                        capture_error TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (bench_id) REFERENCES benches (id)
                    )
                ''')
                
                # Detections table - stores Roboflow detection results
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS detections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        image_id INTEGER NOT NULL,
                        has_bench BOOLEAN NOT NULL,
                        bench_count INTEGER DEFAULT 0,
                        max_confidence REAL DEFAULT 0.0,
                        detections TEXT,  -- JSON string of detection details
                        detection_success BOOLEAN NOT NULL,
                        detection_error TEXT,
                        model_id TEXT NOT NULL,
                        confidence_threshold REAL NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (image_id) REFERENCES images (id)
                    )
                ''')
                
                # Ultralytics detections table - stores full segmentation results
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS ultralytics_detections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        image_id INTEGER NOT NULL,
                        has_bench BOOLEAN NOT NULL,
                        bench_count INTEGER DEFAULT 0,
                        max_confidence REAL DEFAULT 0.0,
                        full_response TEXT,  -- JSON string of complete Ultralytics API response
                        bench_detections TEXT,  -- JSON string of bench-specific detections with segmentation
                        detection_success BOOLEAN NOT NULL,
                        detection_error TEXT,
                        model_url TEXT NOT NULL,
                        confidence_threshold REAL NOT NULL,
                        iou_threshold REAL NOT NULL,
                        image_size INTEGER NOT NULL,
                        inference_time REAL,
                        preprocess_time REAL,
                        postprocess_time REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (image_id) REFERENCES images (id)
                    )
                ''')
                
                # Create indexes for better performance
                conn.execute('CREATE INDEX IF NOT EXISTS idx_benches_search_id ON benches (search_id)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_benches_osm ON benches (osm_id, osm_type)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_images_bench_id ON images (bench_id)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_detections_image_id ON detections (image_id)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_detections_has_bench ON detections (has_bench)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_ultralytics_detections_image_id ON ultralytics_detections (image_id)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_ultralytics_detections_has_bench ON ultralytics_detections (has_bench)')
                
                logger.info(f"Database initialized at {self.db_path}")
                
        except sqlite3.Error as e:
            logger.error(f"Error creating database tables: {e}")
            raise
    
    def create_search(self, query: str, start_lat: float, start_lng: float, 
                     search_radius: int) -> int:
        """
        Create a new search record.
        
        Args:
            query: Original search query string
            start_lat: Starting latitude coordinate
            start_lng: Starting longitude coordinate
            search_radius: Search radius in meters
            
        Returns:
            The ID of the created search record
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    '''INSERT INTO searches (query, start_lat, start_lng, search_radius)
                       VALUES (?, ?, ?, ?)''',
                    (query, start_lat, start_lng, search_radius)
                )
                search_id = cursor.lastrowid
                logger.info(f"Created search record {search_id} for query: {query}")
                return search_id
                
        except sqlite3.Error as e:
            logger.error(f"Error creating search record: {e}")
            raise
    
    def add_bench(self, search_id: int, bench_data: Dict) -> int:
        """
        Add a bench record to the database.
        
        Args:
            search_id: ID of the associated search
            bench_data: Dictionary with bench data from OSM
            
        Returns:
            The ID of the created bench record
        """
        try:
            with self._get_connection() as conn:
                tags_json = json.dumps(bench_data.get('tags', {}))
                
                cursor = conn.execute(
                    '''INSERT OR IGNORE INTO benches 
                       (search_id, osm_id, osm_type, lat, lng, tags)
                       VALUES (?, ?, ?, ?, ?, ?)''',
                    (search_id, bench_data['osm_id'], bench_data['osm_type'],
                     bench_data['lat'], bench_data['lng'], tags_json)
                )
                
                bench_id = cursor.lastrowid
                if bench_id:
                    logger.debug(f"Added bench {bench_data['osm_id']} as record {bench_id}")
                else:
                    # Bench already exists, get its ID
                    cursor = conn.execute(
                        '''SELECT id FROM benches 
                           WHERE search_id = ? AND osm_id = ? AND osm_type = ?''',
                        (search_id, bench_data['osm_id'], bench_data['osm_type'])
                    )
                    row = cursor.fetchone()
                    bench_id = row[0] if row else None
                    logger.debug(f"Bench {bench_data['osm_id']} already exists as record {bench_id}")
                
                return bench_id
                
        except sqlite3.Error as e:
            logger.error(f"Error adding bench record: {e}")
            raise
    
    def add_image(self, bench_id: int, image_data: Dict) -> int:
        """
        Add an image record to the database.
        
        Args:
            bench_id: ID of the associated bench
            image_data: Dictionary with image capture results
            
        Returns:
            The ID of the created image record
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    '''INSERT INTO images 
                       (bench_id, heading, filepath, filename, file_size, 
                        capture_success, capture_error)
                       VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (bench_id, image_data['heading'], image_data.get('filepath'),
                     image_data.get('filename'), image_data.get('file_size'),
                     image_data['success'], image_data.get('error'))
                )
                
                image_id = cursor.lastrowid
                logger.debug(f"Added image record {image_id} for bench {bench_id}, heading {image_data['heading']}")
                return image_id
                
        except sqlite3.Error as e:
            logger.error(f"Error adding image record: {e}")
            raise
    
    def add_detection(self, image_id: int, detection_data: Dict) -> int:
        """
        Add a detection record to the database.
        
        Args:
            image_id: ID of the associated image
            detection_data: Dictionary with detection results
            
        Returns:
            The ID of the created detection record
        """
        try:
            with self._get_connection() as conn:
                detections_json = json.dumps(detection_data.get('detections', []))
                
                cursor = conn.execute(
                    '''INSERT INTO detections 
                       (image_id, has_bench, bench_count, max_confidence, detections,
                        detection_success, detection_error, model_id, confidence_threshold)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (image_id, detection_data['has_bench'], detection_data['bench_count'],
                     detection_data['max_confidence'], detections_json,
                     detection_data['success'], detection_data.get('error'),
                     detection_data['model_id'], detection_data['confidence_threshold'])
                )
                
                detection_id = cursor.lastrowid
                logger.debug(f"Added detection record {detection_id} for image {image_id}")
                return detection_id
                
        except sqlite3.Error as e:
            logger.error(f"Error adding detection record: {e}")
            raise
    
    def add_ultralytics_detection(self, image_id: int, detection_data: Dict) -> int:
        """
        Add an Ultralytics detection record to the database.
        
        Args:
            image_id: ID of the associated image
            detection_data: Dictionary with Ultralytics detection results
            
        Returns:
            The ID of the created detection record
        """
        try:
            with self._get_connection() as conn:
                full_response_json = json.dumps(detection_data.get('full_response', {}))
                bench_detections_json = json.dumps(detection_data.get('bench_detections', []))
                
                cursor = conn.execute(
                    '''INSERT INTO ultralytics_detections 
                       (image_id, has_bench, bench_count, max_confidence, full_response, 
                        bench_detections, detection_success, detection_error, model_url,
                        confidence_threshold, iou_threshold, image_size, inference_time,
                        preprocess_time, postprocess_time)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (image_id, detection_data['has_bench'], detection_data['bench_count'],
                     detection_data['max_confidence'], full_response_json,
                     bench_detections_json, detection_data['success'], detection_data.get('error'),
                     detection_data['model_url'], detection_data['confidence_threshold'],
                     detection_data['iou_threshold'], detection_data['image_size'],
                     detection_data.get('inference_time'), detection_data.get('preprocess_time'),
                     detection_data.get('postprocess_time'))
                )
                
                detection_id = cursor.lastrowid
                logger.debug(f"Added Ultralytics detection record {detection_id} for image {image_id}")
                return detection_id
                
        except sqlite3.Error as e:
            logger.error(f"Error adding Ultralytics detection record: {e}")
            raise
    
    def update_search_status(self, search_id: int, status: str, completed_at: datetime = None):
        """
        Update the status of a search record.
        
        Args:
            search_id: ID of the search record
            status: New status ('pending', 'completed', 'failed')
            completed_at: Completion timestamp (defaults to current time)
        """
        try:
            if completed_at is None:
                completed_at = datetime.now()
                
            with self._get_connection() as conn:
                conn.execute(
                    '''UPDATE searches SET status = ?, completed_at = ? WHERE id = ?''',
                    (status, completed_at, search_id)
                )
                logger.debug(f"Updated search {search_id} status to {status}")
                
        except sqlite3.Error as e:
            logger.error(f"Error updating search status: {e}")
            raise
    
    def get_search_results(self, search_id: int) -> Dict:
        """
        Get comprehensive results for a search.
        
        Args:
            search_id: ID of the search
            
        Returns:
            Dictionary with search results and statistics
        """
        try:
            with self._get_connection() as conn:
                # Get search info
                search_row = conn.execute(
                    'SELECT * FROM searches WHERE id = ?', (search_id,)
                ).fetchone()
                
                if not search_row:
                    return {}
                
                # Get bench count
                bench_count = conn.execute(
                    'SELECT COUNT(*) FROM benches WHERE search_id = ?', (search_id,)
                ).fetchone()[0]
                
                # Get image stats
                image_stats = conn.execute('''
                    SELECT COUNT(*) as total_images, 
                           SUM(capture_success) as successful_images
                    FROM images i 
                    JOIN benches b ON i.bench_id = b.id
                    WHERE b.search_id = ?
                ''', (search_id,)).fetchone()
                
                # Get detection stats
                detection_stats = conn.execute('''
                    SELECT COUNT(*) as total_detections,
                           SUM(has_bench) as images_with_benches,
                           MAX(max_confidence) as best_confidence
                    FROM detections d
                    JOIN images i ON d.image_id = i.id
                    JOIN benches b ON i.bench_id = b.id
                    WHERE b.search_id = ?
                ''', (search_id,)).fetchone()
                
                return {
                    'search_id': search_id,
                    'query': search_row['query'],
                    'start_lat': search_row['start_lat'],
                    'start_lng': search_row['start_lng'],
                    'search_radius': search_row['search_radius'],
                    'status': search_row['status'],
                    'created_at': search_row['created_at'],
                    'completed_at': search_row['completed_at'],
                    'bench_count': bench_count,
                    'total_images': image_stats['total_images'] or 0,
                    'successful_images': image_stats['successful_images'] or 0,
                    'total_detections': detection_stats['total_detections'] or 0,
                    'images_with_benches': detection_stats['images_with_benches'] or 0,
                    'best_confidence': detection_stats['best_confidence'] or 0.0
                }
                
        except sqlite3.Error as e:
            logger.error(f"Error getting search results: {e}")
            return {}
    
    def get_benches_with_detections(self, search_id: int) -> List[Dict]:
        """
        Get all benches with their images and detections for a search.
        
        Args:
            search_id: ID of the search
            
        Returns:
            List of bench dictionaries with nested image and detection data
        """
        try:
            with self._get_connection() as conn:
                query = '''
                    SELECT b.*, i.*, d.*,
                           b.id as bench_id, i.id as image_id, d.id as detection_id
                    FROM benches b
                    LEFT JOIN images i ON b.id = i.bench_id
                    LEFT JOIN detections d ON i.id = d.image_id
                    WHERE b.search_id = ?
                    ORDER BY b.id, i.heading
                '''
                
                rows = conn.execute(query, (search_id,)).fetchall()
                
                # Group results by bench
                benches = {}
                for row in rows:
                    bench_id = row['bench_id']
                    
                    if bench_id not in benches:
                        benches[bench_id] = {
                            'id': bench_id,
                            'osm_id': row['osm_id'],
                            'osm_type': row['osm_type'],
                            'lat': row['lat'],
                            'lng': row['lng'],
                            'tags': json.loads(row['tags']) if row['tags'] else {},
                            'images': []
                        }
                    
                    if row['image_id']:
                        image_data = {
                            'id': row['image_id'],
                            'heading': row['heading'],
                            'filepath': row['filepath'],
                            'filename': row['filename'],
                            'file_size': row['file_size'],
                            'capture_success': bool(row['capture_success']),
                            'capture_error': row['capture_error'],
                            'detection': None
                        }
                        
                        if row['detection_id']:
                            image_data['detection'] = {
                                'id': row['detection_id'],
                                'has_bench': bool(row['has_bench']),
                                'bench_count': row['bench_count'],
                                'max_confidence': row['max_confidence'],
                                'detections': json.loads(row['detections']) if row['detections'] else [],
                                'detection_success': bool(row['detection_success']),
                                'detection_error': row['detection_error']
                            }
                        
                        benches[bench_id]['images'].append(image_data)
                
                return list(benches.values())
                
        except sqlite3.Error as e:
            logger.error(f"Error getting benches with detections: {e}")
            return []
    
    def close(self):
        """Close database connection if needed."""
        # Using context managers, connections are automatically closed
        pass