#!/usr/bin/env python3
"""
Database migration script to add image_source column to images table.
"""

import logging
import os
import sqlite3
import sys
from pathlib import Path


# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import after path is set up
try:
    from bench_finder.config import DATABASE_PATH
except ImportError:
    # Fallback if config import fails
    DATABASE_PATH = os.getenv("DATABASE_PATH", "data/benches.db")

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def migrate_database():
    """Migrate existing database to add image_source column to images table."""

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
        cursor.execute("PRAGMA table_info(images)")
        image_columns = [col[1] for col in cursor.fetchall()]

        logger.info(f"Current image columns: {image_columns}")

        # Add image_source column to images table if it doesn't exist
        if "image_source" not in image_columns:
            logger.info("Adding 'image_source' column to images table...")
            cursor.execute("ALTER TABLE images ADD COLUMN image_source TEXT")
            logger.info("✅ Added 'image_source' column to images table")
        else:
            logger.info("✅ 'image_source' column already exists in images table")

        conn.commit()
        logger.info("🎉 Database migration completed successfully!")

        # Verify the migration
        cursor.execute("PRAGMA table_info(images)")
        image_columns_after = [col[1] for col in cursor.fetchall()]
        logger.info(f"Image columns after migration: {image_columns_after}")

        if "image_source" in image_columns_after:
            logger.info("✅ Migration verification successful!")
        else:
            logger.error(
                "❌ Migration verification failed - image_source column not found"
            )
            return False

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


if __name__ == "__main__":
    print("🗄️  Bench Finder Database Migration - Add image_source Column")
    print("=" * 60)
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
        print("\n🎉 Migration completed successfully!")
        print("The 'image_source' column has been added to the images table.")
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)
