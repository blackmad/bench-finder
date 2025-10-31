"""
Migration script to fix bench_candidate_status to use uppercase enum member names.

SQLAlchemy validates against enum member names (PENDING, DETECTION_DONE)
rather than enum values ("pending", "detection_done"), so the database needs
to store uppercase values.

This script converts all status values to uppercase to match enum member names.

Run:
  uv run python -m tools.fix_bench_candidate_status_to_uppercase
"""

import argparse
import logging
import sqlite3

from bench_finder.services.database import BenchDatabase


logger = logging.getLogger(__name__)


def fix_bench_candidate_status_to_uppercase(dry_run: bool = False):
    """Fix bench_candidate_status to use uppercase enum member names."""
    db = BenchDatabase()
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    try:
        # Check current values
        logger.info("Checking current bench_candidate status values...")
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM bench_candidates
            GROUP BY status
        """)
        current_values = cursor.fetchall()
        logger.info("Current status distribution:")
        for status, count in current_values:
            logger.info(f"  {status}: {count}")

        # Map lowercase values to uppercase enum member names
        value_mapping = {
            "pending": "PENDING",
            "image_download_done": "IMAGE_DOWNLOAD_DONE",
            "detection_done": "DETECTION_DONE",
        }

        # Find rows that need fixing (anything that's not already uppercase)
        statuses_to_fix = []
        for status, count in current_values:
            uppercase = value_mapping.get(status.lower(), None)
            if uppercase and uppercase != status:
                statuses_to_fix.append((status, uppercase, count))

        if not statuses_to_fix:
            # Check if all values are already uppercase
            all_uppercase = all(
                status.upper() == status for status, _ in current_values
            )
            if all_uppercase:
                logger.info("✅ All status values are already uppercase")
                return
            else:
                logger.warning(
                    "Found unexpected status values that don't match expected enum values"
                )

        logger.info(f"Found {len(statuses_to_fix)} status values that need fixing:")
        total_rows = 0
        for old_status, new_status, count in statuses_to_fix:
            logger.info(f"  '{old_status}' -> '{new_status}' ({count} rows)")
            total_rows += count

        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
            return

        # Update all rows to uppercase
        logger.info("Updating status values to uppercase enum member names...")
        updated_count = 0

        for old_status, new_status, _ in statuses_to_fix:
            cursor.execute(
                """
                UPDATE bench_candidates
                SET status = ?
                WHERE status = ?
            """,
                (new_status, old_status),
            )
            count = cursor.rowcount
            updated_count += count
            logger.info(f"  Updated {count} rows: '{old_status}' -> '{new_status}'")

        conn.commit()
        logger.info(f"✅ Updated {updated_count} rows total")

        # Verify the fix
        logger.info("Verifying fix...")
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM bench_candidates
            GROUP BY status
            ORDER BY status
        """)
        final_values = cursor.fetchall()
        logger.info("Final status distribution:")
        for status, count in final_values:
            logger.info(f"  {status}: {count}")

        # Verify all are uppercase and match expected enum member names
        expected = {"PENDING", "IMAGE_DOWNLOAD_DONE", "DETECTION_DONE"}
        actual = {status for status, _ in final_values}

        if actual == expected:
            logger.info("✅ All status values match expected enum member names")
        elif actual.issubset(expected):
            logger.info("✅ All status values are valid enum member names")
        else:
            unexpected = actual - expected
            logger.warning(f"⚠️  Found unexpected status values: {unexpected}")

    except Exception:
        conn.rollback()
        logger.exception("Migration failed")
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Fix bench_candidate_status to use uppercase enum member names"
    )
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

    fix_bench_candidate_status_to_uppercase(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
