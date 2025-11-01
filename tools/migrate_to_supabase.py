#!/usr/bin/env python3
"""
Migration script to copy data from SQLite to Supabase PostgreSQL database.

This script exports all data from the local SQLite database and imports it
into a Supabase PostgreSQL database, maintaining all relationships and data integrity.

Usage:
    python tools/migrate_to_supabase.py \\
        [--sqlite-path data/benches.db] \\
        [--supabase-url postgresql://user:pass@host/db] \\
        [--dry-run] \\
        [--clear-tables]

If --supabase-url is not provided, DATABASE_POSTGRES_URL from .env will be used.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


# Load environment variables from .env file
_ = load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import inspect, text  # noqa: E402
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


def clear_tables(
    target_session: Session,
    target_tables: list[str],
    dry_run: bool = False,
):
    """
    Clear all tables in the target database.

    Clears tables in reverse dependency order (tables with foreign keys first)
    to avoid foreign key constraint violations.

    Args:
        target_session: Target database session
        target_tables: List of table names in target database
        dry_run: If True, only log what would be cleared
    """
    logger.info("=" * 60)
    logger.info("Clearing all tables in target database")
    logger.info("=" * 60)

    if dry_run:
        logger.info("[DRY RUN] Would clear all tables")

    # Define clear order (reverse of migration order to respect FK constraints)
    # Tables with foreign keys first, then parent tables
    clear_order = [
        "missing_bench_reports",
        "processed_benches",
        "detection_items",
        "detections",
        "bench_reports",  # May reference bench_candidates and images
        "reverse_geocodes",  # May reference bench_candidates
        "images",
        "bench_candidates",
        "searches",
    ]

    # Filter to only tables that exist in target
    clear_order = [table for table in clear_order if table in target_tables]

    # Add any remaining tables that weren't in the clear_order
    remaining_tables = [t for t in target_tables if t not in clear_order]
    clear_order.extend(remaining_tables)

    total_cleared = 0

    for table_name in clear_order:
        try:
            if dry_run:
                # Count records in dry-run mode
                result = target_session.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                )
                count = result.scalar()
                if count is not None:
                    logger.info(
                        f"[DRY RUN] Would clear {count} records from {table_name}"
                    )
                    total_cleared += count or 0
            else:
                # Get count before deletion for logging
                count_result = target_session.execute(
                    text(f"SELECT COUNT(*) FROM {table_name}")
                )
                count_before = count_result.scalar() or 0

                # Delete all records
                _ = target_session.execute(text(f"DELETE FROM {table_name}"))
                target_session.commit()
                logger.info(f"Cleared {count_before} records from {table_name}")
                total_cleared += count_before
        except Exception:
            logger.exception(f"Error clearing table {table_name}")
            if not dry_run:
                target_session.rollback()
                raise

    logger.info("=" * 60)
    if dry_run:
        logger.info(f"[DRY RUN] Would clear {total_cleared} total records")
    else:
        logger.info(f"Successfully cleared {total_cleared} total records")
    logger.info("=" * 60)


def migrate_database(
    sqlite_path: str,
    supabase_url: str,
    dry_run: bool = False,
    clear_tables_first: bool = False,
):
    """
    Migrate all data from SQLite to Supabase.

    Args:
        sqlite_path: Path to SQLite database file
        supabase_url: Supabase PostgreSQL connection URL
        dry_run: If True, only validate without migrating
        clear_tables_first: If True, clear all tables in target before migrating
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
    source_session = None
    target_session = None

    try:
        source_session = source_db.get_session()
        target_session = Session(target_engine)

        # Clear tables if requested
        if clear_tables_first:
            clear_tables(target_session, target_tables, dry_run=dry_run)

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
        if source_session is not None:
            source_session.close()
        if target_session is not None:
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
        default=None,
        help=(
            "Supabase PostgreSQL connection URL (postgresql://user:pass@host/db). "
            "If not provided, DATABASE_POSTGRES_URL from .env will be used."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - validate but don't migrate data",
    )
    parser.add_argument(
        "--clear-tables",
        action="store_true",
        help="Clear all tables in target database before migrating",
    )

    args = parser.parse_args()

    # Get Supabase URL from argument or environment variable
    supabase_url = args.supabase_url or os.getenv("DATABASE_POSTGRES_URL")
    if not supabase_url:
        logger.error(
            "Supabase URL not provided. Either use --supabase-url argument "
            "or set DATABASE_POSTGRES_URL in .env file"
        )
        sys.exit(1)

    # Normalize postgres:// to postgresql:// (SQLAlchemy requirement)
    if supabase_url.startswith("postgres://"):
        logger.info(
            "Converting postgres:// to postgresql:// for SQLAlchemy compatibility"
        )
        supabase_url = supabase_url.replace("postgres://", "postgresql://", 1)

    # Validate SQLite path exists
    if not Path(args.sqlite_path).exists():
        logger.error(f"SQLite database not found: {args.sqlite_path}")
        sys.exit(1)

    try:
        migrate_database(
            sqlite_path=args.sqlite_path,
            supabase_url=supabase_url,
            dry_run=args.dry_run,
            clear_tables_first=args.clear_tables,
        )
    except Exception:
        logger.exception("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
