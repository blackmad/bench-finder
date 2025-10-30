# Database Model Documentation

This document describes the current database model for the Bench Finder application, which uses SQLModel (built on SQLAlchemy) with SQLite as the database backend.

## Overview

The database is designed to support a comprehensive bench detection and management system that:
- Searches for bench locations from multiple data sources (OSM, Mapillary)
- Captures street view images of potential bench locations
- Performs AI-powered bench detection on those images
- Manages user reports and feedback
- Supports clustering and analysis of bench data

## Core Database Tables

### 1. `searches` Table
**Purpose**: Tracks search queries and their execution status.

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Unique search identifier |
| `query` | TEXT NOT NULL | Search query string |
| `start_lat` | REAL NOT NULL | Starting latitude for search |
| `start_lng` | REAL NOT NULL | Starting longitude for search |
| `search_radius` | INTEGER NOT NULL | Search radius in meters |
| `created_at` | DATETIME | Search creation timestamp |
| `completed_at` | DATETIME | Search completion timestamp (nullable) |
| `status` | TEXT | Search status: `pending`, `completed`, `failed` |

**Relationships**:
- One-to-many with `benches` table
- One-to-many with `bench_candidates` table

### 2. `benches` Table
**Purpose**: Stores confirmed bench locations from various data sources.

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Unique bench identifier |
| `search_id` | INTEGER | Foreign key to `searches.id` |
| `provider_id` | TEXT | Unified ID from OSM or Mapillary |
| `lat` | REAL NOT NULL | Bench latitude |
| `lng` | REAL NOT NULL | Bench longitude |
| `tags` | JSON | Source-specific metadata (OSM tags, Mapillary data) |
| `source` | TEXT | Data source: `OSM` or `MAPILLARY` |
| `external_id` | TEXT | External system ID (Mapillary image ID, etc.) |
| `created_at` | DATETIME | Bench creation timestamp |

**Relationships**:
- Many-to-one with `searches` table
- One-to-many with `images` table
- One-to-one with `images` table (representative image)

### 3. `images` Table
**Purpose**: Stores street view image metadata and capture results.

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Unique image identifier |
| `bench_id` | INTEGER NOT NULL | Foreign key to `benches.id` |
| `heading` | INTEGER NOT NULL | Camera heading in degrees |
| `filepath` | TEXT | Local file path to image |
| `filename` | TEXT | Image filename |
| `file_size` | INTEGER | File size in bytes |
| `capture_success` | BOOLEAN NOT NULL | Whether image capture succeeded |
| `capture_error` | TEXT | Error message if capture failed |
| `created_at` | DATETIME | Image creation timestamp |

**Relationships**:
- Many-to-one with `benches` table
- One-to-many with `detections` table

### 4. `detections` Table
**Purpose**: Stores AI detection results from various models.

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Unique detection identifier |
| `image_id` | INTEGER NOT NULL | Foreign key to `images.id` |
| `has_bench` | BOOLEAN NOT NULL | Whether any benches were detected |
| `bench_count` | INTEGER | Number of benches detected |
| `max_confidence` | REAL | Highest confidence score among detections |
| `detection_success` | BOOLEAN NOT NULL | Whether detection process succeeded |
| `detection_error` | TEXT | Error message if detection failed |
| `model_id` | TEXT NOT NULL | ID of the detection model used |
| `confidence_threshold` | REAL NOT NULL | Confidence threshold used |
| `source` | TEXT | Detection source: `ROBOFLOW`, `ULTRALYTICS`, `MAPILLARY`, `MULTI_MODEL`, `NONE` |
| `external_detection_id` | TEXT | External detection ID (for Mapillary) |
| `model_url` | TEXT | URL of the model used |
| `iou_threshold` | REAL | IoU threshold for NMS |
| `image_size` | INTEGER | Image size used for inference |
| `inference_time` | REAL | Time taken for inference (seconds) |
| `preprocess_time` | REAL | Time taken for preprocessing (seconds) |
| `postprocess_time` | REAL | Time taken for postprocessing (seconds) |
| `created_at` | DATETIME | Detection creation timestamp |

**Relationships**:
- Many-to-one with `images` table
- One-to-many with `detection_items` table

### 5. `detection_items` Table
**Purpose**: Stores individual detection objects with bounding boxes and polygons.

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Unique detection item identifier |
| `detection_id` | INTEGER NOT NULL | Foreign key to `detections.id` |
| `confidence` | REAL | Confidence score (0.0 to 1.0) |
| `bbox` | JSON | Bounding box coordinates `{x1, y1, x2, y2}` |
| `class_name` | TEXT | Class name (default: "bench") |
| `polygon` | JSON | Optional polygon coordinates for segmentation |
| `created_at` | DATETIME | Detection item creation timestamp |

**Relationships**:
- Many-to-one with `detections` table

### 6. `bench_candidates` Table
**Purpose**: Stores potential bench locations found during search phase.

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Unique candidate identifier |
| `search_id` | INTEGER NOT NULL | Foreign key to `searches.id` |
| `provider_id` | TEXT | Unified ID from OSM or Mapillary |
| `lat` | REAL NOT NULL | Candidate latitude |
| `lng` | REAL NOT NULL | Candidate longitude |
| `tags` | JSON | Source-specific metadata |
| `source` | TEXT | Data source: `OSM` or `MAPILLARY` |
| `external_id` | TEXT | External system ID |
| `confidence` | REAL | Confidence score if available |
| `status` | TEXT | Processing status: `pending`, `image_download_done`, `detection_done` |
| `created_at` | DATETIME | Candidate creation timestamp |

**Relationships**:
- Many-to-one with `searches` table

### 7. `bench_reports` Table
**Purpose**: Stores user reports of bad bench detections.

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Unique report identifier |
| `bench_id` | INTEGER NOT NULL | Foreign key to `benches.id` |
| `image_id` | INTEGER | Foreign key to `images.id` (specific image being reported) |
| `report_type` | TEXT | Report type: `bad_detection`, `incorrect_location`, `poor_image_quality` |
| `description` | TEXT | User description of the issue |
| `user_agent` | TEXT | Browser/app information |
| `ip_address` | TEXT | User IP address for spam prevention |
| `user_location_lat` | REAL | User's GPS latitude when reporting |
| `user_location_lng` | REAL | User's GPS longitude when reporting |
| `reported_image_filename` | TEXT | Filename of the reported image |
| `extra_metadata` | JSON | Additional metadata (device info, etc.) |
| `status` | TEXT | Report status: `pending`, `reviewed`, `resolved`, `dismissed` |
| `admin_notes` | TEXT | Admin notes for review |
| `created_at` | DATETIME | Report creation timestamp |
| `reviewed_at` | DATETIME | Report review timestamp |

**Relationships**:
- Many-to-one with `benches` table
- Many-to-one with `images` table

### 8. `missing_bench_reports` Table
**Purpose**: Stores user reports of missing benches.

| Field | Type | Description |
|-------|------|-------------|
| `id` | INTEGER PRIMARY KEY | Unique report identifier |
| `lat` | REAL NOT NULL | Reported bench latitude |
| `lng` | REAL NOT NULL | Reported bench longitude |
| `description` | TEXT | User description of the bench |
| `user_agent` | TEXT | Browser/app information |
| `ip_address` | TEXT | User IP address for spam prevention |
| `user_location_lat` | REAL | User's GPS latitude when reporting |
| `user_location_lng` | REAL | User's GPS longitude when reporting |
| `location_method` | TEXT | Location method: `gps` or `map_click` |
| `uploaded_image_filename` | TEXT | User-uploaded photo filename |
| `accuracy_meters` | REAL | GPS accuracy if available |
| `extra_metadata` | JSON | Additional metadata |
| `status` | TEXT | Report status: `pending`, `verified`, `added`, `dismissed` |
| `admin_notes` | TEXT | Admin notes for review |
| `created_at` | DATETIME | Report creation timestamp |
| `reviewed_at` | DATETIME | Report review timestamp |

## Data Flow

### 1. Search Process
1. User initiates search → `searches` table entry created
2. System finds potential bench locations → `bench_candidates` table entries created
3. For each candidate:
   - Street view images captured → `images` table entries created
   - AI detection performed → `detections` and `detection_items` table entries created
   - Confirmed benches → `benches` table entries created

### 2. Detection Pipeline
1. Image captured → `images` record with `capture_success` status
2. Detection model runs → `detections` record with results
3. Individual objects detected → `detection_items` records with bounding boxes/polygons
4. Bench confirmed if confidence exceeds threshold

### 3. User Reporting
1. User reports bad detection → `bench_reports` table entry
2. User reports missing bench → `missing_bench_reports` table entry
3. Admin reviews and updates status

## Key Design Decisions

### 1. Unified Data Sources
- Single `benches` table handles both OSM and Mapillary data
- `source` field distinguishes between data providers
- `provider_id` provides unified identification across sources

### 2. Flexible Detection System
- Supports multiple detection backends (Roboflow, Ultralytics, Mapillary)
- `detection_items` table stores individual detection objects
- JSON fields for bounding boxes and polygons support various formats

### 3. Comprehensive Metadata
- JSON fields store source-specific tags and metadata
- Timestamps track creation and processing times
- Error handling with dedicated error message fields

### 4. User Feedback Integration
- Separate tables for different types of user reports
- Admin workflow with status tracking
- Location and device metadata for context

## Database Configuration

- **Engine**: SQLite (file-based)
- **ORM**: SQLModel (built on SQLAlchemy)
- **Location**: Configurable via `DATABASE_PATH` setting
- **Auto-creation**: Tables created automatically on first run
- **JSON Support**: Native JSON column support for flexible metadata storage

## Relationships Summary

```
searches (1) ──→ (many) benches
searches (1) ──→ (many) bench_candidates
benches (1) ──→ (many) images
benches (1) ──→ (1) images (representative_image)
images (1) ──→ (many) detections
detections (1) ──→ (many) detection_items
benches (1) ──→ (many) bench_reports
images (1) ──→ (many) bench_reports
```

This database model provides a robust foundation for the bench detection system, supporting multiple data sources, flexible detection backends, comprehensive user feedback, and detailed analytics capabilities.
