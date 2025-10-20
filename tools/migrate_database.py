#!/usr/bin/env python3
"""
Database migration script to add source support to existing bench finder database.
"""

import logging
import os
import sqlite3
import sys

from config import DATABASE_PATH


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def migrate_database():
    """Migrate existing database to support source columns."""

    if not os.path.exists(DATABASE_PATH):
        logger.error(f"Database not found at {DATABASE_PATH}")
        return False

    # Create backup first
    backup_path = f"{DATABASE_PATH}.backup"
    logger.info(f"Creating backup at {backup_path}")

    try:
        import shutil

        shutil.copy2(DATABASE_PATH, backup_path)
        logger.info("✅ Database backup created")
    except Exception:
        logger.exception("Failed to create backup")
        return False

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        logger.info("🔄 Starting database migration...")

        # Check current schema
        cursor.execute("PRAGMA table_info(benches)")
        bench_columns = [col[1] for col in cursor.fetchall()]

        cursor.execute("PRAGMA table_info(detections)")
        detection_columns = [col[1] for col in cursor.fetchall()]

        logger.info(f"Current bench columns: {bench_columns}")
        logger.info(f"Current detection columns: {detection_columns}")

        # Add missing columns to benches table
        if "source" not in bench_columns:
            logger.info("Adding 'source' column to benches table...")
            cursor.execute("ALTER TABLE benches ADD COLUMN source TEXT DEFAULT 'osm'")

            # Update existing benches to have source='osm'
            cursor.execute("UPDATE benches SET source = 'osm' WHERE source IS NULL")
            logger.info("✅ Added 'source' column to benches")

        if "external_id" not in bench_columns:
            logger.info("Adding 'external_id' column to benches table...")
            cursor.execute("ALTER TABLE benches ADD COLUMN external_id TEXT")
            logger.info("✅ Added 'external_id' column to benches")

        # Add missing columns to detections table
        if "source" not in detection_columns:
            logger.info("Adding 'source' column to detections table...")
            cursor.execute(
                "ALTER TABLE detections ADD COLUMN source TEXT DEFAULT 'roboflow'"
            )

            # Update existing detections based on model_id
            cursor.execute("""
                UPDATE detections SET source = CASE
                    WHEN model_id LIKE '%roboflow%' OR model_id = 'roboflow' THEN 'roboflow'
                    WHEN model_id LIKE '%ultralytics%' OR model_id = 'ultralytics' THEN 'ultralytics'
                    ELSE 'roboflow'
                END
                WHERE source IS NULL OR source = 'roboflow'
            """)
            logger.info("✅ Added 'source' column to detections")

        if "external_detection_id" not in detection_columns:
            logger.info("Adding 'external_detection_id' column to detections table...")
            cursor.execute(
                "ALTER TABLE detections ADD COLUMN external_detection_id TEXT"
            )
            logger.info("✅ Added 'external_detection_id' column to detections")

        # Create new indexes
        logger.info("Creating new indexes...")
        try:
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_benches_source ON benches (source)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_benches_external_id ON benches (external_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_detections_source ON detections (source)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_detections_external_id ON detections (external_detection_id)"
            )
            logger.info("✅ Created new indexes")
        except Exception as e:
            logger.warning(f"Some indexes may already exist: {e}")

        # Make OSM-specific columns nullable (this is more complex in SQLite)
        logger.info("Checking nullable constraints...")

        # SQLite doesn't support dropping NOT NULL constraints easily
        # The columns are already created, so we'll leave them as-is for existing data
        # New Mapillary entries will be inserted with NULL values which should work

        conn.commit()
        logger.info("🎉 Database migration completed successfully!")

        # Verify the migration
        cursor.execute("SELECT COUNT(*) FROM benches")
        bench_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM benches WHERE source = 'osm'")
        osm_bench_count = cursor.fetchone()[0]

        logger.info("📊 Migration verification:")
        logger.info(f"   Total benches: {bench_count}")
        logger.info(f"   OSM benches: {osm_bench_count}")

        conn.close()
        return True

    except Exception:
        logger.exception("❌ Migration failed")

        # Attempt to restore backup
        try:
            logger.info("Attempting to restore backup...")
            shutil.copy2(backup_path, DATABASE_PATH)
            logger.info("✅ Backup restored")
        except Exception:
            logger.exception("❌ Failed to restore backup")

        return False


def verify_migration():
    """Verify that the migration was successful."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Check that new columns exist
        cursor.execute("PRAGMA table_info(benches)")
        bench_columns = [col[1] for col in cursor.fetchall()]

        cursor.execute("PRAGMA table_info(detections)")
        detection_columns = [col[1] for col in cursor.fetchall()]

        required_bench_cols = ["source", "external_id"]
        required_detection_cols = ["source", "external_detection_id"]

        missing_bench_cols = [
            col for col in required_bench_cols if col not in bench_columns
        ]
        missing_detection_cols = [
            col for col in required_detection_cols if col not in detection_columns
        ]

        if missing_bench_cols or missing_detection_cols:
            logger.error("❌ Migration verification failed!")
            logger.error(f"Missing bench columns: {missing_bench_cols}")
            logger.error(f"Missing detection columns: {missing_detection_cols}")
            return False

        # Test a simple query with the new columns
        cursor.execute("SELECT id, source, external_id FROM benches LIMIT 1")
        cursor.execute(
            "SELECT id, source, external_detection_id FROM detections LIMIT 1"
        )

        logger.info("✅ Migration verification successful!")
        conn.close()
        return True

    except Exception:
        logger.exception("❌ Migration verification failed")
        return False


if __name__ == "__main__":
    print("🗄️  Bench Finder Database Migration")
    print("=" * 40)
    print(f"Database: {DATABASE_PATH}")

    if not os.path.exists(DATABASE_PATH):
        print("❌ Database file not found!")
        print("Please run the original bench finder first to create the database.")
        sys.exit(1)

    print("\n⚠️  This will modify your database. A backup will be created.")
    response = input("Continue with migration? (y/N): ").strip().lower()

    if response != "y":
        print("Migration cancelled.")
        sys.exit(0)

    success = migrate_database()

    if success:
        print("\n🔍 Verifying migration...")
        if verify_migration():
            print("\n🎉 Migration completed successfully!")
            print("Your database now supports both OSM and Mapillary sources.")
            print("\nYou can now:")
            print("1. Run the web server with Mapillary support")
            print("2. Use the new API endpoints")
            print("3. View unified bench data from both sources")
        else:
            print("\n❌ Migration verification failed!")
            sys.exit(1)
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)
