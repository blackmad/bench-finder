"""
Migration script to fix bench_candidate_status enum case in database.

The BenchCandidateStatus enum expects lowercase values ('pending', 'image_download_done', 'detection_done'),
but the database may contain uppercase or mixed-case values.

This script updates all status values in bench_candidates table
to match the enum definition.

Run:
  uv run python -m tools.fix_bench_candidate_status_case
"""

import argparse
import logging
import sqlite3

from bench_finder.services.database import BenchDatabase


logger = logging.getLogger(__name__)


def fix_bench_candidate_status_case(dry_run: bool = False):
    """Fix bench_candidate_status enum case in database."""
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

        # Expected enum values (lowercase)
        expected_values = {
            "pending": "pending",
            "PENDING": "pending",
            "image_download_done": "image_download_done",
            "IMAGE_DOWNLOAD_DONE": "image_download_done",
            "IMAGE_DOWNL..": "image_download_done",  # Handle truncated display
            "detection_done": "detection_done",
            "DETECTION_DONE": "detection_done",
            "DETECTION_D..": "detection_done",  # Handle truncated display
        }

        # Also check for exact matches that might need normalization
        cursor.execute("""
            SELECT DISTINCT status
            FROM bench_candidates
        """)
        all_statuses = [row[0] for row in cursor.fetchall()]

        statuses_to_fix = []
        for status in all_statuses:
            normalized = expected_values.get(status)
            if normalized and normalized != status:
                statuses_to_fix.append((status, normalized))
            elif status.upper() == status and status.lower() in expected_values:
                # All uppercase, needs to be lowercase
                statuses_to_fix.append((status, status.lower()))

        logger.info(f"Found {len(statuses_to_fix)} status values that need fixing:")
        for old_status, new_status in statuses_to_fix:
            cursor.execute(
                "SELECT COUNT(*) FROM bench_candidates WHERE status = ?", (old_status,)
            )
            count = cursor.fetchone()[0]
            logger.info(f"  '{old_status}' -> '{new_status}' ({count} rows)")

        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
            return

        if not statuses_to_fix:
            logger.info("✅ All status values are already correct (lowercase)")
            return

        # Update all rows to lowercase
        logger.info("Updating status values to lowercase...")
        updated_count = 0

        for old_status, new_status in statuses_to_fix:
            cursor.execute(
                """
                UPDATE bench_candidates
                SET status = ?
                WHERE status = ?
            """,
                (new_status, old_status),
            )
            updated_count += cursor.rowcount

        conn.commit()
        logger.info(f"✅ Updated {updated_count} rows")

        # Verify the fix
        logger.info("Verifying fix...")
        cursor.execute("""
            SELECT status, COUNT(*) as count
            FROM bench_candidates
            GROUP BY status
        """)
        final_values = cursor.fetchall()
        logger.info("Final status distribution:")
        for status, count in final_values:
            logger.info(f"  {status}: {count}")

        # Check if any uppercase values remain
        cursor.execute("""
            SELECT COUNT(*)
            FROM bench_candidates
            WHERE status != LOWER(status)
        """)
        remaining = cursor.fetchone()[0]
        if remaining > 0:
            logger.warning(
                f"⚠️  {remaining} rows still have uppercase/mixed-case values"
            )
        else:
            logger.info("✅ All status values are now lowercase")

    except Exception:
        conn.rollback()
        logger.exception("Migration failed")
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Fix bench_candidate_status enum case in database"
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

    fix_bench_candidate_status_case(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
