#!/usr/bin/env python3
"""
Migration script to copy data from SQLite to Cloud SQL PostgreSQL database.

This script exports all data from the local SQLite database and imports it
into a PostgreSQL database (Cloud SQL or any PostgreSQL), maintaining all
relationships and data integrity.

The script automatically adds the current IP to the Cloud SQL authorized
networks before migration if CLOUDSQL_INSTANCE and GCP_PROJECT are configured.

For uploading images to Firebase Hosting, use the separate script:
    python tools/upload_images_to_firebase_hosting.py

Usage:
    python tools/migrate_to_cloudsql.py \\
        [--sqlite-path data/benches.db] \\
        [--postgres-url postgresql://user:pass@host/db] \\
        [--cloudsql-instance instance-name] \\
        [--gcp-project project-id] \\
        [--dry-run] \\
        [--clear-tables]

If --postgres-url is not provided, DATABASE_URL from .env will be used.
If --cloudsql-instance and --gcp-project are not provided, CLOUDSQL_INSTANCE
and GCP_PROJECT from .env will be used for automatic IP allowlisting.
"""

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
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

from bench_finder.models.unified_models import (  # noqa: E402
    BenchCandidate,
    BenchReport,
    DataSource,
    Detection,
    DetectionItem,
    Image,
    MissingBenchReport,
    ProcessedBench,
    ReverseGeocode,
    Search,
    init_database,
)


# BenchDatabase not needed - using init_database directly to avoid DATABASE_URL env var conflicts


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_current_ip() -> str:
    """
    Get the current public IP address.

    Returns:
        The current public IP address as a string.

    Raises:
        RuntimeError: If unable to determine the public IP address.
    """
    services = [
        "https://api.ipify.org",
        "https://ifconfig.me/ip",
        "https://icanhazip.com",
    ]

    for service in services:
        try:
            with urllib.request.urlopen(service, timeout=5) as response:
                ip = response.read().decode("utf-8").strip()
                logger.info(f"Current public IP: {ip}")
                return ip
        except Exception as e:
            logger.debug(f"Failed to get IP from {service}: {e}")
            continue

    raise RuntimeError("Unable to determine public IP address")


def _get_cloudsql_service():
    """
    Get an authenticated Cloud SQL Admin API service client.

    Loads credentials from firebase_creds.json or FIREBASE_CREDENTIALS_PATH.

    Returns:
        A tuple of (Google Cloud SQL Admin API service client, project_id).

    Raises:
        RuntimeError: If unable to authenticate.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient import discovery

        # Find credentials file - try multiple paths
        creds_paths = [
            os.getenv("FIREBASE_CREDENTIALS_PATH"),
            "firebase_creds.json",
            project_root / "firebase_creds.json",
        ]

        creds_path = None
        for path in creds_paths:
            if path and Path(path).exists():
                creds_path = path
                break

        if not creds_path:
            raise RuntimeError(
                "Credentials file not found. Set FIREBASE_CREDENTIALS_PATH "
                "or place firebase_creds.json in the project root."
            )

        credentials = service_account.Credentials.from_service_account_file(
            str(creds_path),
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )

        # Get project ID from credentials file
        with open(creds_path) as f:
            creds_data = json.load(f)
            project_id = creds_data.get("project_id")

        service = discovery.build("sqladmin", "v1beta4", credentials=credentials)
        return service, project_id
    except Exception as e:
        logger.error(f"Failed to create Cloud SQL API client: {e}")
        raise RuntimeError(f"Failed to authenticate with Google Cloud: {e}")


def get_gcp_project() -> str | None:
    """
    Get the current GCP project from firebase_creds.json or gcloud config.

    Returns:
        The current GCP project ID, or None if not configured.
    """
    # Try firebase_creds.json first
    try:
        creds_paths = [
            os.getenv("FIREBASE_CREDENTIALS_PATH"),
            "firebase_creds.json",
            project_root / "firebase_creds.json",
        ]
        for creds_path in creds_paths:
            if creds_path and Path(creds_path).exists():
                with open(creds_path) as f:
                    creds_data = json.load(f)
                    project = creds_data.get("project_id")
                    if project:
                        logger.info(
                            f"Discovered GCP project from credentials: {project}"
                        )
                        return project
    except Exception as e:
        logger.debug(f"Failed to get project from credentials file: {e}")

    # Fall back to gcloud config
    try:
        result = subprocess.run(
            ["gcloud", "config", "get-value", "project"],
            capture_output=True,
            text=True,
            check=True,
        )
        project = result.stdout.strip()
        if project and project != "(unset)":
            logger.info(f"Discovered GCP project from gcloud config: {project}")
            return project
    except subprocess.CalledProcessError:
        pass
    except FileNotFoundError:
        logger.debug("gcloud CLI not found")

    return None


def get_cloudsql_instance(project_id: str) -> str | None:
    """
    Get the Cloud SQL instance name for a project.

    Tries Python API first, then falls back to gcloud CLI.
    If there's only one instance, returns it. If there are multiple,
    returns the first one and logs a warning.

    Args:
        project_id: Google Cloud project ID

    Returns:
        The Cloud SQL instance name, or None if no instances found.
    """
    instances = []

    # Try Python API first
    try:
        service, _ = _get_cloudsql_service()
        request = service.instances().list(project=project_id)
        response = request.execute()
        instances = [i["name"] for i in response.get("items", [])]
    except Exception as e:
        logger.debug(f"Python API failed to list instances: {e}")

    # Fall back to gcloud CLI
    if not instances:
        try:
            result = subprocess.run(
                [
                    "gcloud",
                    "sql",
                    "instances",
                    "list",
                    "--project",
                    project_id,
                    "--format=value(name)",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            instances = [
                i.strip() for i in result.stdout.strip().split("\n") if i.strip()
            ]
        except subprocess.CalledProcessError as e:
            logger.debug(f"gcloud failed to list instances: {e.stderr}")
        except FileNotFoundError:
            logger.debug("gcloud CLI not found")

    if not instances:
        logger.warning(f"No Cloud SQL instances found in project {project_id}")
        return None

    if len(instances) == 1:
        logger.info(f"Discovered Cloud SQL instance: {instances[0]}")
        return instances[0]
    else:
        logger.warning(
            f"Multiple Cloud SQL instances found: {instances}. "
            f"Using first one: {instances[0]}. "
            f"Use --cloudsql-instance to specify a different one."
        )
        return instances[0]


def add_ip_to_cloudsql_allowlist(
    instance_name: str,
    project_id: str,
    ip_address: str | None = None,
) -> None:
    """
    Add the current IP address to Cloud SQL instance authorized networks.

    Tries Python API first, then falls back to gcloud CLI.

    Args:
        instance_name: Cloud SQL instance name
        project_id: Google Cloud project ID
        ip_address: IP address to add (if None, will be auto-detected)

    Raises:
        RuntimeError: If unable to add IP to allowlist
    """
    if ip_address is None:
        ip_address = get_current_ip()

    logger.info(f"Adding IP {ip_address} to Cloud SQL allowlist...")

    # Try Python API first
    try:
        service, _ = _get_cloudsql_service()

        # Get current instance settings
        request = service.instances().get(project=project_id, instance=instance_name)
        instance_info = request.execute()

        # Get current authorized networks
        settings = instance_info.get("settings", {})
        ip_config = settings.get("ipConfiguration", {})
        current_networks = ip_config.get("authorizedNetworks", [])

        # Check if IP is already authorized
        for network in current_networks:
            if (
                network.get("value") == ip_address
                or network.get("value") == f"{ip_address}/32"
            ):
                logger.info(f"IP {ip_address} is already in the allowlist")
                return

        # Build the new authorized networks list
        new_networks = list(current_networks)
        new_entry_name = f"migrate-{ip_address.replace('.', '-')}"
        new_networks.append(
            {
                "name": new_entry_name,
                "value": f"{ip_address}/32",
            }
        )

        # Update the instance
        logger.info(
            f"Updating Cloud SQL instance {instance_name} authorized networks..."
        )
        body = {
            "settings": {
                "ipConfiguration": {
                    "authorizedNetworks": new_networks,
                }
            }
        }
        request = service.instances().patch(
            project=project_id,
            instance=instance_name,
            body=body,
        )
        request.execute()
        logger.info(f"✓ Successfully added IP {ip_address} to Cloud SQL allowlist")
        return
    except Exception as e:
        logger.debug(f"Python API failed to update allowlist: {e}")

    # Fall back to gcloud CLI
    logger.info("Falling back to gcloud CLI...")
    try:
        # Get current authorized networks via gcloud
        result = subprocess.run(
            [
                "gcloud",
                "sql",
                "instances",
                "describe",
                instance_name,
                "--project",
                project_id,
                "--format=json",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        instance_info = json.loads(result.stdout)

        settings = instance_info.get("settings", {})
        ip_config = settings.get("ipConfiguration", {})
        current_networks = ip_config.get("authorizedNetworks", [])

        # Check if IP is already authorized
        for network in current_networks:
            if (
                network.get("value") == ip_address
                or network.get("value") == f"{ip_address}/32"
            ):
                logger.info(f"IP {ip_address} is already in the allowlist")
                return

        # Build the new authorized networks list for gcloud
        # gcloud format is just comma-separated CIDR values
        network_values = []
        for network in current_networks:
            value = network.get("value", "")
            if value:
                network_values.append(value)

        # Add the new IP
        new_ip_cidr = f"{ip_address}/32"
        network_values.append(new_ip_cidr)
        networks_arg = ",".join(network_values)

        # Update via gcloud
        logger.info(
            f"Updating Cloud SQL instance {instance_name} authorized networks..."
        )
        result = subprocess.run(
            [
                "gcloud",
                "sql",
                "instances",
                "patch",
                instance_name,
                "--project",
                project_id,
                f"--authorized-networks={networks_arg}",
                "--quiet",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        logger.info(f"✓ Successfully added IP {ip_address} to Cloud SQL allowlist")
    except subprocess.CalledProcessError as e:
        logger.error(f"gcloud failed: {e.stderr}")
        raise RuntimeError(f"Failed to add IP to Cloud SQL allowlist: {e.stderr}")
    except FileNotFoundError:
        raise RuntimeError(
            "Neither Python API nor gcloud CLI could update the allowlist. "
            "Install gcloud or grant Cloud SQL Admin permissions to the service account."
        )


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
                    logger.debug(f"stdout: {e.stdout}")
                if e.stderr:
                    logger.debug(f"stderr: {e.stderr}")
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
        target_session: Target database session (PostgreSQL/Cloud SQL)
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
    postgres_url: str,
    dry_run: bool = False,
    clear_tables_first: bool = False,
):
    """
    Migrate all data from SQLite to PostgreSQL (Cloud SQL or other).

    Args:
        sqlite_path: Path to SQLite database file
        postgres_url: PostgreSQL connection URL
        dry_run: If True, only validate without migrating
        clear_tables_first: If True, clear all tables in target before migrating
    """
    logger.info("=" * 60)
    logger.info("Database Migration: SQLite -> PostgreSQL (Cloud SQL)")
    logger.info("=" * 60)

    if dry_run:
        logger.info("DRY RUN MODE - No data will be written")

    # Create source database connection (SQLite)
    # Use init_database directly to bypass BenchDatabase which may use DATABASE_URL from env
    logger.info(f"Connecting to source database: {sqlite_path}")
    source_engine = init_database(database_path=sqlite_path, database_url=None)

    # Verify we're actually connected to SQLite
    if source_engine.dialect.name != "sqlite":
        raise ValueError(
            f"Expected SQLite database but got {source_engine.dialect.name}. "
            f"Please ensure the SQLite path is correct: {sqlite_path}"
        )

    # Create target database connection (PostgreSQL/Cloud SQL)
    logger.info("Connecting to target database (PostgreSQL)...")
    target_engine = init_database(database_url=postgres_url)
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
        # Create session directly from engine to bypass BenchDatabase wrapper
        source_session = Session(source_engine)
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

        # Migrate all tables
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

        # Create indexes after data migration is complete
        logger.info("=" * 60)
        logger.info("Creating indexes in target database...")
        logger.info("=" * 60)
        create_indexes(target_engine, source_indexes, dry_run=dry_run)

        logger.info("=" * 60)
        logger.info(f"Migration complete! Total records migrated: {total_migrated}")
        logger.info("=" * 60)
        logger.info(
            "Note: To upload images to Firebase Hosting, run: "
            "python tools/upload_images_to_firebase_hosting.py"
        )

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
        description="Migrate SQLite database to PostgreSQL (Cloud SQL)"
    )
    parser.add_argument(
        "--sqlite-path",
        type=str,
        default="data/benches.db",
        help="Path to SQLite database file",
    )
    parser.add_argument(
        "--postgres-url",
        type=str,
        default=None,
        help=(
            "PostgreSQL connection URL (postgresql://user:pass@host/db). "
            "If not provided, DATABASE_URL from .env will be used."
        ),
    )
    # Legacy argument for backward compatibility
    parser.add_argument(
        "--supabase-url",
        type=str,
        default=None,
        help=argparse.SUPPRESS,  # Hidden, for backward compatibility
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
        "--cloudsql-instance",
        type=str,
        default=None,
        help=(
            "Cloud SQL instance name. If not provided, CLOUDSQL_INSTANCE "
            "from .env will be used."
        ),
    )
    parser.add_argument(
        "--gcp-project",
        type=str,
        default=None,
        help=(
            "Google Cloud project ID. If not provided, GCP_PROJECT "
            "from .env will be used."
        ),
    )

    args = parser.parse_args()

    # Get PostgreSQL URL from argument or environment variable
    postgres_url = args.postgres_url or args.supabase_url or os.getenv("DATABASE_URL")
    if not postgres_url:
        logger.error(
            "PostgreSQL URL not provided. Either use --postgres-url argument "
            "or set DATABASE_URL in .env file"
        )
        sys.exit(1)

    # Normalize postgres:// to postgresql:// (SQLAlchemy requirement)
    if postgres_url.startswith("postgres://"):
        logger.info(
            "Converting postgres:// to postgresql:// for SQLAlchemy compatibility"
        )
        postgres_url = postgres_url.replace("postgres://", "postgresql://", 1)

    # Validate SQLite path exists
    if not Path(args.sqlite_path).exists():
        logger.error(f"SQLite database not found: {args.sqlite_path}")
        sys.exit(1)

    # Get Cloud SQL instance and project for IP allowlisting
    # Priority: CLI arg > env var > auto-discover from gcloud
    gcp_project = args.gcp_project or os.getenv("GCP_PROJECT") or get_gcp_project()
    cloudsql_instance = args.cloudsql_instance or os.getenv("CLOUDSQL_INSTANCE")

    # If we have a project but no instance, try to discover the instance
    if gcp_project and not cloudsql_instance:
        cloudsql_instance = get_cloudsql_instance(gcp_project)

    # Add current IP to Cloud SQL allowlist
    if cloudsql_instance and gcp_project:
        try:
            add_ip_to_cloudsql_allowlist(
                instance_name=cloudsql_instance,
                project_id=gcp_project,
            )
        except RuntimeError as e:
            logger.error(f"Failed to add IP to allowlist: {e}")
            logger.warning(
                "Continuing with migration - connection may fail if IP not allowed"
            )
    else:
        logger.warning(
            "Could not determine Cloud SQL instance or project. Skipping IP allowlist. "
            "Ensure gcloud is configured or set CLOUDSQL_INSTANCE and GCP_PROJECT in .env."
        )

    try:
        migrate_database(
            sqlite_path=args.sqlite_path,
            postgres_url=postgres_url,
            dry_run=args.dry_run,
            clear_tables_first=args.clear_tables,
        )
    except Exception:
        logger.exception("Migration failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
