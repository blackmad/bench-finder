#!/usr/bin/env python3
"""
Migration script to add the reverse_geocodes table to the database.

This script creates the reverse_geocodes table that stores reverse geocoding
results for bench candidates.

Usage:
    python tools/add_reverse_geocodes_table.py [--db-path PATH]
"""

import argparse
import logging
import os
import sqlite3
import sys


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def migrate_database(db_path: str):
    """Add reverse_geocodes table to the SQLite database."""

    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        return False

    # Create backup first
    backup_path = f"{db_path}.backup"
    logger.info(f"Creating backup at {backup_path}")

    try:
        import shutil

        shutil.copy2(db_path, backup_path)
        logger.info("✅ Database backup created")
    except Exception as e:
        logger.exception(f"Failed to create backup: {e}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        logger.info("🔄 Checking if reverse_geocodes table exists...")

        # Check if table already exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='reverse_geocodes'"
        )
        if cursor.fetchone():
            logger.info("✅ reverse_geocodes table already exists")
            conn.close()
            return True

        logger.info("Creating reverse_geocodes table...")

        # Create the reverse_geocodes table
        cursor.execute("""
            CREATE TABLE reverse_geocodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bench_candidate_id INTEGER NOT NULL UNIQUE,
                formatted_address TEXT NOT NULL,
                raw_response TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME,
                FOREIGN KEY (bench_candidate_id) REFERENCES bench_candidates (id)
            )
        """)

        # Create index on bench_candidate_id for faster lookups
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_reverse_geocodes_bench_candidate_id "
            "ON reverse_geocodes (bench_candidate_id)"
        )

        conn.commit()
        conn.close()

        logger.info("✅ Reverse geocodes table created successfully")
        return True

    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            logger.info("✅ reverse_geocodes table already exists")
            return True
        logger.exception(f"Failed to create table: {e}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Add reverse_geocodes table to the database"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/benches.db",
        help="Path to SQLite database file (default: data/benches.db)",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Migration: Add reverse_geocodes table")
    logger.info("=" * 60)
    logger.info(f"Database path: {args.db_path}")

    success = migrate_database(args.db_path)

    if success:
        logger.info("✅ Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
