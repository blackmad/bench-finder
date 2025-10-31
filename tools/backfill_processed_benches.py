"""
Backfill script to populate processed_benches table from BenchCandidate records.

This script creates one ProcessedBench record per BenchCandidate:
- If a bench was detected (has_bench=True), creates with detection_status="detected"
  and sets best_image_id and best_detection_id to the best detection
- If no bench was detected, creates with detection_status="no_bench"

Strategy:
- For each BenchCandidate, find all successful images
- For each image, find detections that either:
  - have has_bench=True, OR
  - have detection items (bounding boxes) indicating a bench was detected
- Pick the image/detection pair with highest max_confidence
- If found, create ProcessedBench with status="detected"
- Otherwise, create ProcessedBench with status="no_bench"

Run:
  uv run python -m tools.backfill_processed_benches --missing-only
  uv run python -m tools.backfill_processed_benches --all --limit 100
"""

import argparse
import logging

from bench_finder.models.unified_models import (
    BenchCandidate,
    ProcessedBench,
)
from bench_finder.services.database import BenchDatabase


logger = logging.getLogger(__name__)


def backfill(missing_only: bool = True, limit: int | None = None) -> int:
    """
    Backfill ProcessedBench records from BenchCandidate data.

    Args:
        missing_only: If True, only process candidates without ProcessedBench records
        limit: Optional limit on number of candidates to process

    Returns:
        Number of ProcessedBench records created
    """
    db = BenchDatabase()
    created = 0
    updated = 0

    with db.get_session() as session:
        # Select bench candidates, optionally only those without a processed_bench row
        # Use raw SQL query to avoid enum conversion issues with old data
        from sqlalchemy import text

        if missing_only:
            sql = text("""
                SELECT bc.* FROM bench_candidates bc
                LEFT JOIN processed_benches pb ON pb.bench_candidate_id = bc.id
                WHERE pb.id IS NULL
            """)
            if limit:
                sql = text(f"{str(sql).rstrip(';')} LIMIT {limit}")
        else:
            sql = text("SELECT * FROM bench_candidates")
            if limit:
                sql = text(f"{str(sql).rstrip(';')} LIMIT {limit}")

        # Execute raw query and convert results
        result = session.execute(sql)
        rows = result.fetchall()

        # Convert rows to BenchCandidate objects, handling enum conversion
        candidates = []
        for row in rows:
            row_dict = dict(row._mapping)
            # Convert source to uppercase if it's a string
            if isinstance(row_dict.get("source"), str):
                row_dict["source"] = row_dict["source"].upper()
            candidate = BenchCandidate(**row_dict)
            candidates.append(candidate)
        logger.info(f"Found {len(candidates)} bench candidates to process")

        # Check actual database schema to see which column exists
        from sqlalchemy import inspect as sql_inspect

        engine = session.bind
        inspector = sql_inspect(engine)
        image_columns = [col["name"] for col in inspector.get_columns("images")]
        use_bench_candidate_id = "bench_candidate_id" in image_columns
        use_bench_id = "bench_id" in image_columns

        if not use_bench_candidate_id and not use_bench_id:
            logger.error(
                "Neither bench_id nor bench_candidate_id found in images table"
            )
            return 0

        for candidate in candidates:
            # Get successful images for this candidate using raw SQL to handle schema differences
            if use_bench_candidate_id:
                image_col = "bench_candidate_id"
            else:
                image_col = "bench_id"
                # In old schema, bench_id may not match candidate.id
                # We'll need to find benches that correspond to this candidate
                # This is a limitation - proper migration needed
                logger.debug(
                    f"Using old schema with bench_id for candidate {candidate.id}"
                )

            # Use raw SQL to query images
            images_sql = text(f"""
                SELECT i.* FROM images i
                WHERE i.{image_col} = :candidate_id
                AND i.capture_success = 1
            """)
            image_rows = session.execute(
                images_sql, {"candidate_id": candidate.id}
            ).fetchall()

            # Check if ProcessedBench already exists for this candidate
            from sqlalchemy import select

            existing_processed_bench = session.exec(
                select(ProcessedBench).where(
                    ProcessedBench.bench_candidate_id == candidate.id
                )
            ).first()

            if not image_rows:
                # No images - create or update to NoBenchDetected record
                if existing_processed_bench:
                    existing_processed_bench.detection_status = "no_bench"
                    existing_processed_bench.best_image_id = None
                    existing_processed_bench.best_detection_id = None
                    updated += 1
                    logger.debug(
                        f"Candidate {candidate.id}: No images, updating to 'no_bench' record"
                    )
                else:
                    processed_bench = ProcessedBench(
                        bench_candidate_id=candidate.id,
                        detection_status="no_bench",
                        best_image_id=None,
                        best_detection_id=None,
                    )
                    session.add(processed_bench)
                    created += 1
                    logger.debug(
                        f"Candidate {candidate.id}: No images, creating 'no_bench' record"
                    )
                continue

            # Get detections for each image
            best_image_id: int | None = None
            best_detection_id: int | None = None
            best_confidence: float = 0.0

            for img_row in image_rows:
                img_dict = dict(img_row._mapping)
                img_id = img_dict["id"]

                # Query detections for this image
                # Check for detections that either:
                # 1. Have has_bench = 1, OR
                # 2. Have detection items (bounding boxes) indicating a bench was detected
                detections_sql = text("""
                    SELECT DISTINCT d.* FROM detections d
                    LEFT JOIN detection_items di ON di.detection_id = d.id
                    WHERE d.image_id = :image_id
                    AND (
                        d.has_bench = 1
                        OR (
                            di.id IS NOT NULL
                            AND di.bbox IS NOT NULL
                            AND (di.class_name = 'bench' OR di.class_name IS NULL)
                        )
                    )
                    ORDER BY d.max_confidence DESC
                """)
                detection_rows = session.execute(
                    detections_sql, {"image_id": img_id}
                ).fetchall()

                for det_row in detection_rows:
                    det_dict = dict(det_row._mapping)
                    confidence = det_dict.get("max_confidence", 0.0)
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_image_id = img_id
                        best_detection_id = det_dict["id"]

            # Create or update ProcessedBench record
            if best_image_id is not None and best_detection_id is not None:
                # Bench detected
                if existing_processed_bench:
                    existing_processed_bench.detection_status = "detected"
                    existing_processed_bench.best_image_id = best_image_id
                    existing_processed_bench.best_detection_id = best_detection_id
                    updated += 1
                    logger.debug(
                        f"Candidate {candidate.id}: Bench detected (confidence={best_confidence:.3f}), "
                        f"updating 'detected' record with image={best_image_id}, detection={best_detection_id}"
                    )
                else:
                    processed_bench = ProcessedBench(
                        bench_candidate_id=candidate.id,
                        detection_status="detected",
                        best_image_id=best_image_id,
                        best_detection_id=best_detection_id,
                    )
                    session.add(processed_bench)
                    created += 1
                    logger.debug(
                        f"Candidate {candidate.id}: Bench detected (confidence={best_confidence:.3f}), "
                        f"creating 'detected' record with image={best_image_id}, detection={best_detection_id}"
                    )
            # No bench detected
            elif existing_processed_bench:
                existing_processed_bench.detection_status = "no_bench"
                existing_processed_bench.best_image_id = None
                existing_processed_bench.best_detection_id = None
                updated += 1
                logger.debug(
                    f"Candidate {candidate.id}: No bench detected, updating to 'no_bench' record"
                )
            else:
                processed_bench = ProcessedBench(
                    bench_candidate_id=candidate.id,
                    detection_status="no_bench",
                    best_image_id=None,
                    best_detection_id=None,
                )
                session.add(processed_bench)
                created += 1
                logger.debug(
                    f"Candidate {candidate.id}: No bench detected, creating 'no_bench' record"
                )

            # Commit periodically to avoid long transactions
            if (created + updated) % 100 == 0:
                session.commit()
                logger.info(
                    f"Processed {created + updated} candidates so far... ({created} created, {updated} updated)"
                )

        # Final commit
        session.commit()
        logger.info(
            f"Completed: {created} ProcessedBench records created, {updated} ProcessedBench records updated"
        )

    return created + updated


def main():
    parser = argparse.ArgumentParser(
        description="Backfill processed_benches table from BenchCandidate records"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all candidates, not just missing processed_benches",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit candidates processed (useful for testing)",
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

    count = backfill(missing_only=not args.all, limit=args.limit)
    print(f"✅ Backfilled {count} ProcessedBench records")


if __name__ == "__main__":
    main()
