"""
Backfill script to populate detected_benches from existing images and detections.

Strategy:
- For each bench, consider successful images.
- For each image, consider detections with has_bench = True and take the maximum max_confidence.
- Pick the image with the highest confidence and upsert into detected_benches.

Run:
  uv run python -m tools.backfill_detected_benches --missing-only
"""

import argparse
import logging

from bench_finder.models.unified_models import Bench, DetectedBench, Detection, Image
from bench_finder.services.database import BenchDatabase


logger = logging.getLogger(__name__)


def backfill(missing_only: bool = True, limit: int | None = None) -> int:
    db = BenchDatabase()
    updated = 0

    with db.get_session() as session:
        # Select benches, optionally only those without a detected_benches row
        query = session.query(Bench)
        if missing_only:
            query = query.outerjoin(
                DetectedBench, DetectedBench.bench_id == Bench.id
            ).filter(DetectedBench.id.is_(None))
        if limit:
            query = query.limit(limit)

        benches = query.all()
        logger.info(f"Found {len(benches)} benches to backfill")

        for bench in benches:
            # Successful images for bench
            images = (
                session.query(Image)
                .filter(Image.bench_id == bench.id, Image.capture_success)
                .all()
            )
            if not images:
                continue

            best_image_id: int | None = None
            best_confidence: float = 0.0

            for img in images:
                # For each image pick the highest confidence detection that has a bench
                det = (
                    session.query(Detection)
                    .filter(
                        Detection.image_id == img.id,
                        Detection.has_bench,
                    )
                    .order_by(Detection.max_confidence.desc())
                    .first()
                )
                if det and det.max_confidence >= best_confidence:
                    best_confidence = det.max_confidence
                    best_image_id = img.id

            if best_image_id is not None:
                db.upsert_detected_bench(
                    bench_id=bench.id,
                    image_id=best_image_id,
                    confidence=best_confidence,
                )
                updated += 1

    return updated


def main():
    parser = argparse.ArgumentParser(description="Backfill detected_benches table")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all benches, not just missing detected_benches",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit benches processed"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    count = backfill(missing_only=not args.all, limit=args.limit)
    print(f"Backfilled {count} benches")


if __name__ == "__main__":
    main()
