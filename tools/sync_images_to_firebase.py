#!/usr/bin/env python3
"""
Sync local images to Firebase Storage and update database records.

This script uploads all images from the local images directory to Firebase Storage
and updates the database records with Firebase URLs.

Usage:
    python tools/sync_images_to_firebase.py \\
        --images-dir images \\
        --firebase-bucket bench-finder-images \\
        --firebase-credentials path/to/serviceAccount.json \\
        [--resume] \\
        [--dry-run]
"""

import argparse
import logging
import sys
from pathlib import Path


# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


from bench_finder.models.unified_models import Image  # noqa: E402
from bench_finder.services.database import BenchDatabase  # noqa: E402
from bench_finder.services.image_storage import FirebaseImageStorage  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def sync_images_to_firebase(
    images_dir: str,
    firebase_bucket: str,
    firebase_credentials: str,
    resume: bool = False,
    dry_run: bool = False,
):
    """
    Sync all local images to Firebase Storage and update database.

    Args:
        images_dir: Local directory containing images
        firebase_bucket: Firebase Storage bucket name
        firebase_credentials: Path to Firebase service account JSON file
        resume: Skip images that already have Firebase URLs
        dry_run: If True, only validate without uploading
    """
    import asyncio

    logger.info("=" * 60)
    logger.info("Image Sync: Local -> Firebase Storage")
    logger.info("=" * 60)

    if dry_run:
        logger.info("DRY RUN MODE - No images will be uploaded")

    # Initialize Firebase Storage
    logger.info(f"Initializing Firebase Storage: {firebase_bucket}")
    try:
        firebase_storage = FirebaseImageStorage(
            bucket_name=firebase_bucket,
            credentials_path=firebase_credentials,
        )
    except Exception:
        logger.exception("Failed to initialize Firebase Storage")
        sys.exit(1)

    # Initialize database
    logger.info("Connecting to database...")
    db = BenchDatabase()

    # Get all images from database
    with db.get_session() as session:
        images = session.query(Image).all()
        logger.info(f"Found {len(images)} images in database")

        # Filter images to sync
        images_to_sync = []
        for image in images:
            if not image.filename:
                logger.warning(f"Image {image.id} has no filename, skipping")
                continue

            if resume and image.firebase_url:
                logger.debug(
                    f"Image {image.filename} already has Firebase URL, skipping"
                )
                continue

            if not image.filepath:
                logger.warning(
                    f"Image {image.id} ({image.filename}) has no filepath, skipping"
                )
                continue

            # Check if local file exists
            local_path = Path(images_dir) / image.filename
            if not local_path.exists():
                logger.warning(
                    f"Local file not found for {image.filename}: {local_path}"
                )
                continue

            images_to_sync.append((image, local_path))

        logger.info(f"Found {len(images_to_sync)} images to sync")

        if dry_run:
            logger.info(
                f"[DRY RUN] Would upload {len(images_to_sync)} images to Firebase"
            )
            return

        # Sync images
        success_count = 0
        skip_count = 0
        fail_count = 0

        async def sync_all():
            """Sync all images to Firebase."""
            nonlocal success_count, skip_count, fail_count

            for image, local_path in images_to_sync:
                try:
                    # Check if image already exists in Firebase Storage
                    if firebase_storage.exists(image.filename):
                        # Image exists - get URL and update database if needed
                        if not image.firebase_url:
                            firebase_url = await firebase_storage.get_image_url(
                                image.filename
                            )
                            if firebase_url:
                                image.firebase_url = firebase_url
                                session.add(image)
                                session.commit()
                                logger.info(
                                    f"✓ Found existing {image.filename} -> {firebase_url}"
                                )
                            else:
                                logger.warning(
                                    f"Image {image.filename} exists but couldn't get URL"
                                )
                        else:
                            logger.debug(
                                f"⊘ Skipping {image.filename} - already exists in Firebase"
                            )
                        skip_count += 1
                        continue

                    # Image doesn't exist - upload it
                    logger.info(f"Uploading {image.filename}...")
                    firebase_url = await firebase_storage.upload_image(
                        str(local_path), image.filename
                    )

                    # Update database record
                    image.firebase_url = firebase_url
                    session.add(image)
                    session.commit()

                    logger.info(f"✓ Uploaded {image.filename} -> {firebase_url}")
                    success_count += 1

                except Exception:
                    logger.exception(f"✗ Failed to upload {image.filename}")
                    session.rollback()
                    fail_count += 1

            logger.info("=" * 60)
            logger.info("Sync complete!")
            logger.info(f"  Successfully uploaded: {success_count}")
            logger.info(f"  Already existed (skipped): {skip_count}")
            logger.info(f"  Failed: {fail_count}")
            logger.info("=" * 60)

        # Run async sync
        asyncio.run(sync_all())


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync local images to Firebase Storage"
    )
    parser.add_argument(
        "--images-dir",
        type=str,
        default="images",
        help="Local directory containing images",
    )
    parser.add_argument(
        "--firebase-bucket",
        type=str,
        required=True,
        help="Firebase Storage bucket name",
    )
    parser.add_argument(
        "--firebase-credentials",
        type=str,
        required=True,
        help="Path to Firebase service account JSON file",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip images that already have Firebase URLs",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - validate but don't upload images",
    )

    args = parser.parse_args()

    # Validate images directory exists
    if not Path(args.images_dir).exists():
        logger.error(f"Images directory not found: {args.images_dir}")
        sys.exit(1)

    # Validate Firebase credentials file exists
    if not Path(args.firebase_credentials).exists():
        logger.error(
            f"Firebase credentials file not found: {args.firebase_credentials}"
        )
        sys.exit(1)

    try:
        sync_images_to_firebase(
            images_dir=args.images_dir,
            firebase_bucket=args.firebase_bucket,
            firebase_credentials=args.firebase_credentials,
            resume=args.resume,
            dry_run=args.dry_run,
        )
    except Exception:
        logger.exception("Sync failed")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
