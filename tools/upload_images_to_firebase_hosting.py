#!/usr/bin/env python3
"""
Upload images to Firebase Storage and update database records.

This script uploads images from the local images directory to Firebase Storage
and updates the database records with Firebase Storage URLs. It skips Mapillary
images and supports resumable uploads via a progress tracking file.

Usage:
    python tools/upload_images_to_firebase_hosting.py \\
        [--images-dir images] \\
        [--firebase-bucket BUCKET_NAME] \\
        [--firebase-credentials PATH] \\
        [--firebase-credentials-base64 BASE64] \\
        [--progress-file .upload_progress.json] \\
        [--database-url DATABASE_URL] \\
        [--dry-run]

Either --firebase-credentials or --firebase-credentials-base64 must be provided.
If --database-url is not provided, DATABASE_POSTGRES_URL from .env will be used.
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


from bench_finder.models.enums import DataSource  # noqa: E402
from bench_finder.models.unified_models import (  # noqa: E402
    BenchCandidate,
    Image,
)


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
    Load upload progress from file.

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
    Save upload progress to file.

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
        progress_file: Progress file path
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
                logger.error(
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


def upload_images(
    images_dir: str,
    firebase_project_id: str,
    firebase_hosting_site: str | None = None,
    progress_file: str | None = None,
    database_url: str | None = None,
    dry_run: bool = False,
    update_database: bool = True,
):
    """
    Main function to upload images to Firebase Hosting.

    Args:
        images_dir: Local directory containing images
        firebase_project_id: Firebase project ID
        firebase_hosting_site: Firebase Hosting site ID (optional)
        progress_file: Path to progress tracking file
        database_url: Database connection URL (optional)
        dry_run: If True, only simulate upload
        update_database: If True, update database records with Firebase URLs
    """
    logger.info("=" * 60)
    logger.info("Image Upload: Local -> Firebase Hosting")
    logger.info("=" * 60)

    if dry_run:
        logger.info("DRY RUN MODE - No images will be uploaded")

    # Initialize progress tracking
    if progress_file:
        progress_path = Path(progress_file)
    else:
        progress_path = Path(".upload_progress.json")

    progress = load_progress(progress_path)
    logger.info(f"Loaded progress from: {progress_path}")
    logger.info(f"Already uploaded: {len(progress.get('images_uploaded', {}))} images")

    # Initialize database connection if updating database
    session = None
    # if update_database and not dry_run:
    # if database_url:
    #     engine = init_database(database_url=database_url)
    #     session = Session(engine)
    # else:
    #     # Use default database
    #     db = BenchDatabase()
    #     session = db.get_session()

    try:
        images_path = Path(images_dir)

        # Get all images from database
        images_with_candidates = []
        if session:
            images = session.query(Image).all()
            logger.info(f"Found {len(images)} images in database")

            for image in images:
                bench_candidate = (
                    session.query(BenchCandidate)
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
        else:
            # If no database, scan images directory
            logger.info(f"Scanning images directory: {images_path}")
            for image_file in images_path.glob("*"):
                if image_file.is_file() and image_file.suffix.lower() in [
                    ".jpg",
                    ".jpeg",
                    ".png",
                ]:
                    # Create a minimal Image-like object
                    class FakeImage:
                        id = image_file.stem
                        filename = image_file.name
                        filepath = None
                        firebase_url = None

                    images_with_candidates.append((FakeImage(), image_file, None))

        logger.info(f"Found {len(images_with_candidates)} images to process")

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

    finally:
        if session:
            session.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Upload images to Firebase Hosting and update database"
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
        default=".upload_progress.json",
        help="Path to progress tracking file",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="Database connection URL (from .env: DATABASE_POSTGRES_URL)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - validate but don't upload images",
    )
    parser.add_argument(
        "--no-update-db",
        action="store_true",
        help="Don't update database records with Firebase URLs",
    )

    args = parser.parse_args()

    # Get Firebase project ID from argument or environment
    firebase_project_id = args.firebase_project_id or os.getenv("FIREBASE_PROJECT_ID")
    if not firebase_project_id:
        logger.error(
            "Firebase project ID not provided. Either use --firebase-project-id argument "
            "or set FIREBASE_PROJECT_ID in .env file"
        )
        sys.exit(1)

    # Get database URL from argument or environment
    database_url = args.database_url or os.getenv("DATABASE_POSTGRES_URL")

    # Validate images directory exists
    if not Path(args.images_dir).exists():
        logger.error(f"Images directory not found: {args.images_dir}")
        sys.exit(1)

    try:
        upload_images(
            images_dir=args.images_dir,
            firebase_project_id=firebase_project_id,
            firebase_hosting_site=args.firebase_hosting_site,
            progress_file=args.progress_file,
            database_url=database_url,
            dry_run=args.dry_run,
            update_database=not args.no_update_db,
        )
    except Exception:
        logger.exception("Upload failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
