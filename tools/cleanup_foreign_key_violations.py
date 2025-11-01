#!/usr/bin/env python3
"""
Find and clean up foreign key violations in the database.

This script identifies orphaned records that reference non-existent parent records
and optionally deletes them to maintain referential integrity.

Usage:
    python tools/cleanup_foreign_key_violations.py [--dry-run] [--fix]
"""

import argparse
import logging
import sys
from collections import defaultdict
from pathlib import Path


# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from bench_finder.models.unified_models import (  # noqa: E402
    BenchCandidate,
    BenchReport,
    Detection,
    DetectionItem,
    Image,
    ProcessedBench,
    ReverseGeocode,
)
from bench_finder.services.database import BenchDatabase  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def find_orphaned_images(session: Session) -> list[Image]:
    """Find images with invalid bench_candidate_id references."""
    result = session.execute(
        text("""
            SELECT i.id, i.bench_candidate_id
            FROM images i
            LEFT JOIN bench_candidates bc ON i.bench_candidate_id = bc.id
            WHERE bc.id IS NULL
        """)
    ).fetchall()

    orphaned = []
    for row in result:
        image = session.get(Image, row[0])
        if image:
            orphaned.append(image)
    return orphaned


def find_orphaned_detections(session: Session) -> list[Detection]:
    """Find detections with invalid image_id references."""
    result = session.execute(
        text("""
            SELECT d.id, d.image_id
            FROM detections d
            LEFT JOIN images i ON d.image_id = i.id
            WHERE i.id IS NULL
        """)
    ).fetchall()

    orphaned = []
    for row in result:
        detection = session.get(Detection, row[0])
        if detection:
            orphaned.append(detection)
    return orphaned


def find_orphaned_detection_items(session: Session) -> list[DetectionItem]:
    """Find detection items with invalid detection_id references."""
    result = session.execute(
        text("""
            SELECT di.id, di.detection_id
            FROM detection_items di
            LEFT JOIN detections d ON di.detection_id = d.id
            WHERE d.id IS NULL
        """)
    ).fetchall()

    orphaned = []
    for row in result:
        item = session.get(DetectionItem, row[0])
        if item:
            orphaned.append(item)
    return orphaned


def find_orphaned_reverse_geocodes(session: Session) -> list[ReverseGeocode]:
    """Find reverse geocodes with invalid bench_candidate_id references."""
    result = session.execute(
        text("""
            SELECT rg.id, rg.bench_candidate_id
            FROM reverse_geocodes rg
            LEFT JOIN bench_candidates bc ON rg.bench_candidate_id = bc.id
            WHERE bc.id IS NULL
        """)
    ).fetchall()

    orphaned = []
    for row in result:
        rg = session.get(ReverseGeocode, row[0])
        if rg:
            orphaned.append(rg)
    return orphaned


def find_orphaned_processed_benches(session: Session) -> list[ProcessedBench]:
    """Find processed benches with invalid bench_candidate_id references."""
    result = session.execute(
        text("""
            SELECT pb.id, pb.bench_candidate_id
            FROM processed_benches pb
            LEFT JOIN bench_candidates bc ON pb.bench_candidate_id = bc.id
            WHERE bc.id IS NULL
        """)
    ).fetchall()

    orphaned = []
    for row in result:
        pb = session.get(ProcessedBench, row[0])
        if pb:
            orphaned.append(pb)
    return orphaned


def find_orphaned_bench_reports(session: Session) -> list[BenchReport]:
    """Find bench reports with invalid bench_candidate_id or image_id references."""
    result = session.execute(
        text("""
            SELECT br.id, br.bench_candidate_id, br.image_id
            FROM bench_reports br
            LEFT JOIN bench_candidates bc ON br.bench_candidate_id = bc.id
            LEFT JOIN images i ON br.image_id = i.id
            WHERE bc.id IS NULL
               OR (br.image_id IS NOT NULL AND i.id IS NULL)
        """)
    ).fetchall()

    orphaned = []
    for row in result:
        br = session.get(BenchReport, row[0])
        if br:
            orphaned.append(br)
    return orphaned


def find_orphaned_bench_candidates(session: Session) -> list[BenchCandidate]:
    """Find bench candidates with invalid search_id references."""
    result = session.execute(
        text("""
            SELECT bc.id, bc.search_id
            FROM bench_candidates bc
            LEFT JOIN searches s ON bc.search_id = s.id
            WHERE s.id IS NULL
        """)
    ).fetchall()

    orphaned = []
    for row in result:
        bc = session.get(BenchCandidate, row[0])
        if bc:
            orphaned.append(bc)
    return orphaned


def find_invalid_processed_bench_references(session: Session) -> dict[str, list]:
    """Find ProcessedBench records with invalid best_image_id or best_detection_id."""
    invalid = defaultdict(list)

    # Check best_image_id
    result = session.execute(
        text("""
            SELECT pb.id, pb.best_image_id
            FROM processed_benches pb
            WHERE pb.best_image_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM images i WHERE i.id = pb.best_image_id
            )
        """)
    ).fetchall()

    for row in result:
        pb = session.get(ProcessedBench, row[0])
        if pb:
            invalid["invalid_best_image_id"].append(pb)

    # Check best_detection_id
    result = session.execute(
        text("""
            SELECT pb.id, pb.best_detection_id
            FROM processed_benches pb
            WHERE pb.best_detection_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM detections d WHERE d.id = pb.best_detection_id
            )
        """)
    ).fetchall()

    for row in result:
        pb = session.get(ProcessedBench, row[0])
        if pb:
            invalid["invalid_best_detection_id"].append(pb)

    return invalid


def scan_all_violations(session: Session) -> dict[str, list]:
    """Scan all FK violations in the database."""
    violations = {}

    logger.info("Scanning for foreign key violations...")

    violations["orphaned_images"] = find_orphaned_images(session)
    violations["orphaned_detections"] = find_orphaned_detections(session)
    violations["orphaned_detection_items"] = find_orphaned_detection_items(session)
    violations["orphaned_reverse_geocodes"] = find_orphaned_reverse_geocodes(session)
    violations["orphaned_processed_benches"] = find_orphaned_processed_benches(session)
    violations["orphaned_bench_reports"] = find_orphaned_bench_reports(session)
    violations["orphaned_bench_candidates"] = find_orphaned_bench_candidates(session)

    invalid_refs = find_invalid_processed_bench_references(session)
    violations.update(invalid_refs)

    return violations


def print_violations(violations: dict[str, list]) -> None:
    """Print a summary of all FK violations found."""
    total = sum(len(items) for items in violations.values())

    if total == 0:
        logger.info("✅ No foreign key violations found!")
        return

    logger.warning(f"⚠️  Found {total} foreign key violation(s):\n")

    for violation_type, items in violations.items():
        if items:
            logger.warning(f"  {violation_type}: {len(items)} record(s)")
            # Show first few IDs as examples
            ids = [getattr(item, "id", None) for item in items[:10]]
            logger.warning(f"    Example IDs: {ids}")


def fix_violations(
    session: Session, violations: dict[str, list], dry_run: bool = False
) -> None:
    """Fix FK violations by deleting orphaned records."""
    total_deleted = 0

    for violation_type, items in violations.items():
        if not items:
            continue

        logger.info(f"\nProcessing {violation_type}: {len(items)} record(s)")

        for item in items:
            try:
                item_id = getattr(item, "id", None)
                logger.info(f"  Deleting {violation_type} with id={item_id}")

                if not dry_run:
                    session.delete(item)
                    total_deleted += 1
            except Exception:
                logger.exception(f"  Error deleting {violation_type} id={item_id}")

    if not dry_run:
        logger.info(f"\nCommitting {total_deleted} deletion(s)...")
        session.commit()
        logger.info("✅ All violations fixed!")
    else:
        logger.info(f"\n[dry-run] Would delete {total_deleted} record(s)")


def main():
    parser = argparse.ArgumentParser(
        description="Find and clean up foreign key violations in the database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show violations without making changes",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Fix violations by deleting orphaned records",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.fix:
        logger.info(
            "Running in scan-only mode. Use --fix to apply changes or --dry-run to preview."
        )

    # Initialize database
    db = BenchDatabase()
    session = db.get_session()

    try:
        # Scan for violations
        violations = scan_all_violations(session)

        # Print summary
        print_violations(violations)

        # Fix if requested
        if args.fix:
            if args.dry_run:
                logger.info("\n[dry-run mode] Would fix violations...")
                fix_violations(session, violations, dry_run=True)
            else:
                logger.info("\nFixing violations...")
                fix_violations(session, violations, dry_run=False)
        elif args.dry_run:
            logger.info("\n[dry-run mode] Use --fix to apply changes")

    except Exception:
        logger.exception("Error scanning/fixing violations")
        session.rollback()
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
