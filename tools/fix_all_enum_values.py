#!/usr/bin/env python3
"""
Migration script to fix all enum values to use enum member names (uppercase).

SQLAlchemy validates against enum member names (PENDING, COMPLETED, FAILED)
rather than enum values ("pending", "completed", "failed"), so the database needs
to store uppercase values matching the enum member names.

This script updates all enum values in all tables:
- searches.status: pending -> COMPLETED, completed -> COMPLETED, failed -> FAILED
- bench_candidates.status: pending -> PENDING, image_download_done -> IMAGE_DOWNLOAD_DONE, detection_done -> DETECTION_DONE
- bench_candidates.source: osm -> OSM, mapillary -> MAPILLARY
- detections.source: roboflow -> ROBOFLOW, ultralytics -> ULTRALYTICS, etc.
- bench_reports.report_type: bad_detection -> BAD_DETECTION, etc.
- bench_reports.status: pending -> PENDING, etc.
- missing_bench_reports.status: pending -> PENDING, etc.

Run:
  python tools/fix_all_enum_values.py
  python tools/fix_all_enum_values.py --dry-run  # Preview changes
"""

import argparse
import logging
import os
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def fix_all_enum_values(dry_run: bool = False, db_path: str | None = None):
    """Fix all enum values in the database to use enum member names."""
    # Get database path from env or use default
    if not db_path:
        db_path = os.getenv("DATABASE_PATH", "data/benches.db")
    
    # Make path absolute if relative
    if not os.path.isabs(db_path):
        # Try to find from project root
        script_dir = Path(__file__).parent
        project_root = script_dir.parent
        db_path = project_root / db_path
    
    db_path = str(db_path)
    
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    changes = []

    try:
        # ============================================================
        # Fix searches.status
        # ============================================================
        logger.info("Checking searches.status...")
        cursor.execute("SELECT DISTINCT status FROM searches")
        statuses = [row[0] for row in cursor.fetchall()]
        logger.info(f"  Found statuses: {statuses}")

        updates = {
            "pending": "PENDING",
            "completed": "COMPLETED",
            "failed": "FAILED",
        }

        for old_status, new_status in updates.items():
            cursor.execute(
                "SELECT COUNT(*) FROM searches WHERE status = ?", (old_status,)
            )
            count = cursor.fetchone()[0]
            if count > 0:
                logger.info(
                    f"  Will update {count} rows: {old_status} -> {new_status}"
                )
                if not dry_run:
                    cursor.execute(
                        "UPDATE searches SET status = ? WHERE status = ?",
                        (new_status, old_status),
                    )
                changes.append(("searches.status", old_status, new_status, count))

        # ============================================================
        # Fix bench_candidates.status
        # ============================================================
        logger.info("Checking bench_candidates.status...")
        cursor.execute("SELECT DISTINCT status FROM bench_candidates")
        statuses = [row[0] for row in cursor.fetchall()]
        logger.info(f"  Found statuses: {statuses}")

        updates = {
            "pending": "PENDING",
            "image_download_done": "IMAGE_DOWNLOAD_DONE",
            "detection_done": "DETECTION_DONE",
        }

        for old_status, new_status in updates.items():
            cursor.execute(
                "SELECT COUNT(*) FROM bench_candidates WHERE status = ?",
                (old_status,),
            )
            count = cursor.fetchone()[0]
            if count > 0:
                logger.info(
                    f"  Will update {count} rows: {old_status} -> {new_status}"
                )
                if not dry_run:
                    cursor.execute(
                        "UPDATE bench_candidates SET status = ? WHERE status = ?",
                        (new_status, old_status),
                    )
                changes.append(
                    ("bench_candidates.status", old_status, new_status, count)
                )

        # ============================================================
        # Fix bench_candidates.source
        # ============================================================
        logger.info("Checking bench_candidates.source...")
        cursor.execute("SELECT DISTINCT source FROM bench_candidates")
        sources = [row[0] for row in cursor.fetchall()]
        logger.info(f"  Found sources: {sources}")

        updates = {
            "osm": "OSM",
            "mapillary": "MAPILLARY",
            "OSM": "OSM",  # Already correct
            "MAPILLARY": "MAPILLARY",  # Already correct
        }

        for old_source, new_source in updates.items():
            if old_source == new_source:
                continue
            cursor.execute(
                "SELECT COUNT(*) FROM bench_candidates WHERE source = ?",
                (old_source,),
            )
            count = cursor.fetchone()[0]
            if count > 0:
                logger.info(
                    f"  Will update {count} rows: {old_source} -> {new_source}"
                )
                if not dry_run:
                    cursor.execute(
                        "UPDATE bench_candidates SET source = ? WHERE source = ?",
                        (new_source, old_source),
                    )
                changes.append(
                    ("bench_candidates.source", old_source, new_source, count)
                )

        # ============================================================
        # Fix detections.source
        # ============================================================
        logger.info("Checking detections.source...")
        cursor.execute("SELECT DISTINCT source FROM detections")
        sources = [row[0] for row in cursor.fetchall()]
        logger.info(f"  Found sources: {sources}")

        updates = {
            "roboflow": "ROBOFLOW",
            "ultralytics": "ULTRALYTICS",
            "mapillary": "MAPILLARY",
            "multi_model": "MULTI_MODEL",
            "none": "NONE",
        }

        for old_source, new_source in updates.items():
            cursor.execute(
                "SELECT COUNT(*) FROM detections WHERE source = ?", (old_source,)
            )
            count = cursor.fetchone()[0]
            if count > 0:
                logger.info(
                    f"  Will update {count} rows: {old_source} -> {new_source}"
                )
                if not dry_run:
                    cursor.execute(
                        "UPDATE detections SET source = ? WHERE source = ?",
                        (new_source, old_source),
                    )
                changes.append(("detections.source", old_source, new_source, count))

        # ============================================================
        # Fix bench_reports.report_type
        # ============================================================
        logger.info("Checking bench_reports.report_type...")
        cursor.execute("SELECT COUNT(*) FROM bench_reports")
        if cursor.fetchone()[0] > 0:
            cursor.execute("SELECT DISTINCT report_type FROM bench_reports")
            types = [row[0] for row in cursor.fetchall()]
            logger.info(f"  Found types: {types}")

            updates = {
                "bad_detection": "BAD_DETECTION",
                "incorrect_location": "INCORRECT_LOCATION",
                "poor_image_quality": "POOR_IMAGE_QUALITY",
            }

            for old_type, new_type in updates.items():
                cursor.execute(
                    "SELECT COUNT(*) FROM bench_reports WHERE report_type = ?",
                    (old_type,),
                )
                count = cursor.fetchone()[0]
                if count > 0:
                    logger.info(
                        f"  Will update {count} rows: {old_type} -> {new_type}"
                    )
                    if not dry_run:
                        cursor.execute(
                            "UPDATE bench_reports SET report_type = ? WHERE report_type = ?",
                            (new_type, old_type),
                        )
                    changes.append(
                        ("bench_reports.report_type", old_type, new_type, count)
                    )

        # ============================================================
        # Fix bench_reports.status
        # ============================================================
        logger.info("Checking bench_reports.status...")
        cursor.execute("SELECT COUNT(*) FROM bench_reports")
        if cursor.fetchone()[0] > 0:
            cursor.execute("SELECT DISTINCT status FROM bench_reports")
            statuses = [row[0] for row in cursor.fetchall()]
            logger.info(f"  Found statuses: {statuses}")

            updates = {
                "pending": "PENDING",
                "reviewed": "REVIEWED",
                "resolved": "RESOLVED",
                "dismissed": "DISMISSED",
            }

            for old_status, new_status in updates.items():
                cursor.execute(
                    "SELECT COUNT(*) FROM bench_reports WHERE status = ?",
                    (old_status,),
                )
                count = cursor.fetchone()[0]
                if count > 0:
                    logger.info(
                        f"  Will update {count} rows: {old_status} -> {new_status}"
                    )
                    if not dry_run:
                        cursor.execute(
                            "UPDATE bench_reports SET status = ? WHERE status = ?",
                            (new_status, old_status),
                        )
                    changes.append(
                        ("bench_reports.status", old_status, new_status, count)
                    )

        # ============================================================
        # Fix missing_bench_reports.status
        # ============================================================
        logger.info("Checking missing_bench_reports.status...")
        cursor.execute("SELECT COUNT(*) FROM missing_bench_reports")
        if cursor.fetchone()[0] > 0:
            cursor.execute("SELECT DISTINCT status FROM missing_bench_reports")
            statuses = [row[0] for row in cursor.fetchall()]
            logger.info(f"  Found statuses: {statuses}")

            updates = {
                "pending": "PENDING",
                "verified": "VERIFIED",
                "added": "ADDED",
                "dismissed": "DISMISSED",
            }

            for old_status, new_status in updates.items():
                cursor.execute(
                    "SELECT COUNT(*) FROM missing_bench_reports WHERE status = ?",
                    (old_status,),
                )
                count = cursor.fetchone()[0]
                if count > 0:
                    logger.info(
                        f"  Will update {count} rows: {old_status} -> {new_status}"
                    )
                    if not dry_run:
                        cursor.execute(
                            "UPDATE missing_bench_reports SET status = ? WHERE status = ?",
                            (new_status, old_status),
                        )
                    changes.append(
                        (
                            "missing_bench_reports.status",
                            old_status,
                            new_status,
                            count,
                        )
                    )

        # Commit if not dry run
        if not dry_run and changes:
            conn.commit()
            logger.info(f"\n✅ Successfully updated {len(changes)} enum value types")
        elif dry_run:
            logger.info(f"\n🔍 DRY RUN: Would update {len(changes)} enum value types")
        else:
            logger.info("\n✅ No changes needed")

        # Summary
        if changes:
            logger.info("\n📊 Summary of changes:")
            for table_col, old_val, new_val, count in changes:
                logger.info(
                    f"  {table_col}: {count} rows {old_val} -> {new_val}"
                )

    except Exception as e:
        logger.error(f"Error fixing enum values: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Fix all enum values to use enum member names (uppercase)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        help="Path to database file (default: data/benches.db)",
    )
    args = parser.parse_args()

    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - No changes will be made\n")
    else:
        logger.info("⚠️  LIVE MODE - Changes will be applied to database\n")

    fix_all_enum_values(dry_run=args.dry_run, db_path=args.db_path)


if __name__ == "__main__":
    main()

