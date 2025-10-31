"""
Migration script to:
1. Migrate images table from bench_id to bench_candidate_id
2. Deduplicate images by filepath (keep one, delete duplicates)
3. Delete duplicate detections associated with deleted images

This script:
- Maps bench_id to bench_candidate_id using provider_id and source matching
- Identifies duplicate images by filepath
- Keeps the image with the lowest ID for each filepath
- Deletes duplicate images and their associated detections
- Adds bench_candidate_id column and removes bench_id column

Run:
  uv run python -m tools.migrate_images_to_bench_candidate_id
"""

import argparse
import logging
import sqlite3

from bench_finder.services.database import BenchDatabase


logger = logging.getLogger(__name__)


def migrate_images():
    """Migrate images table and deduplicate."""
    db = BenchDatabase()
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    try:
        # Step 1: Check if migration already done
        cursor.execute("PRAGMA table_info(images)")
        columns = [row[1] for row in cursor.fetchall()]
        if "bench_candidate_id" in columns and "bench_id" not in columns:
            logger.info(
                "Migration already completed - images table has bench_candidate_id"
            )
            return

        logger.info("Starting images migration...")

        # Step 2: Add bench_candidate_id column if it doesn't exist
        if "bench_candidate_id" not in columns:
            logger.info("Adding bench_candidate_id column...")
            cursor.execute("ALTER TABLE images ADD COLUMN bench_candidate_id INTEGER")
            conn.commit()

        # Step 3: Map bench_id to bench_candidate_id
        logger.info("Mapping bench_id to bench_candidate_id...")
        # Match by provider_id and source (handle case differences)
        cursor.execute("""
            UPDATE images
            SET bench_candidate_id = (
                SELECT bc.id
                FROM bench_candidates bc
                JOIN benches b ON UPPER(b.provider_id) = UPPER(bc.provider_id)
                    AND UPPER(b.source) = UPPER(bc.source)
                WHERE b.id = images.bench_id
                LIMIT 1
            )
            WHERE bench_id IS NOT NULL
        """)
        mapped_count = cursor.rowcount
        logger.info(f"Mapped {mapped_count} images to bench_candidate_id")
        conn.commit()

        # Check for unmapped images
        cursor.execute(
            "SELECT COUNT(*) FROM images WHERE bench_candidate_id IS NULL AND bench_id IS NOT NULL"
        )
        unmapped = cursor.fetchone()[0]
        if unmapped > 0:
            logger.warning(
                f"{unmapped} images could not be mapped to bench_candidate_id"
            )

        # Step 4: Find duplicate images by filepath
        logger.info("Finding duplicate images by filepath...")
        cursor.execute("""
            SELECT filepath, COUNT(*) as cnt, GROUP_CONCAT(id) as ids
            FROM images
            WHERE filepath IS NOT NULL
            GROUP BY filepath
            HAVING cnt > 1
        """)
        duplicates = cursor.fetchall()
        logger.info(f"Found {len(duplicates)} duplicate filepaths")

        # Step 5: Delete duplicates (keep the one with lowest ID)
        deleted_images = 0
        deleted_detections = 0

        for _filepath, _count, ids_str in duplicates:
            ids = [int(id_str) for id_str in ids_str.split(",")]
            ids.sort()
            keep_id = ids[0]
            delete_ids = ids[1:]

            # Get bench_candidate_id from one of the duplicates before deletion
            # Check if kept image has bench_candidate_id, if not, try to get from others
            cursor.execute(
                "SELECT bench_candidate_id FROM images WHERE id = ?", (keep_id,)
            )
            result = cursor.fetchone()
            kept_bc_id = result[0] if result else None

            # If kept image doesn't have bench_candidate_id, try to get from duplicates
            if kept_bc_id is None:
                for dup_id in ids[1:]:
                    cursor.execute(
                        "SELECT bench_candidate_id FROM images WHERE id = ?", (dup_id,)
                    )
                    dup_result = cursor.fetchone()
                    if dup_result and dup_result[0] is not None:
                        # Update kept image with bench_candidate_id from duplicate
                        cursor.execute(
                            "UPDATE images SET bench_candidate_id = ? WHERE id = ?",
                            (dup_result[0], keep_id),
                        )
                        kept_bc_id = dup_result[0]
                        break

            # Delete detections for duplicate images
            if delete_ids:
                placeholders = ",".join("?" * len(delete_ids))
                cursor.execute(
                    f"SELECT id FROM detections WHERE image_id IN ({placeholders})",
                    delete_ids,
                )
                detection_ids = [row[0] for row in cursor.fetchall()]

                if detection_ids:
                    # Delete detection_items first (foreign key constraint)
                    detection_placeholders = ",".join("?" * len(detection_ids))
                    cursor.execute(
                        f"DELETE FROM detection_items WHERE detection_id IN ({detection_placeholders})",
                        detection_ids,
                    )

                    # Delete detections
                    cursor.execute(
                        f"DELETE FROM detections WHERE id IN ({detection_placeholders})",
                        detection_ids,
                    )
                    deleted_detections += cursor.rowcount

            # Delete duplicate images
            placeholders = ",".join("?" * len(delete_ids))
            cursor.execute(
                f"DELETE FROM images WHERE id IN ({placeholders})", delete_ids
            )
            deleted_images += len(delete_ids)

            if (deleted_images + deleted_detections) % 100 == 0:
                conn.commit()
                logger.debug(
                    f"Deleted {deleted_images} duplicate images, {deleted_detections} detections so far..."
                )

        conn.commit()
        logger.info(
            f"Deleted {deleted_images} duplicate images and {deleted_detections} associated detections"
        )

        # Step 6: For any remaining images without bench_candidate_id, try to match by filepath pattern
        logger.info("Attempting to match remaining unmapped images by filepath...")
        cursor.execute("""
            UPDATE images
            SET bench_candidate_id = (
                SELECT bc.id
                FROM bench_candidates bc
                WHERE images.filepath LIKE '%' || bc.provider_id || '%'
                LIMIT 1
            )
            WHERE bench_candidate_id IS NULL
        """)
        matched_by_path = cursor.rowcount
        logger.info(f"Matched {matched_by_path} additional images by filepath pattern")
        conn.commit()

        # Step 7: Remove bench_id column (SQLite doesn't support DROP COLUMN directly)
        # We'll need to recreate the table
        logger.info("Removing bench_id column...")

        # Create new table without bench_id
        cursor.execute("""
            CREATE TABLE images_new (
                id INTEGER PRIMARY KEY,
                bench_candidate_id INTEGER NOT NULL,
                heading INTEGER NOT NULL,
                filepath TEXT,
                filename TEXT,
                file_size INTEGER,
                capture_success INTEGER NOT NULL,
                capture_error TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (bench_candidate_id) REFERENCES bench_candidates(id)
            )
        """)

        # Copy data
        cursor.execute("""
            INSERT INTO images_new
            (id, bench_candidate_id, heading, filepath, filename, file_size, capture_success, capture_error, created_at)
            SELECT id, bench_candidate_id, heading, filepath, filename, file_size, capture_success, capture_error, created_at
            FROM images
            WHERE bench_candidate_id IS NOT NULL
        """)
        copied_count = cursor.rowcount
        logger.info(f"Copied {copied_count} images to new table")

        # Drop old table and rename new one
        cursor.execute("DROP TABLE images")
        cursor.execute("ALTER TABLE images_new RENAME TO images")

        # Recreate indexes
        cursor.execute(
            "CREATE INDEX idx_images_bench_candidate_id ON images(bench_candidate_id)"
        )
        cursor.execute(
            "CREATE INDEX idx_images_capture_success ON images(capture_success)"
        )

        conn.commit()
        logger.info("✅ Migration completed successfully!")

        # Final statistics
        cursor.execute("SELECT COUNT(*) FROM images")
        final_count = cursor.fetchone()[0]
        logger.info(f"Final image count: {final_count}")

    except Exception:
        conn.rollback()
        logger.exception("Migration failed")
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate images table from bench_id to bench_candidate_id and deduplicate"
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

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")
        # TODO: Implement dry-run logic
        return

    migrate_images()


if __name__ == "__main__":
    main()
