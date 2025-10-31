"""
Migration script to fix datasource enum case in database.

The DataSource enum expects uppercase values ('OSM', 'MAPILLARY'),
but the database may contain lowercase values ('osm', 'mapillary').

This script updates all datasource values in bench_candidates table
to match the enum definition.

Run:
  uv run python -m tools.fix_datasource_case
"""

import argparse
import logging
import sqlite3

from bench_finder.services.database import BenchDatabase


logger = logging.getLogger(__name__)


def fix_datasource_case(dry_run: bool = False):
    """Fix datasource enum case in database."""
    db = BenchDatabase()
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    try:
        # Check current values
        logger.info("Checking current datasource values...")
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM bench_candidates
            GROUP BY source
        """)
        current_values = cursor.fetchall()
        logger.info("Current datasource distribution:")
        for source, count in current_values:
            logger.info(f"  {source}: {count}")

        # Find rows that need fixing
        cursor.execute("""
            SELECT id, source
            FROM bench_candidates
            WHERE source != UPPER(source)
        """)
        rows_to_fix = cursor.fetchall()
        logger.info(f"Found {len(rows_to_fix)} rows with lowercase datasource values")

        if dry_run:
            logger.info("DRY RUN MODE - Would update the following rows:")
            for row_id, source in rows_to_fix[:10]:  # Show first 10
                logger.info(f"  ID {row_id}: '{source}' -> '{source.upper()}'")
            if len(rows_to_fix) > 10:
                logger.info(f"  ... and {len(rows_to_fix) - 10} more")
            return

        if not rows_to_fix:
            logger.info("✅ All datasource values are already correct (uppercase)")
            return

        # Update all rows to uppercase
        logger.info("Updating datasource values to uppercase...")
        cursor.execute("""
            UPDATE bench_candidates
            SET source = UPPER(source)
            WHERE source != UPPER(source)
        """)
        updated_count = cursor.rowcount
        conn.commit()
        logger.info(f"✅ Updated {updated_count} rows")

        # Verify the fix
        logger.info("Verifying fix...")
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM bench_candidates
            GROUP BY source
        """)
        final_values = cursor.fetchall()
        logger.info("Final datasource distribution:")
        for source, count in final_values:
            logger.info(f"  {source}: {count}")

        # Check if any lowercase values remain
        cursor.execute("""
            SELECT COUNT(*)
            FROM bench_candidates
            WHERE source != UPPER(source)
        """)
        remaining = cursor.fetchone()[0]
        if remaining > 0:
            logger.warning(f"⚠️  {remaining} rows still have lowercase values")
        else:
            logger.info("✅ All datasource values are now uppercase")

    except Exception:
        conn.rollback()
        logger.exception("Migration failed")
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Fix datasource enum case in database")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging"
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    fix_datasource_case(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
