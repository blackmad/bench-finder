#!/usr/bin/env python3
"""
Migration script to add status field to bench_candidates table.

This script adds a 'status' column to the bench_candidates table with a default value of 'pending'.
"""

import logging
import sqlite3
import sys
from pathlib import Path

from bench_finder.config import DATABASE_PATH


logger = logging.getLogger(__name__)


def migrate_database():
    """Add status field to bench_candidates table."""
    logger.info(f"Starting migration for database: {DATABASE_PATH}")

    # Check if database exists
    if not Path(DATABASE_PATH).exists():
        logger.error(f"Database file not found: {DATABASE_PATH}")
        return False

    try:
        # Connect to the database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Check if the status column already exists
        cursor.execute("PRAGMA table_info(bench_candidates)")
        columns = [column[1] for column in cursor.fetchall()]

        if "status" in columns:
            logger.info("Status column already exists, skipping migration")
            return True

        # Add the status column with default value 'pending'
        logger.info("Adding status column to bench_candidates table")
        cursor.execute("""
            ALTER TABLE bench_candidates
            ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'
        """)

        # Create index for the status column
        logger.info("Creating index for status column")
        cursor.execute("""
            CREATE INDEX idx_bench_candidates_status ON bench_candidates(status)
        """)

        # Commit the changes
        conn.commit()

        # Verify the migration
        cursor.execute("SELECT COUNT(*) FROM bench_candidates WHERE status = 'pending'")
        pending_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM bench_candidates")
        total_count = cursor.fetchone()[0]

        logger.info("Migration completed successfully:")
        logger.info(f"  - Total candidates: {total_count}")
        logger.info(f"  - Candidates with 'pending' status: {pending_count}")

        conn.close()
        return True

    except Exception:
        logger.exception("Migration failed")
        if "conn" in locals():
            conn.rollback()
            conn.close()
        return False


def main():
    """Main migration function."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Starting bench_candidates status migration")

    success = migrate_database()

    if success:
        logger.info("Migration completed successfully")
        sys.exit(0)
    else:
        logger.error("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
