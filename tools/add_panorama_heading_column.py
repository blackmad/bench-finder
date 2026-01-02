#!/usr/bin/env python3
"""
Migration script to add panorama_heading column to images table.

This script adds the panorama_heading column to the images table if it doesn't exist.
The column stores the heading/orientation of the panorama itself from streetlevel/lookaround APIs.
"""

import sys
from pathlib import Path


# Add parent directory to path to import bench_finder modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text

from bench_finder.config import DATABASE_PATH, DATABASE_URL
from bench_finder.models.unified_models import create_database_engine


def add_panorama_heading_column():
    """Add panorama_heading column to images table if it doesn't exist."""
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

            if "panorama_heading" not in columns:
                print("Adding panorama_heading column to images table (SQLite)...")
                conn.execute(text("ALTER TABLE images ADD COLUMN panorama_heading REAL"))
                conn.commit()
                print("✓ Successfully added panorama_heading column")
            else:
                print("✓ panorama_heading column already exists")
        else:
            # For PostgreSQL, use information_schema
            result = conn.execute(
                text("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'images' AND column_name = 'panorama_heading'
                """)
            )

            if result.fetchone() is None:
                print("Adding panorama_heading column to images table (PostgreSQL)...")
                conn.execute(text("ALTER TABLE images ADD COLUMN panorama_heading DOUBLE PRECISION"))
                conn.commit()
                print("✓ Successfully added panorama_heading column")
            else:
                print("✓ panorama_heading column already exists")


if __name__ == "__main__":
    try:
        add_panorama_heading_column()
        print("Migration completed successfully!")
    except Exception as e:
        print(f"Error running migration: {e}", file=sys.stderr)
        sys.exit(1)

