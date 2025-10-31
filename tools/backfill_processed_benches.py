"""
Backfill script to populate processed_benches table from BenchCandidate records.

This script creates one ProcessedBench record per BenchCandidate:
- If a bench was detected (has_bench=True), creates with detection_status="detected"
  and sets best_image_id and best_detection_id to the best detection
- If no bench was detected, creates with detection_status="no_bench"

Strategy:
- For each BenchCandidate, find all successful images
- For each image, find detections with has_bench=True
- Pick the image/detection pair with highest max_confidence
- If found, create ProcessedBench with status="detected"
- Otherwise, create ProcessedBench with status="no_bench"

Run:
  uv run python -m tools.backfill_processed_benches --missing-only
  uv run python -m tools.backfill_processed_benches --all --limit 100
"""

import argparse
import logging

from sqlalchemy.orm import joinedload

from bench_finder.models.unified_models import (
    BenchCandidate,
    Image,
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

    with db.get_session() as session:
        # Select bench candidates, optionally only those without a processed_bench row
        query = session.query(BenchCandidate)
        if missing_only:
            query = query.outerjoin(
                ProcessedBench, ProcessedBench.bench_candidate_id == BenchCandidate.id
            ).filter(ProcessedBench.id.is_(None))
        if limit:
            query = query.limit(limit)

        candidates = query.all()
        logger.info(f"Found {len(candidates)} bench candidates to process")

        for candidate in candidates:
            # Get successful images for this candidate
            images = (
                session.query(Image)
                .filter(
                    Image.bench_candidate_id == candidate.id,
                    Image.capture_success,
                )
                .options(joinedload(Image.detections))
                .all()
            )

            if not images:
                # No images - create NoBenchDetected record
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

            # Find the best detection across all images
            best_image_id: int | None = None
            best_detection_id: int | None = None
            best_confidence: float = 0.0

            for img in images:
                # Find detections with has_bench=True for this image
                detections = [
                    det
                    for det in img.detections
                    if det.has_bench and det.max_confidence > best_confidence
                ]

                for det in detections:
                    if det.max_confidence > best_confidence:
                        best_confidence = det.max_confidence
                        best_image_id = img.id
                        best_detection_id = det.id

            # Create ProcessedBench record
            if best_image_id is not None and best_detection_id is not None:
                # Bench detected
                processed_bench = ProcessedBench(
                    bench_candidate_id=candidate.id,
                    detection_status="detected",
                    best_image_id=best_image_id,
                    best_detection_id=best_detection_id,
                )
                logger.debug(
                    f"Candidate {candidate.id}: Bench detected (confidence={best_confidence:.3f}), "
                    f"creating 'detected' record with image={best_image_id}, detection={best_detection_id}"
                )
            else:
                # No bench detected
                processed_bench = ProcessedBench(
                    bench_candidate_id=candidate.id,
                    detection_status="no_bench",
                    best_image_id=None,
                    best_detection_id=None,
                )
                logger.debug(
                    f"Candidate {candidate.id}: No bench detected, creating 'no_bench' record"
                )

            session.add(processed_bench)
            created += 1

            # Commit periodically to avoid long transactions
            if created % 100 == 0:
                session.commit()
                logger.info(f"Processed {created} candidates so far...")

        # Final commit
        session.commit()
        logger.info(f"Created {created} ProcessedBench records")

    return created


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
