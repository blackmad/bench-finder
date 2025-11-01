"""
Migration script to migrate bench_reports table from bench_id to bench_candidate_id.

This script:
- Adds bench_candidate_id column if it doesn't exist
- Maps existing bench_id values to bench_candidate_id via ProcessedBench
- Removes bench_id column if it exists

Run:
  uv run python -m tools.migrate_bench_reports_to_bench_candidate_id
"""

import argparse
import logging
import sqlite3

from bench_finder.services.database import BenchDatabase


logger = logging.getLogger(__name__)


def migrate_bench_reports():
    """Migrate bench_reports table to use bench_candidate_id."""
    db = BenchDatabase()

    # Get database path from engine URL
    if db.db_path:
        db_path = db.db_path
    elif db.db_url and db.db_url.startswith("sqlite:///"):
        # Extract path from sqlite:/// URL
        db_path = db.db_url.replace("sqlite:///", "")
    else:
        # Try to get from engine URL
        engine_url = str(db.engine.url)
        if engine_url.startswith("sqlite:///"):
            db_path = engine_url.replace("sqlite:///", "")
        else:
            raise ValueError(
                f"Cannot migrate: database is not SQLite. URL: {engine_url}"
            )

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Step 1: Check current table schema
        cursor.execute("PRAGMA table_info(bench_reports)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        column_names = list(columns.keys())

        if "bench_candidate_id" in column_names and "bench_id" not in column_names:
            logger.info(
                "Migration already completed - bench_reports table has bench_candidate_id"
            )
            return

        logger.info("Starting bench_reports migration...")

        # Step 2: Add bench_candidate_id column if it doesn't exist
        if "bench_candidate_id" not in column_names:
            logger.info("Adding bench_candidate_id column...")
            cursor.execute(
                "ALTER TABLE bench_reports ADD COLUMN bench_candidate_id INTEGER"
            )
            conn.commit()

        # Step 3: Map bench_id to bench_candidate_id via ProcessedBench
        if "bench_id" in column_names:
            logger.info("Mapping bench_id to bench_candidate_id via ProcessedBench...")
            # Map via processed_benches table
            cursor.execute("""
                UPDATE bench_reports
                SET bench_candidate_id = (
                    SELECT pb.bench_candidate_id
                    FROM processed_benches pb
                    WHERE pb.id = bench_reports.bench_id
                    LIMIT 1
                )
                WHERE bench_id IS NOT NULL
                AND bench_candidate_id IS NULL
            """)
            mapped_count = cursor.rowcount
            logger.info(f"Mapped {mapped_count} reports to bench_candidate_id")
            conn.commit()

            # Check for unmapped reports
            cursor.execute(
                "SELECT COUNT(*) FROM bench_reports WHERE bench_candidate_id IS NULL AND bench_id IS NOT NULL"
            )
            unmapped = cursor.fetchone()[0]
            if unmapped > 0:
                logger.warning(
                    f"{unmapped} reports could not be mapped to bench_candidate_id"
                )

        # Step 4: Check if we need to handle NULL values
        cursor.execute(
            "SELECT COUNT(*) FROM bench_reports WHERE bench_candidate_id IS NULL"
        )
        null_count = cursor.fetchone()[0]
        if null_count > 0:
            logger.warning(
                f"{null_count} reports have NULL bench_candidate_id - these may need manual review"
            )

        # Step 5: Remove bench_id column if it exists (SQLite doesn't support DROP COLUMN directly)
        if "bench_id" in column_names:
            logger.info("Removing bench_id column...")

            # Get all column definitions except bench_id
            cursor.execute("PRAGMA table_info(bench_reports)")
            all_columns = cursor.fetchall()
            keep_columns = [col for col in all_columns if col[1] != "bench_id"]

            # Create new table without bench_id
            # Build column definitions
            column_defs = []
            for col in keep_columns:
                col_name = col[1]
                col_type = col[2]
                not_null = " NOT NULL" if col[3] else ""
                default_val = f" DEFAULT {col[4]}" if col[4] is not None else ""
                primary_key = " PRIMARY KEY" if col[5] else ""
                column_defs.append(
                    f"{col_name} {col_type}{not_null}{default_val}{primary_key}"
                )

            # Get column names for INSERT
            keep_column_names = [col[1] for col in keep_columns]

            # Create new table
            create_sql = f"""
                CREATE TABLE bench_reports_new (
                    {', '.join(column_defs)},
                    FOREIGN KEY (bench_candidate_id) REFERENCES bench_candidates(id)
                )
            """
            cursor.execute(create_sql)

            # Copy data (excluding bench_id)
            column_list = ", ".join(keep_column_names)
            cursor.execute(f"""
                INSERT INTO bench_reports_new ({column_list})
                SELECT {column_list}
                FROM bench_reports
            """)
            copied_count = cursor.rowcount
            logger.info(f"Copied {copied_count} reports to new table")

            # Drop old table and rename new one
            cursor.execute("DROP TABLE bench_reports")
            cursor.execute("ALTER TABLE bench_reports_new RENAME TO bench_reports")

            # Recreate any indexes if needed
            # Note: We don't track indexes here, but you may need to recreate them
            logger.info("Recreated bench_reports table without bench_id column")

        conn.commit()
        logger.info("✅ Migration completed successfully!")

        # Final statistics
        cursor.execute("SELECT COUNT(*) FROM bench_reports")
        final_count = cursor.fetchone()[0]
        logger.info(f"Final report count: {final_count}")

        cursor.execute(
            "SELECT COUNT(*) FROM bench_reports WHERE bench_candidate_id IS NOT NULL"
        )
        with_bc_id = cursor.fetchone()[0]
        logger.info(f"Reports with bench_candidate_id: {with_bc_id}")

    except Exception:
        conn.rollback()
        logger.exception("Migration failed")
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate bench_reports table from bench_id to bench_candidate_id"
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

    migrate_bench_reports()


if __name__ == "__main__":
    main()
