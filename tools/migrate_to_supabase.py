#!/usr/bin/env python3
"""
Migration script to copy data from SQLite to Supabase PostgreSQL database.

This script exports all data from the local SQLite database and imports it
into a Supabase PostgreSQL database, maintaining all relationships and data integrity.
It also uploads images to Firebase Hosting and updates database records with hosting URLs.

Usage:
    python tools/migrate_to_supabase.py \\
        [--sqlite-path data/benches.db] \\
        [--supabase-url postgresql://user:pass@host/db] \\
        [--images-dir images] \\
        [--firebase-project-id PROJECT_ID] \\
        [--firebase-hosting-site SITE_ID] \\
        [--progress-file .migration_progress.json] \\
        [--dry-run] \\
        [--clear-tables] \\
        [--skip-images]

If --supabase-url is not provided, DATABASE_POSTGRES_URL from .env will be used.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


# Load environment variables from .env file
_ = load_dotenv()

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from bench_finder.models.enums import DataSource  # noqa: E402
from bench_finder.models.unified_models import (  # noqa: E402
    BenchCandidate,
    BenchReport,
    Detection,
    DetectionItem,
    Image,
    MissingBenchReport,
    ProcessedBench,
    ReverseGeocode,
    Search,
    init_database,
)
from bench_finder.services.database import BenchDatabase  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def is_mapillary_image(
    image: Image, bench_candidate: BenchCandidate | None = None
) -> bool:
    """
    Check if an image is from Mapillary.

    Args:
        image: Image object to check
        bench_candidate: Optional bench candidate to check source

    Returns:
        True if image is from Mapillary, False otherwise
    """
    # Check if bench candidate source is Mapillary
    if bench_candidate and bench_candidate.source == DataSource.MAPILLARY:
        return True

    # Check if filename or filepath contains "mapillary"
    if image.filename and "mapillary" in image.filename.lower():
        return True
    if image.filepath and "mapillary" in image.filepath.lower():
        return True

    # Check if firebase_url contains "mapillary"
    return bool(image.firebase_url and "mapillary" in image.firebase_url.lower())


def load_progress(progress_file: Path) -> dict[str, Any]:
    """
    Load migration progress from file.

    Args:
        progress_file: Path to progress file

    Returns:
        Dictionary with progress data
    """
    if progress_file.exists():
        try:
            with open(progress_file) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load progress file: {e}. Starting fresh.")
    return {
        "images_uploaded": {},
        "last_image_id": None,
    }


def save_progress(progress_file: Path, progress: dict[str, Any]):
    """
    Save migration progress to file.

    Args:
        progress_file: Path to progress file
        progress: Progress dictionary to save
    """
    try:
        with open(progress_file, "w") as f:
            json.dump(progress, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save progress file: {e}")


def upload_images_to_firebase_hosting(
    images: list[tuple[Image, Path, BenchCandidate | None]],
    images_dir: Path,
    firebase_project_id: str,
    firebase_hosting_site: str | None,
    progress: dict[str, Any],
    progress_file: Path,
    dry_run: bool = False,
) -> dict[str, str]:
    """
    Upload images to Firebase Hosting and return mapping of image IDs to hosting URLs.

    Args:
        images: List of (Image, local_path, BenchCandidate) tuples
        images_dir: Local directory containing images
        firebase_project_id: Firebase project ID
        firebase_hosting_site: Firebase Hosting site ID (optional)
        progress: Progress dictionary
        progress: Progress file path
        dry_run: If True, only simulate upload

    Returns:
        Dictionary mapping image ID to Firebase Hosting URL
    """
    logger.info("=" * 60)
    logger.info("Uploading Images to Firebase Hosting")
    logger.info("=" * 60)

    if dry_run:
        logger.info("[DRY RUN] Would upload images to Firebase Hosting")
        return {}

    # Filter out Mapillary images and already uploaded images
    images_to_upload = []
    skipped_mapillary = 0
    skipped_already_uploaded = 0

    for image, local_path, bench_candidate in images:
        # Skip Mapillary images
        if is_mapillary_image(image, bench_candidate):
            skipped_mapillary += 1
            logger.debug(f"Skipping Mapillary image: {image.filename}")
            continue

        # Skip if already uploaded
        if str(image.id) in progress.get("images_uploaded", {}):
            skipped_already_uploaded += 1
            logger.debug(f"Skipping already uploaded image: {image.filename}")
            continue

        # Check if local file exists
        if not local_path.exists():
            logger.warning(f"Local file not found: {local_path}, skipping")
            continue

        images_to_upload.append((image, local_path, bench_candidate))

    logger.info(f"Found {len(images_to_upload)} images to upload")
    logger.info(f"Skipped {skipped_mapillary} Mapillary images")
    logger.info(f"Skipped {skipped_already_uploaded} already uploaded images")

    if not images_to_upload:
        logger.info("No images to upload")
        return {}

    # Create temporary directory for Firebase Hosting deployment
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        hosting_images_dir = temp_path / "public" / "images"
        hosting_images_dir.mkdir(parents=True, exist_ok=True)

        # Copy images to hosting directory
        uploaded_count = 0
        failed_count = 0
        image_urls = {}

        for image, local_path, _bench_candidate in images_to_upload:
            try:
                # Copy image to hosting directory
                dest_path = hosting_images_dir / image.filename
                shutil.copy2(local_path, dest_path)
                logger.info(f"Prepared {image.filename} for upload")

                # Build Firebase Hosting URL
                # Format: https://<site-id>.web.app/images/<filename>
                if firebase_hosting_site:
                    hosting_url = f"https://{firebase_hosting_site}.web.app/images/{image.filename}"
                else:
                    hosting_url = (
                        f"https://{firebase_project_id}.web.app/images/{image.filename}"
                    )

                image_urls[str(image.id)] = hosting_url
                progress["images_uploaded"][str(image.id)] = hosting_url
                progress["last_image_id"] = image.id

                uploaded_count += 1

                # Save progress periodically
                if uploaded_count % 10 == 0:
                    save_progress(progress_file, progress)
                    logger.info(f"Progress saved: {uploaded_count} images prepared")

            except Exception:
                logger.exception(f"Failed to prepare image {image.filename}")
                failed_count += 1

        # Deploy to Firebase Hosting
        if image_urls:
            logger.info(f"Deploying {len(image_urls)} images to Firebase Hosting...")
            try:
                # Create firebase.json if it doesn't exist in temp directory
                firebase_json = temp_path / "firebase.json"
                firebase_json.write_text(
                    json.dumps(
                        {
                            "hosting": {
                                "public": "public",
                                "ignore": [
                                    "firebase.json",
                                    "**/.*",
                                    "**/node_modules/**",
                                ],
                            }
                        },
                        indent=2,
                    )
                )

                # Build Firebase deploy command
                if firebase_hosting_site:
                    cmd = [
                        "firebase",
                        "deploy",
                        "--only",
                        f"hosting:{firebase_hosting_site}",
                        "--project",
                        firebase_project_id,
                    ]
                else:
                    cmd = [
                        "firebase",
                        "deploy",
                        "--only",
                        "hosting",
                        "--project",
                        firebase_project_id,
                    ]

                result = subprocess.run(
                    cmd,
                    cwd=temp_path,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                logger.info("✓ Successfully deployed images to Firebase Hosting")
                logger.info(f"  Deployed {uploaded_count} images")
                if result.stdout:
                    logger.debug(f"Firebase output: {result.stdout}")

            except subprocess.CalledProcessError as e:
                logger.exception("Failed to deploy to Firebase Hosting")
                if e.stdout:
                    logger.exception(f"stdout: {e.stdout}")
                if e.stderr:
                    logger.exception(f"stderr: {e.stderr}")
                raise
            except FileNotFoundError:
                logger.exception(
                    "Firebase CLI not found. Please install it: "
                    "npm install -g firebase-tools"
                )
                raise

        # Save final progress
        save_progress(progress_file, progress)

        logger.info("=" * 60)
        logger.info("Image Upload Summary:")
        logger.info(f"  Successfully uploaded: {uploaded_count}")
        logger.info(f"  Failed: {failed_count}")
        logger.info(f"  Skipped (Mapillary): {skipped_mapillary}")
        logger.info(f"  Skipped (already uploaded): {skipped_already_uploaded}")
        logger.info("=" * 60)

    return image_urls


def get_table_names(engine):
    """Get list of table names from database."""
    inspector = inspect(engine)
    return inspector.get_table_names()


def get_indexes(engine):
    """
    Get all indexes from database.

    Args:
        engine: SQLAlchemy engine

    Returns:
        Dictionary mapping table_name -> list of index info dicts
    """
    inspector = inspect(engine)
    indexes_by_table = {}

    for table_name in inspector.get_table_names():
        indexes = inspector.get_indexes(table_name)
        if indexes:
            indexes_by_table[table_name] = indexes

    return indexes_by_table


def create_indexes(
    target_engine, indexes_by_table: dict[str, list], dry_run: bool = False
):
    """
    Create indexes in target database.

    Args:
        target_engine: Target database engine (PostgreSQL)
        indexes_by_table: Dictionary of table_name -> list of index info
        dry_run: If True, only log what would be created
    """
    logger.info("=" * 60)
    logger.info("Creating Indexes in Target Database")
    logger.info("=" * 60)

    is_postgresql = target_engine.dialect.name == "postgresql"
    total_indexes = sum(len(indexes) for indexes in indexes_by_table.values())
    created = 0
    skipped = 0

    for table_name, indexes in indexes_by_table.items():
        for index_info in indexes:
            index_name = index_info["name"]
            columns = index_info.get("column_names", [])

            # Skip SQLite internal indexes (sqlite_autoindex_*)
            if index_name.startswith("sqlite_autoindex_"):
                logger.debug(f"Skipping SQLite internal index: {index_name}")
                skipped += 1
                continue

            # Skip primary key indexes (they're automatically created)
            if index_info.get("unique", False) and len(columns) == 1:
                # Check if it's a primary key column
                inspector = inspect(target_engine)
                pk_constraint = inspector.get_pk_constraint(table_name)
                if pk_constraint and columns[0] in pk_constraint.get(
                    "constrained_columns", []
                ):
                    logger.debug(f"Skipping primary key index: {index_name}")
                    skipped += 1
                    continue

            # Build CREATE INDEX statement
            columns_str = ", ".join(columns)
            unique = "UNIQUE " if index_info.get("unique", False) else ""

            if is_postgresql:
                # PostgreSQL syntax
                create_sql = f"CREATE {unique}INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"
            else:
                # SQLite syntax (for reference, though we're migrating to PostgreSQL)
                create_sql = f"CREATE {unique}INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns_str})"

            if dry_run:
                logger.info(
                    f"[DRY RUN] Would create index: {index_name} on {table_name}({columns_str})"
                )
                created += 1
            else:
                try:
                    with target_engine.begin() as conn:
                        conn.execute(text(create_sql))
                    logger.info(
                        f"✅ Created index: {index_name} on {table_name}({columns_str})"
                    )
                    created += 1
                except Exception as e:
                    # Index might already exist or there might be a constraint issue
                    error_msg = str(e).lower()
                    if "already exists" in error_msg or "duplicate" in error_msg:
                        logger.debug(f"⏭️  Index already exists: {index_name}")
                        skipped += 1
                    else:
                        logger.warning(f"⚠️  Failed to create index {index_name}: {e}")
                        skipped += 1

    logger.info("=" * 60)
    if dry_run:
        logger.info(f"[DRY RUN] Would create {created} indexes, skip {skipped}")
    else:
        logger.info(
            f"Index creation complete: Created {created}, Skipped {skipped}, Total {total_indexes}"
        )
    logger.info("=" * 60)


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
    images_dir: str | None = None,
    firebase_project_id: str | None = None,
    firebase_hosting_site: str | None = None,
    progress_file: str | None = None,
    dry_run: bool = False,
    clear_tables_first: bool = False,
    skip_images: bool = False,
):
    """
    Migrate all data from SQLite to Supabase and upload images to Firebase Hosting.

    Args:
        sqlite_path: Path to SQLite database file
        supabase_url: Supabase PostgreSQL connection URL
        images_dir: Local directory containing images
        firebase_project_id: Firebase project ID for hosting
        firebase_hosting_site: Firebase Hosting site ID (optional)
        progress_file: Path to progress tracking file
        dry_run: If True, only validate without migrating
        clear_tables_first: If True, clear all tables in target before migrating
        skip_images: If True, skip image upload step
    """
    logger.info("=" * 60)
    logger.info("Database Migration: SQLite -> Supabase")
    logger.info("=" * 60)

    if dry_run:
        logger.info("DRY RUN MODE - No data will be written")

    # Initialize progress tracking
    if progress_file:
        progress_path = Path(progress_file)
    else:
        progress_path = Path(".migration_progress.json")

    progress = load_progress(progress_path)
    logger.info(f"Loaded progress from: {progress_path}")
    logger.info(f"Already uploaded: {len(progress.get('images_uploaded', {}))} images")

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
        (ReverseGeocode, "reverse_geocodes"),  # Depends on bench_candidates
        (Detection, "detections"),  # Depends on images
        (DetectionItem, "detection_items"),  # Depends on detections
        (
            ProcessedBench,
            "processed_benches",
        ),  # Depends on bench_candidates, images, detections
        (BenchReport, "bench_reports"),  # Depends on bench_candidates, images
        (MissingBenchReport, "missing_bench_reports"),  # No foreign keys
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

        # Get indexes from source database to copy to target
        logger.info("Extracting indexes from source database...")
        source_indexes = get_indexes(source_engine)
        logger.info(
            f"Found {sum(len(idxs) for idxs in source_indexes.values())} indexes across {len(source_indexes)} tables"
        )

        # Migrate tables (but skip images initially if we're uploading to Firebase Hosting)
        tables_to_migrate = migration_order.copy()
        images_model_class = None
        images_table_name = None

        if not skip_images and firebase_project_id:
            # Remove images from initial migration order
            for idx, (model_class, table_name) in enumerate(tables_to_migrate):
                if table_name == "images":
                    images_model_class = model_class
                    images_table_name = table_name
                    tables_to_migrate.pop(idx)
                    break

        for model_class, table_name in tables_to_migrate:
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

        # Handle image upload and migration
        image_urls = {}
        if not skip_images and firebase_project_id and images_model_class:
            # Get all images with their bench candidates
            images_with_candidates = []
            images_path = Path(images_dir) if images_dir else Path("images")

            # Query images with bench candidates
            source_images = source_session.query(Image).all()
            logger.info(f"Found {len(source_images)} images in source database")

            for image in source_images:
                bench_candidate = (
                    source_session.query(BenchCandidate)
                    .filter(BenchCandidate.id == image.bench_candidate_id)
                    .first()
                )

                # Skip Mapillary images
                if is_mapillary_image(image, bench_candidate):
                    continue

                if image.filename:
                    local_path = images_path / image.filename
                    if local_path.exists():
                        images_with_candidates.append(
                            (image, local_path, bench_candidate)
                        )

            # Upload images to Firebase Hosting
            image_urls = upload_images_to_firebase_hosting(
                images_with_candidates,
                images_path,
                firebase_project_id,
                firebase_hosting_site,
                progress,
                progress_path,
                dry_run=dry_run,
            )

            # Now migrate images table with updated Firebase URLs
            logger.info("Migrating images table with Firebase Hosting URLs...")
            source_images = source_session.query(Image).all()

            migrated_images = 0
            for image in source_images:
                try:
                    # Update firebase_url if we have a hosting URL
                    if str(image.id) in image_urls:
                        image.firebase_url = image_urls[str(image.id)]
                    elif str(image.id) in progress.get("images_uploaded", {}):
                        image.firebase_url = progress["images_uploaded"][str(image.id)]

                    # Convert to dict
                    record_dict = {
                        col.name: getattr(image, col.name)
                        for col in inspect(Image).mapper.columns
                    }
                    # Remove None primary key
                    if "id" in record_dict and record_dict["id"] is None:
                        record_dict.pop("id")

                    target_image = Image(**record_dict)
                    target_session.add(target_image)
                    migrated_images += 1

                except Exception:
                    logger.exception(f"Failed to migrate image {image.id}")
                    target_session.rollback()
                    raise

            if not dry_run:
                target_session.commit()
                logger.info(f"Migrated {migrated_images} images to {images_table_name}")
                total_migrated += migrated_images

        elif images_model_class and images_table_name:
            # Just migrate images without Firebase Hosting
            count = migrate_table(
                source_session,
                target_session,
                images_model_class,
                images_table_name,
                dry_run=dry_run,
            )
            total_migrated += count

        # Create indexes after data migration is complete
        logger.info("=" * 60)
        logger.info("Creating indexes in target database...")
        logger.info("=" * 60)
        create_indexes(target_engine, source_indexes, dry_run=dry_run)

        logger.info("=" * 60)
        logger.info(f"Migration complete! Total records migrated: {total_migrated}")
        if image_urls:
            logger.info(f"Images uploaded to Firebase Hosting: {len(image_urls)}")
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
    parser.add_argument(
        "--images-dir",
        type=str,
        default="images",
        help="Local directory containing images to upload",
    )
    parser.add_argument(
        "--firebase-project-id",
        type=str,
        default=None,
        help="Firebase project ID for hosting (from .env: FIREBASE_PROJECT_ID)",
    )
    parser.add_argument(
        "--firebase-hosting-site",
        type=str,
        default=None,
        help="Firebase Hosting site ID (optional, defaults to project ID)",
    )
    parser.add_argument(
        "--progress-file",
        type=str,
        default=".migration_progress.json",
        help="Path to progress tracking file",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="Skip image upload step (just migrate database)",
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

    # Get Firebase project ID from argument or environment
    firebase_project_id = args.firebase_project_id or os.getenv("FIREBASE_PROJECT_ID")

    # If images are to be uploaded, validate Firebase project ID is provided
    if not args.skip_images and not firebase_project_id:
        logger.warning(
            "Firebase project ID not provided. Images will not be uploaded to Firebase Hosting. "
            "Set --firebase-project-id or FIREBASE_PROJECT_ID environment variable."
        )

    try:
        migrate_database(
            sqlite_path=args.sqlite_path,
            supabase_url=supabase_url,
            images_dir=args.images_dir,
            firebase_project_id=firebase_project_id,
            firebase_hosting_site=args.firebase_hosting_site,
            progress_file=args.progress_file,
            dry_run=args.dry_run,
            clear_tables_first=args.clear_tables,
            skip_images=args.skip_images,
        )
    except Exception:
        logger.exception("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
