#!/usr/bin/env python3
"""
Migration script to add firebase_url column to images table.

This script adds the firebase_url column to the images table if it doesn't exist.
The column is defined in the model but may not exist in older database schemas.
"""

import sys
from pathlib import Path


# Add parent directory to path to import bench_finder modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from bench_finder.config import DATABASE_PATH, DATABASE_URL
from bench_finder.models.unified_models import create_database_engine


def add_firebase_url_column():
    """Add firebase_url column to images table if it doesn't exist."""
    # Create database engine
    if DATABASE_URL:
        engine = create_database_engine(database_url=DATABASE_URL)
    else:
        engine = create_database_engine(database_path=DATABASE_PATH)

    # Check if column exists and add it if missing
    with engine.connect() as conn:
        # For SQLite, check if column exists
        if "sqlite" in str(engine.url):
            # Get table info to check if column exists
            result = conn.execute(text("PRAGMA table_info(images)"))
            columns = [row[1] for row in result]

            if "firebase_url" not in columns:
                print("Adding firebase_url column to images table (SQLite)...")
                conn.execute(text("ALTER TABLE images ADD COLUMN firebase_url TEXT"))
                conn.commit()
                print("✓ Successfully added firebase_url column")
            else:
                print("✓ firebase_url column already exists")
        else:
            # For PostgreSQL, use information_schema
            result = conn.execute(
                text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'images' AND column_name = 'firebase_url'
                """)
            )

            if result.fetchone() is None:
                print("Adding firebase_url column to images table (PostgreSQL)...")
                conn.execute(text("ALTER TABLE images ADD COLUMN firebase_url VARCHAR"))
                conn.commit()
                print("✓ Successfully added firebase_url column")
            else:
                print("✓ firebase_url column already exists")


if __name__ == "__main__":
    try:
        add_firebase_url_column()
        print("Migration completed successfully!")
    except Exception as e:
        print(f"Error running migration: {e}", file=sys.stderr)
        sys.exit(1)
