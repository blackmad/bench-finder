#!/usr/bin/env python3
"""
Migration script to add R-tree spatial indexing for bounding box queries.

SQLite R-tree virtual tables provide optimal performance for spatial queries
like bounding box searches. This script:
1. Creates an R-tree virtual table for bench_candidates
2. Populates it with existing data
3. Creates triggers to maintain the index automatically
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


def add_rtree_index():
    """Add R-tree spatial index for bench_candidates table."""
    logger.info(f"Setting up R-tree spatial index for database: {DATABASE_PATH}")

    # Check if database exists
    if not Path(DATABASE_PATH).exists():
        logger.error(f"Database file not found: {DATABASE_PATH}")
        return False

    try:
        # Connect to the database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # R-tree is built into SQLite by default, no need to enable it
        logger.info("✅ R-tree support is available (built into SQLite)")

        # Check if R-tree table already exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rtree_bench_candidates';"
        )
        if cursor.fetchone():
            logger.info("⏭️  R-tree table already exists, checking if populated...")

            # Check if it has data
            cursor.execute("SELECT COUNT(*) FROM rtree_bench_candidates;")
            count = cursor.fetchone()[0]
            if count > 0:
                logger.info(f"✅ R-tree index already populated with {count} entries")
                conn.close()
                return True
            else:
                logger.info("⚠️  R-tree table exists but is empty, populating...")
        else:
            # Create R-tree virtual table
            # R-tree stores bounding boxes: minX, maxX, minY, maxY
            # For lat/lng: minX = lng, maxX = lng, minY = lat, maxY = lat (point)
            logger.info("Creating R-tree virtual table...")
            cursor.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS rtree_bench_candidates USING rtree(
                    id,              -- Integer primary key (links to bench_candidates.id)
                    minLng, maxLng,  -- Longitude bounds (X coordinate)
                    minLat, maxLat   -- Latitude bounds (Y coordinate)
                );
                """
            )
            logger.info("✅ Created R-tree virtual table")

        # Populate R-tree with existing data
        logger.info("Populating R-tree index with existing bench_candidates...")
        cursor.execute(
            """
            INSERT OR REPLACE INTO rtree_bench_candidates (id, minLng, maxLng, minLat, maxLat)
            SELECT id, lng, lng, lat, lat
            FROM bench_candidates
            WHERE id IS NOT NULL;
            """
        )
        populated_count = cursor.rowcount
        logger.info(f"✅ Populated R-tree index with {populated_count} entries")

        # Create triggers to maintain R-tree index automatically
        logger.info("Creating triggers to maintain R-tree index...")

        # Trigger for INSERT
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS rtree_bench_candidates_insert
            AFTER INSERT ON bench_candidates
            WHEN NEW.id IS NOT NULL
            BEGIN
                INSERT OR REPLACE INTO rtree_bench_candidates (id, minLng, maxLng, minLat, maxLat)
                VALUES (NEW.id, NEW.lng, NEW.lng, NEW.lat, NEW.lat);
            END;
            """
        )
        logger.info("✅ Created INSERT trigger")

        # Trigger for UPDATE
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS rtree_bench_candidates_update
            AFTER UPDATE OF lat, lng ON bench_candidates
            WHEN NEW.id IS NOT NULL
            BEGIN
                INSERT OR REPLACE INTO rtree_bench_candidates (id, minLng, maxLng, minLat, maxLat)
                VALUES (NEW.id, NEW.lng, NEW.lng, NEW.lat, NEW.lat);
            END;
            """
        )
        logger.info("✅ Created UPDATE trigger")

        # Trigger for DELETE
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS rtree_bench_candidates_delete
            AFTER DELETE ON bench_candidates
            WHEN OLD.id IS NOT NULL
            BEGIN
                DELETE FROM rtree_bench_candidates WHERE id = OLD.id;
            END;
            """
        )
        logger.info("✅ Created DELETE trigger")

        # Commit the changes
        conn.commit()

        logger.info("✅ R-tree spatial index setup completed successfully")

        # Verify the setup
        cursor.execute("SELECT COUNT(*) FROM rtree_bench_candidates;")
        rtree_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM bench_candidates WHERE id IS NOT NULL;")
        bench_count = cursor.fetchone()[0]

        logger.info(
            f"\n📊 R-tree index status:\n"
            f"   R-tree entries: {rtree_count}\n"
            f"   Bench candidates: {bench_count}\n"
            f"   Coverage: {'✅ Complete' if rtree_count == bench_count else '⚠️  Mismatch'}"
        )

        conn.close()
        return True

    except Exception:
        logger.exception("❌ Error setting up R-tree spatial index")
        return False


if __name__ == "__main__":
    success = add_rtree_index()
    sys.exit(0 if success else 1)
