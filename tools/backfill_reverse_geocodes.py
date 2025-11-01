#!/usr/bin/env python3
"""
Backfill reverse geocodes for existing bench candidates.

This script:
1. Finds all bench candidates that don't have reverse geocodes
2. Calls the reverse geocoding API for each candidate
3. Stores the results in the database

Usage:
    python tools/backfill_reverse_geocodes.py [--limit LIMIT] [--delay DELAY]

Options:
    --limit LIMIT: Maximum number of candidates to process (default: None, process all)
    --delay DELAY: Delay in seconds between API calls to respect rate limits (default: 0.1)
"""

import argparse
import logging
import sys
import time
from pathlib import Path


# Add parent directory to path to import bench_finder modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from bench_finder.core.geocoder import Geocoder
from bench_finder.services.database import BenchDatabase
from bench_finder.utils import setup_logging


def backfill_reverse_geocodes(
    limit: int | None = None,
    delay: float = 0.1,
    batch_size: int = 100,
) -> dict[str, int]:
    """
    Backfill reverse geocodes for bench candidates that don't have them.

    Args:
        limit: Maximum number of candidates to process (None for all)
        delay: Delay in seconds between API calls (to respect rate limits)
        batch_size: Number of candidates to process in each batch

    Returns:
        Dictionary with statistics: {'processed': int, 'successful': int, 'failed': int, 'skipped': int}
    """
    logger = logging.getLogger(__name__)

    # Initialize components
    database = BenchDatabase()

    try:
        geocoder = Geocoder()
    except ValueError:
        logger.exception("Failed to initialize geocoder")
        logger.exception("Make sure GOOGLE_MAPS_API_KEY is set in your environment")
        return {"processed": 0, "successful": 0, "failed": 0, "skipped": 0}

    # Get candidates without reverse geocodes
    logger.info("Finding bench candidates without reverse geocodes...")
    candidates = database.get_bench_candidates_without_reverse_geocode(limit=limit)
    total_count = len(candidates)

    if total_count == 0:
        logger.info("No candidates found that need reverse geocoding")
        return {"processed": 0, "successful": 0, "failed": 0, "skipped": 0}

    logger.info(f"Found {total_count} candidates to reverse geocode")

    # Statistics
    stats = {"processed": 0, "successful": 0, "failed": 0, "skipped": 0}

    # Process candidates in batches
    for batch_start in range(0, total_count, batch_size):
        batch_end = min(batch_start + batch_size, total_count)
        batch = candidates[batch_start:batch_end]

        logger.info(
            f"Processing batch {batch_start // batch_size + 1} ({batch_start + 1}-{batch_end} of {total_count})"
        )

        for candidate in batch:
            stats["processed"] += 1

            try:
                # Check if reverse geocode already exists (double-check)
                existing = database.get_reverse_geocode(candidate.id or 0)
                if existing:
                    logger.debug(
                        f"Candidate {candidate.id} already has reverse geocode, skipping"
                    )
                    stats["skipped"] += 1
                    continue

                # Reverse geocode (structured)
                structured_address = geocoder.reverse_geocode_structured(
                    candidate.lat, candidate.lng
                )

                if structured_address:
                    # Store in database
                    database.add_or_update_reverse_geocode(
                        bench_candidate_id=candidate.id or 0,
                        formatted_address=structured_address["formatted_address"],
                        street_number=structured_address.get("street_number"),
                        street_name=structured_address.get("street_name"),
                        city=structured_address.get("city"),
                        state=structured_address.get("state"),
                        postal_code=structured_address.get("postal_code"),
                        country=structured_address.get("country"),
                        raw_response=structured_address.get("raw_response"),
                    )
                    stats["successful"] += 1
                    logger.debug(
                        f"Reverse geocoded candidate {candidate.id}: {structured_address.get('city', 'Unknown')}, {structured_address.get('state', 'Unknown')}"
                    )
                else:
                    logger.warning(
                        f"No address found for candidate {candidate.id} at ({candidate.lat}, {candidate.lng})"
                    )
                    stats["failed"] += 1

                # Delay to respect rate limits
                if delay > 0:
                    time.sleep(delay)

            except Exception:
                logger.exception(f"Error processing candidate {candidate.id}")
                stats["failed"] += 1

                # Delay even on error to respect rate limits
                if delay > 0:
                    time.sleep(delay)

        logger.info(
            f"Batch complete: {stats['successful']} successful, {stats['failed']} failed, {stats['skipped']} skipped"
        )

    logger.info(
        f"\nBackfill complete:\n"
        f"  Processed: {stats['processed']}\n"
        f"  Successful: {stats['successful']}\n"
        f"  Failed: {stats['failed']}\n"
        f"  Skipped: {stats['skipped']}"
    )

    return stats


def main() -> None:
    """Main entry point for the backfill script."""
    parser = argparse.ArgumentParser(
        description="Backfill reverse geocodes for existing bench candidates"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of candidates to process (default: None, process all)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.1,
        help="Delay in seconds between API calls to respect rate limits (default: 0.1)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of candidates to process in each batch (default: 100)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(level=args.log_level)
    logger = logging.getLogger(__name__)

    # Run backfill
    try:
        stats = backfill_reverse_geocodes(
            limit=args.limit,
            delay=args.delay,
            batch_size=args.batch_size,
        )

        # Exit with error code if there were failures
        if stats["failed"] > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nBackfill interrupted by user")
        sys.exit(130)
    except Exception:
        logger.exception("Unexpected error during backfill")
        sys.exit(1)


if __name__ == "__main__":
    main()
