#!/usr/bin/env python3
"""
Migration script to add performance indexes for database queries.

This script adds critical indexes to improve query performance for the benches API endpoint.
"""

import logging
import sqlite3
import sys
from pathlib import Path

from bench_finder.config import DATABASE_PATH


logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def add_indexes():
    """Add all performance indexes."""
    logger.info(f"Starting index creation for database: {DATABASE_PATH}")

    # Check if database exists
    if not Path(DATABASE_PATH).exists():
        logger.error(f"Database file not found: {DATABASE_PATH}")
        return False

    try:
        # Connect to the database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Enable WAL mode for better performance
        cursor.execute("PRAGMA journal_mode=WAL;")
        logger.info("✅ Enabled WAL mode")

        # Increase cache size (negative = KB, so -10000 = 10MB)
        cursor.execute("PRAGMA cache_size = -10000;")
        logger.info("✅ Set cache size to 10MB")

        indexes = [
            # Foreign Key Indexes
            (
                "idx_processed_benches_bench_candidate_id",
                "processed_benches(bench_candidate_id)",
                "Foreign key index for ProcessedBench -> BenchCandidate",
            ),
            (
                "idx_processed_benches_best_detection_id",
                "processed_benches(best_detection_id)",
                "Foreign key index for ProcessedBench -> Detection",
            ),
            (
                "idx_processed_benches_best_image_id",
                "processed_benches(best_image_id)",
                "Foreign key index for ProcessedBench -> Image",
            ),
            (
                "idx_images_bench_candidate_id",
                "images(bench_candidate_id)",
                "Foreign key index for Image -> BenchCandidate",
            ),
            (
                "idx_detections_image_id",
                "detections(image_id)",
                "Foreign key index for Detection -> Image",
            ),
            (
                "idx_detection_items_detection_id",
                "detection_items(detection_id)",
                "Foreign key index for DetectionItem -> Detection",
            ),
            # Filter Column Indexes
            (
                "idx_processed_benches_detection_status",
                "processed_benches(detection_status)",
                "Index for detection_status filtering",
            ),
            (
                "idx_detections_max_confidence",
                "detections(max_confidence)",
                "Index for confidence filtering",
            ),
            (
                "idx_bench_candidates_source",
                "bench_candidates(source)",
                "Index for source filtering",
            ),
            (
                "idx_images_capture_success",
                "images(capture_success)",
                "Index for capture_success filtering",
            ),
            # Composite Indexes for Common Query Patterns
            (
                "idx_processed_benches_status_detection",
                "processed_benches(detection_status, best_detection_id)",
                "Composite index for status + detection lookup",
            ),
            (
                "idx_images_bench_success",
                "images(bench_candidate_id, capture_success)",
                "Composite index for bench + success filtering",
            ),
            (
                "idx_bench_candidates_source_lat_lng",
                "bench_candidates(source, lat, lng)",
                "Composite index for source + spatial queries",
            ),
            # Spatial Index for Distance Sorting
            (
                "idx_bench_candidates_lat_lng",
                "bench_candidates(lat, lng)",
                "Spatial index for distance-based queries",
            ),
            # Separate indexes for efficient bbox BETWEEN queries
            # SQLite can use both indexes efficiently for AND conditions
            (
                "idx_bench_candidates_lat",
                "bench_candidates(lat)",
                "Single-column index on lat for bbox queries",
            ),
            (
                "idx_bench_candidates_lng",
                "bench_candidates(lng)",
                "Single-column index on lng for bbox queries",
            ),
        ]

        created = 0
        skipped = 0

        for index_name, index_def, description in indexes:
            try:
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON {index_def}"
                )
                if cursor.rowcount > 0:
                    logger.info(f"✅ Created index: {index_name} - {description}")
                    created += 1
                else:
                    logger.debug(f"⏭️  Index already exists: {index_name}")
                    skipped += 1
            except Exception as e:
                logger.warning(f"⚠️  Failed to create index {index_name}: {e}")
                skipped += 1

        # Commit the changes
        conn.commit()

        logger.info(
            f"\n📊 Index creation complete:\n"
            f"   Created: {created}\n"
            f"   Skipped (already exist): {skipped}\n"
            f"   Total: {len(indexes)}"
        )

        # Analyze tables to update query planner statistics
        logger.info("📈 Analyzing tables to update query planner statistics...")
        for table in [
            "processed_benches",
            "bench_candidates",
            "images",
            "detections",
            "detection_items",
        ]:
            try:
                cursor.execute(f"ANALYZE {table};")
            except Exception as e:
                logger.warning(f"Could not analyze {table}: {e}")

        conn.commit()

        # Run optimize
        cursor.execute("PRAGMA optimize;")
        logger.info("✅ Optimized database")

        conn.close()
        logger.info("✅ Index creation completed successfully")
        return True

    except Exception:
        logger.exception("❌ Error creating indexes")
        return False


if __name__ == "__main__":
    success = add_indexes()
    sys.exit(0 if success else 1)
