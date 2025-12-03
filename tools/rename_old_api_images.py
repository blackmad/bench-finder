#!/usr/bin/env python3
"""
Rename old format API images to new _api format and update database entries.

Old format: bench_{id}_heading_{heading}.jpg
New format: bench_{id}_heading_{heading}_api.jpg
"""

import logging
import os
import re
import sys
from pathlib import Path


# Add parent directory to path to import bench_finder modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import or_

from bench_finder.config import IMAGES_DIR
from bench_finder.models.enums import ImageSource
from bench_finder.services.database import BenchDatabase


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def find_old_format_images(images_dir: str) -> list[tuple[str, str, str]]:
    """
    Find all images with old format (no source suffix).

    Returns:
        List of tuples: (old_filename, new_filename, bench_id_pattern)
    """
    images_path = Path(images_dir)
    old_format_pattern = re.compile(r"^bench_(\d+)_(node|way)_heading_(\d+)\.jpg$")

    old_images = []
    for image_file in images_path.glob("bench_*_heading_*.jpg"):
        filename = image_file.name

        # Skip if already has a source suffix
        if any(
            suffix in filename
            for suffix in ["_api.jpg", "_streetview.jpg", "_lookaround.jpg"]
        ):
            continue

        match = old_format_pattern.match(filename)
        if match:
            bench_id = match.group(1)
            bench_type = match.group(2)
            heading = match.group(3)

            # Generate new filename with _api suffix
            new_filename = f"bench_{bench_id}_{bench_type}_heading_{heading}_api.jpg"
            old_images.append(
                (filename, new_filename, f"bench_{bench_id}_{bench_type}")
            )

    return old_images


def rename_images_and_update_db(
    images_dir: str, dry_run: bool = False
) -> tuple[int, int]:
    """
    Rename old format API images and update database entries.

    Args:
        images_dir: Directory containing images
        dry_run: If True, only report what would be done without making changes

    Returns:
        Tuple of (files_renamed, db_entries_updated)
    """
    db = BenchDatabase()
    images_path = Path(images_dir)

    old_images = find_old_format_images(images_dir)
    logger.info(f"Found {len(old_images)} images with old format")

    files_renamed = 0
    db_entries_updated = 0

    with db.get_session() as session:
        from bench_finder.models.unified_models import Image

        for old_filename, new_filename, _bench_id_pattern in old_images:
            old_filepath = images_path / old_filename
            new_filepath = images_path / new_filename

            # Check if file exists
            if not old_filepath.exists():
                logger.warning(f"File not found: {old_filepath}")
                continue

            # Check if new filename already exists
            if new_filepath.exists():
                logger.warning(
                    f"Target file already exists: {new_filepath}, skipping {old_filename}"
                )
                continue

            # Find database entries for this image
            # Match by filename or filepath containing the old filename
            from sqlmodel import select

            statement = select(Image).where(
                or_(
                    Image.filename == old_filename,
                    Image.filename == old_filepath.name,
                    Image.filepath.like(f"%{old_filename}"),
                )
            )
            images = list(session.exec(statement).all())

            # Also try to match by pattern if no exact match
            if not images:
                # Extract bench_id and heading from filename
                match = re.match(
                    r"^bench_(\d+)_(node|way)_heading_(\d+)\.jpg$", old_filename
                )
                if match:
                    # Try to find by bench_candidate_id pattern
                    # This is trickier - we need to match bench candidates
                    # For now, let's just update what we can find by filename
                    pass

            # Update database entries
            if images:
                logger.info(f"Found {len(images)} database entries for {old_filename}")
                for image in images:
                    if not dry_run:
                        image.filename = new_filename
                        if image.filepath:
                            # Update filepath to use new filename
                            old_dir = os.path.dirname(image.filepath)
                            image.filepath = os.path.join(old_dir, new_filename)
                        # Set image_source to API if not already set
                        if not image.image_source:
                            image.image_source = ImageSource.STREETVIEW_API
                        db_entries_updated += 1
                    else:
                        logger.info(
                            f"  Would update image ID {image.id}: "
                            f"filename={old_filename} -> {new_filename}, "
                            f"image_source={image.image_source} -> {ImageSource.STREETVIEW_API}"
                        )
            else:
                logger.debug(
                    f"No database entries found for {old_filename}, will still rename file"
                )

            # Rename file
            if not dry_run:
                try:
                    old_filepath.rename(new_filepath)
                    files_renamed += 1
                    logger.info(f"Renamed: {old_filename} -> {new_filename}")
                except Exception:
                    logger.exception(f"Error renaming {old_filename}")
            else:
                logger.info(f"Would rename: {old_filename} -> {new_filename}")

        if not dry_run:
            session.commit()
            logger.info(f"Committed {db_entries_updated} database updates")

    return files_renamed, db_entries_updated


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Rename old format API images to new _api format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--images-dir",
        type=str,
        default=IMAGES_DIR,
        help=f"Directory containing images (default: {IMAGES_DIR})",
    )

    args = parser.parse_args()

    logger.info("Starting image rename migration...")
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    files_renamed, db_entries_updated = rename_images_and_update_db(
        args.images_dir, dry_run=args.dry_run
    )

    logger.info(
        f"Migration complete: {files_renamed} files renamed, "
        f"{db_entries_updated} database entries updated"
    )


if __name__ == "__main__":
    main()
