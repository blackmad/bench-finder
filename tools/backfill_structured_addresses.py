#!/usr/bin/env python3
"""
Backfill structured address components for existing reverse geocodes.

This script:
1. Finds all reverse geocodes that have formatted_address but missing structured components
2. Parses the formatted_address using a heuristic (split on commas) to extract components
3. Updates the database with structured components

Usage:
    python tools/backfill_structured_addresses.py [--db-path PATH]
"""

import argparse
import logging
import os
import re
import sqlite3
import sys


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_formatted_address(formatted_address: str) -> dict[str, str | None]:
    """
    Parse a formatted address into structured components using heuristics.

    Common Google format: "123 Main St, City, State ZIP, Country"

    Args:
        formatted_address: Formatted address string

    Returns:
        Dictionary with structured components: street_number, street_name, city, state, postal_code, country
    """
    if not formatted_address:
        return {
            "street_number": None,
            "street_name": None,
            "city": None,
            "state": None,
            "postal_code": None,
            "country": None,
        }

    # Split by commas
    parts = [part.strip() for part in formatted_address.split(",")]

    structured = {
        "street_number": None,
        "street_name": None,
        "city": None,
        "state": None,
        "postal_code": None,
        "country": None,
    }

    if len(parts) == 0:
        return structured

    # First part is usually street address (e.g., "123 Main St")
    if len(parts) > 0:
        street_part = parts[0]
        # Try to extract street number and name
        street_match = re.match(r"^(\d+)\s+(.+)$", street_part)
        if street_match:
            structured["street_number"] = street_match.group(1)
            structured["street_name"] = street_match.group(2)
        else:
            # No number, might be just street name
            structured["street_name"] = street_part

    # Second part is usually city
    if len(parts) > 1:
        structured["city"] = parts[1]

    # Third part might be state and postal code (e.g., "CA 94102" or "California 94102")
    if len(parts) > 2:
        state_part = parts[2]
        # Try to extract state and postal code
        # Pattern: "CA 94102" or "California 94102"
        state_zip_match = re.match(
            r"^([A-Z]{2}|[A-Za-z\s]+?)\s+(\d{5}(?:-\d{4})?)$", state_part
        )
        if state_zip_match:
            structured["state"] = state_zip_match.group(1).strip()
            structured["postal_code"] = state_zip_match.group(2)
        # Might be just state, or might have zip later
        # Check if it looks like a state code
        elif re.match(r"^[A-Z]{2}$", state_part.strip()):
            structured["state"] = state_part.strip()
        else:
            structured["state"] = state_part

    # Fourth part is usually country
    if len(parts) > 3:
        structured["country"] = parts[3]

    # If we have a state with a space, try to extract postal code from it
    if structured["state"] and " " in structured["state"]:
        state_parts = structured["state"].split()
        if len(state_parts) == 2 and re.match(r"^\d{5}(?:-\d{4})?$", state_parts[1]):
            # Last part might be postal code
            structured["state"] = state_parts[0]
            structured["postal_code"] = state_parts[1]

    return structured


def backfill_structured_addresses(db_path: str) -> dict[str, int]:
    """
    Backfill structured address components for existing reverse geocodes.

    Args:
        db_path: Path to SQLite database

    Returns:
        Dictionary with statistics: {'processed': int, 'updated': int, 'failed': int}
    """
    if not os.path.exists(db_path):
        logger.error(f"Database not found at {db_path}")
        return {"processed": 0, "updated": 0, "failed": 0}

    stats = {"processed": 0, "updated": 0, "failed": 0}

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Find all reverse geocodes that need structured components
        # Get rows where formatted_address exists but city is NULL
        cursor.execute("""
            SELECT id, bench_candidate_id, formatted_address,
                   street_number, street_name, city, state, postal_code, country
            FROM reverse_geocodes
            WHERE formatted_address IS NOT NULL
            AND (city IS NULL OR street_name IS NULL)
        """)

        rows = cursor.fetchall()
        total = len(rows)

        if total == 0:
            logger.info("No reverse geocodes need structured address parsing")
            conn.close()
            return stats

        logger.info(f"Found {total} reverse geocodes to parse")

        for row in rows:
            stats["processed"] += 1
            row_id = row["id"]
            formatted_address = row["formatted_address"]

            try:
                # Parse the formatted address
                structured = parse_formatted_address(formatted_address)

                # Only update if we found at least some components
                if any(
                    [structured["city"], structured["state"], structured["street_name"]]
                ):
                    # Update the row
                    cursor.execute(
                        """
                        UPDATE reverse_geocodes
                        SET street_number = ?,
                            street_name = ?,
                            city = ?,
                            state = ?,
                            postal_code = ?,
                            country = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """,
                        (
                            structured["street_number"],
                            structured["street_name"],
                            structured["city"],
                            structured["state"],
                            structured["postal_code"],
                            structured["country"],
                            row_id,
                        ),
                    )

                    stats["updated"] += 1
                    if stats["updated"] % 100 == 0:
                        conn.commit()
                        logger.info(
                            f"Processed {stats['processed']}/{total}, updated {stats['updated']}"
                        )
                else:
                    logger.debug(
                        f"Could not parse structured components for ID {row_id}: {formatted_address}"
                    )

            except Exception:
                logger.exception(f"Error processing reverse geocode ID {row_id}")
                stats["failed"] += 1

        conn.commit()
        conn.close()

        logger.info(
            f"\nBackfill complete:\n"
            f"  Processed: {stats['processed']}\n"
            f"  Updated: {stats['updated']}\n"
            f"  Failed: {stats['failed']}"
        )

        return stats

    except Exception:
        logger.exception("Error during backfill")
        return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill structured address components for existing reverse geocodes"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="data/benches.db",
        help="Path to SQLite database file (default: data/benches.db)",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Backfill: Parse structured addresses from formatted addresses")
    logger.info("=" * 60)
    logger.info(f"Database path: {args.db_path}")

    stats = backfill_structured_addresses(args.db_path)

    if stats["failed"] == 0:
        logger.info("✅ Backfill completed successfully")
        sys.exit(0)
    else:
        logger.error(f"❌ Backfill completed with {stats['failed']} failures")
        sys.exit(1)


if __name__ == "__main__":
    main()
