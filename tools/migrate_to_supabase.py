#!/usr/bin/env python3
"""
Migration script to copy data from SQLite to Supabase PostgreSQL database.

This script exports all data from the local SQLite database and imports it
into a Supabase PostgreSQL database, maintaining all relationships and data integrity.

Usage:
    python tools/migrate_to_supabase.py \\
        --sqlite-path data/benches.db \\
        --supabase-url postgresql://user:pass@host/db \\
        [--dry-run]
"""

import argparse
import logging
import sys
from pathlib import Path


# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import inspect  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from bench_finder.models.unified_models import (  # noqa: E402
    BenchCandidate,
    Detection,
    DetectionItem,
    Image,
    MissingBenchReport,
    ProcessedBench,
    Search,
    init_database,
)
from bench_finder.services.database import BenchDatabase  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_table_names(engine):
    """Get list of table names from database."""
    inspector = inspect(engine)
    return inspector.get_table_names()


def migrate_table(
    source_session: Session,
    target_session: Session,
    model_class,
    table_name: str,
    batch_size: int = 100,
    dry_run: bool = False,
) -> int:
    """
    Migrate data from source to target database for a specific table.

    Args:
        source_session: Source database session (SQLite)
        target_session: Target database session (Supabase)
        model_class: SQLModel class for the table
        table_name: Name of the table
        batch_size: Number of records to process per batch
        dry_run: If True, only count records without migrating

    Returns:
        Number of records migrated
    """
    logger.info(f"Starting migration for table: {table_name}")

    # Get all records from source
    source_records = source_session.query(model_class).all()
    total_count = len(source_records)

    logger.info(f"Found {total_count} records in source table {table_name}")

    if dry_run:
        logger.info(f"[DRY RUN] Would migrate {total_count} records to {table_name}")
        return total_count

    if total_count == 0:
        logger.info(f"No records to migrate for {table_name}")
        return 0

    # Migrate in batches
    migrated_count = 0
    for i in range(0, total_count, batch_size):
        batch = source_records[i : i + batch_size]
        try:
            # Add all records in batch to target
            for record in batch:
                # Convert to dict to avoid SQLAlchemy instance issues
                record_dict = {
                    col.name: getattr(record, col.name)
                    for col in inspect(model_class).mapper.columns
                }
                # Remove None primary key to let database generate it
                if "id" in record_dict and record_dict["id"] is None:
                    record_dict.pop("id")

                target_record = model_class(**record_dict)
                target_session.add(target_record)

            target_session.commit()
            migrated_count += len(batch)
            logger.info(
                f"Migrated batch {i // batch_size + 1}: {migrated_count}/{total_count} records"
            )

        except Exception:
            logger.exception(f"Error migrating batch {i // batch_size + 1}")
            target_session.rollback()
            raise

    logger.info(f"Successfully migrated {migrated_count} records to {table_name}")
    return migrated_count


def migrate_database(
    sqlite_path: str,
    supabase_url: str,
    dry_run: bool = False,
):
    """
    Migrate all data from SQLite to Supabase.

    Args:
        sqlite_path: Path to SQLite database file
        supabase_url: Supabase PostgreSQL connection URL
        dry_run: If True, only validate without migrating
    """
    logger.info("=" * 60)
    logger.info("Database Migration: SQLite -> Supabase")
    logger.info("=" * 60)

    if dry_run:
        logger.info("DRY RUN MODE - No data will be written")

    # Create source database connection (SQLite)
    logger.info(f"Connecting to source database: {sqlite_path}")
    source_db = BenchDatabase(db_path=sqlite_path)
    source_engine = source_db.engine

    # Create target database connection (Supabase)
    logger.info("Connecting to target database (Supabase)...")
    target_engine = init_database(database_url=supabase_url)
    logger.info("Target database tables initialized")

    # Get table names
    source_tables = get_table_names(source_engine)
    target_tables = get_table_names(target_engine)

    logger.info(f"Source tables: {source_tables}")
    logger.info(f"Target tables: {target_tables}")

    # Define migration order (respecting foreign key constraints)
    # Tables with no foreign keys first, then dependent tables
    migration_order = [
        (Search, "searches"),
        (BenchCandidate, "bench_candidates"),
        (Image, "images"),
        (Detection, "detections"),
        (DetectionItem, "detection_items"),
        (ProcessedBench, "processed_benches"),
        (MissingBenchReport, "missing_bench_reports"),
    ]

    # Filter to only tables that exist in source
    migration_order = [
        (model, table) for model, table in migration_order if table in source_tables
    ]

    total_migrated = 0

    try:
        source_session = source_db.get_session()
        target_session = Session(target_engine)

        for model_class, table_name in migration_order:
            try:
                count = migrate_table(
                    source_session,
                    target_session,
                    model_class,
                    table_name,
                    dry_run=dry_run,
                )
                total_migrated += count
            except Exception:
                logger.exception(f"Failed to migrate table {table_name}")
                if not dry_run:
                    raise

        logger.info("=" * 60)
        logger.info(f"Migration complete! Total records migrated: {total_migrated}")
        logger.info("=" * 60)

    except Exception:
        logger.exception("Migration failed")
        raise
    finally:
        source_session.close()
        target_session.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate SQLite database to Supabase PostgreSQL"
    )
    parser.add_argument(
        "--sqlite-path",
        type=str,
        default="data/benches.db",
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--supabase-url",
        type=str,
        required=True,
        help="Supabase PostgreSQL connection URL (postgresql://user:pass@host/db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - validate but don't migrate data",
    )

    args = parser.parse_args()

    # Validate SQLite path exists
    if not Path(args.sqlite_path).exists():
        logger.error(f"SQLite database not found: {args.sqlite_path}")
        sys.exit(1)

    try:
        migrate_database(
            sqlite_path=args.sqlite_path,
            supabase_url=args.supabase_url,
            dry_run=args.dry_run,
        )
    except Exception:
        logger.exception("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
