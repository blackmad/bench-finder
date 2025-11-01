#!/usr/bin/env python3
"""
Migration script to add structured address columns to the reverse_geocodes table.

Usage:
    python tools/add_structured_address_columns.py [--db-path PATH]
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
    """Add structured address columns to the reverse_geocodes table."""

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
    except Exception:
        logger.exception("Failed to create backup")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        logger.info("🔄 Adding structured address columns...")

        # Check which columns already exist
        cursor.execute("PRAGMA table_info(reverse_geocodes)")
        existing_columns = [col[1] for col in cursor.fetchall()]

        columns_to_add = [
            ("street_number", "TEXT"),
            ("street_name", "TEXT"),
            ("city", "TEXT"),
            ("state", "TEXT"),
            ("postal_code", "TEXT"),
            ("country", "TEXT"),
        ]

        added_count = 0
        for column_name, column_type in columns_to_add:
            if column_name not in existing_columns:
                cursor.execute(
                    f"ALTER TABLE reverse_geocodes ADD COLUMN {column_name} {column_type}"
                )
                logger.info(f"  ✅ Added column: {column_name}")
                added_count += 1
            else:
                logger.info(f"  ⏭️  Column already exists: {column_name}")

        conn.commit()
        conn.close()

        if added_count > 0:
            logger.info(f"✅ Added {added_count} new columns to reverse_geocodes table")
        else:
            logger.info("✅ All structured address columns already exist")
        return True

    except sqlite3.OperationalError:
        logger.exception("Failed to add columns")
        return False
    except Exception:
        logger.exception("Unexpected error")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Add structured address columns to reverse_geocodes table"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/benches.db",
        help="Path to SQLite database file (default: data/benches.db)",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Migration: Add structured address columns")
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
