#!/usr/bin/env python3
"""
Find and remove indoor Street View images from the database.

This script identifies images that are indoor photospheres (indicated by having
a person's name in the lower right corner instead of "Google"), moves them to
a separate directory, deletes the corresponding database records, and resets
the bench candidate status to pending.

Usage:
    python tools/remove_indoor_images.py [--dry-run] [--images-dir images] [--indoor-dir images/indoor]
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path

from PIL import Image as PILImage
from PIL import ImageEnhance, ImageFilter


# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


import pytesseract

from bench_finder.config import IMAGES_DIR
from bench_finder.models.enums import BenchCandidateStatus
from bench_finder.models.unified_models import Image
from bench_finder.services.database import BenchDatabase


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def check_ocr_available() -> bool:
    """Check if OCR is available."""
    if pytesseract is None:
        logger.error(
            "pytesseract is not installed. Install it with: pip install pytesseract"
        )
        logger.error("Also install tesseract-ocr: brew install tesseract (on macOS)")
        return False
    try:
        # Test if tesseract is available
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        logger.exception("Tesseract OCR is not available")
        logger.error("Install tesseract-ocr: brew install tesseract (on macOS)")
        return False


def extract_lower_right_corner(
    image_path: str, crop_ratio: float = 0.15
) -> PILImage.Image:
    """
    Extract the lower right corner of an image for copyright text detection.

    Args:
        image_path: Path to the image file
        crop_ratio: Ratio of image to crop (default 0.15 = 15% of width/height)

    Returns:
        PIL Image of the lower right corner
    """
    with PILImage.open(image_path) as img:
        width, height = img.size

        # Calculate crop box (lower right corner)
        crop_width = int(width * crop_ratio)
        crop_height = int(height * crop_ratio)

        left = width - crop_width
        top = height - crop_height
        right = width
        bottom = height

        # Crop the lower right corner
        corner = img.crop((left, top, right, bottom))
        return corner.copy()


def preprocess_image_for_ocr(img: PILImage.Image) -> PILImage.Image:
    """
    Preprocess image to improve OCR accuracy.

    Args:
        img: PIL Image

    Returns:
        Preprocessed PIL Image
    """
    # Convert to grayscale if needed
    if img.mode != "L":
        img = img.convert("L")

    # Enhance contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)

    # Enhance sharpness
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)

    # Apply slight blur to reduce noise
    img = img.filter(ImageFilter.MedianFilter(size=3))

    return img


def detect_copyright_text(image_path: str) -> tuple[bool, str | None]:
    """
    Detect copyright text in the lower right corner of an image.

    Args:
        image_path: Path to the image file

    Returns:
        Tuple of (is_indoor, detected_text)
        - is_indoor: True if person's name detected (not "Google")
        - detected_text: The detected text (or None if no text found)
    """
    if not check_ocr_available():
        return False, None

    try:
        # Extract lower right corner
        corner = extract_lower_right_corner(image_path)

        # Preprocess for OCR
        processed = preprocess_image_for_ocr(corner)

        # Run OCR
        try:
            text = pytesseract.image_to_string(
                processed,
                config="--psm 7",  # Treat image as single text line
            ).strip()
        except Exception as e:
            logger.debug(f"OCR failed for {image_path}: {e}")
            return False, None

        if not text:
            return False, None

        # Normalize text for comparison
        text_lower = text.lower()

        # Check if it contains "Google" (outdoor Street View)
        if "google" in text_lower or "© google" in text_lower:
            return False, text

        # If we have text but it's not Google, it's likely a person's name (indoor)
        # Check for common patterns: person names often have spaces, commas, or "©" symbol
        if len(text) > 2 and ("©" in text or "," in text or " " in text):
            return True, text

        # If text is short and doesn't contain Google, assume it might be indoor
        # But be conservative - only mark as indoor if we're confident
        if len(text) > 5:
            return True, text

        return False, text

    except Exception as e:
        logger.debug(f"Error detecting copyright text in {image_path}: {e}")
        return False, None


def get_relative_path(
    file_path: Path, base_path: Path, project_root: Path | None = None
) -> str:
    """
    Get relative path from project_root if provided, otherwise from base_path.
    Always includes directory structure (e.g., images/filename.jpg not just filename.jpg).

    Args:
        file_path: Path to the file
        base_path: Base path to make relative to (typically images_dir)
        project_root: Optional project root to try first

    Returns:
        Relative path string
    """
    # Try project root first if provided
    if project_root:
        try:
            relative = str(file_path.relative_to(project_root))
            return relative
        except ValueError:
            pass

    # Try base_path - but ensure we include the base directory name
    try:
        relative = str(file_path.relative_to(base_path))
        # If we only got the filename, prepend the base directory name
        if relative == file_path.name:
            # Get the base_path name (e.g., "images")
            base_name = base_path.name
            return f"{base_name}/{relative}"
        return relative
    except ValueError:
        # File is not within base_path, return absolute path
        return str(file_path)


def process_indoor_images(
    dry_run: bool = False,
    images_dir: str | None = None,
    indoor_dir: str | None = None,
    batch_size: int = 100,
) -> None:
    """
    Process images to find and handle indoor Street View images.

    Args:
        dry_run: If True, only report what would be done without making changes
        images_dir: Directory where images are stored (defaults to config IMAGES_DIR)
        indoor_dir: Directory to move indoor images to (defaults to images_dir/indoor)
        batch_size: Number of images to process in each batch
    """
    logger.info("=" * 60)
    logger.info("Indoor Image Detection and Removal")
    logger.info("=" * 60)

    if dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    if not check_ocr_available():
        logger.error("OCR is required but not available. Exiting.")
        sys.exit(1)

    # Set up directories
    project_root_local = Path(__file__).parent.parent
    if images_dir is None:
        images_dir = IMAGES_DIR
    images_path = Path(images_dir)
    if not images_path.is_absolute():
        # Make relative paths absolute relative to project root
        images_path = project_root_local / images_path

    if indoor_dir is None:
        indoor_dir = str(images_path / "indoor")
    indoor_path = Path(indoor_dir)

    if not dry_run:
        indoor_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Indoor images directory: {indoor_path}")
    else:
        logger.info(f"Would create indoor images directory: {indoor_path}")

    # Initialize database
    logger.info("Connecting to database...")
    db = BenchDatabase()

    # Import models
    from bench_finder.models.unified_models import BenchCandidate, ProcessedBench

    # Get all images from database
    with db.get_session() as session:
        images = session.query(Image).filter(Image.filepath.isnot(None)).all()
        logger.info(f"Found {len(images)} images in database with filepaths")

        indoor_images = []
        processed_count = 0
        error_count = 0

        for image in images:
            if not image.filepath:
                continue

            # Check if file exists
            file_path = Path(image.filepath)
            if not file_path.exists():
                # Check if it's relative to images_dir
                if image.filename:
                    file_path = images_path / image.filename
                elif file_path.name:
                    # Try using just the filename from filepath
                    file_path = images_path / file_path.name
                else:
                    logger.debug(f"Image file not found: {image.filepath}")
                    error_count += 1
                    continue

                if not file_path.exists():
                    logger.debug(f"Image file not found: {image.filepath}")
                    error_count += 1
                    continue

            # Ensure file_path is absolute
            file_path = file_path.resolve()

            try:
                # Detect if indoor
                is_indoor, detected_text = detect_copyright_text(str(file_path))

                if is_indoor:
                    relative_path = get_relative_path(
                        file_path, images_path, project_root_local
                    )
                    logger.info(
                        f"Indoor image detected: {relative_path} "
                        f"(text: '{detected_text}')"
                    )
                    indoor_images.append((image, file_path, detected_text))

                processed_count += 1

                if processed_count % batch_size == 0:
                    logger.info(f"Processed {processed_count} images...")

            except Exception as e:
                logger.error(f"Error processing image {image.id}: {e}")
                error_count += 1
                continue

        logger.info(
            f"Processing complete. Processed: {processed_count}, "
            f"Errors: {error_count}, Indoor images found: {len(indoor_images)}"
        )

        if not indoor_images:
            logger.info("No indoor images found. Exiting.")
            return

        # Display summary
        logger.info("\n" + "=" * 60)
        logger.info("Summary of indoor images:")
        logger.info("=" * 60)
        for image, file_path, text in indoor_images:
            relative_path = get_relative_path(
                file_path, images_path, project_root_local
            )
            logger.info(
                f"  - Image ID {image.id}: {relative_path} "
                f"(Bench Candidate ID: {image.bench_candidate_id}, Text: '{text}')"
            )

        if dry_run:
            # Check for ProcessedBench records that would be affected
            deleted_image_ids = [img[0].id for img in indoor_images]
            processed_bench_count = 0
            if deleted_image_ids:
                processed_bench_count = (
                    session.query(ProcessedBench)
                    .filter(ProcessedBench.best_image_id.in_(deleted_image_ids))
                    .count()
                )

            logger.info("\nDRY RUN: Would perform the following actions:")
            logger.info(f"  - Move {len(indoor_images)} images to {indoor_path}")
            logger.info(f"  - Delete {len(indoor_images)} image records from database")
            logger.info(f"  - Update {processed_bench_count} ProcessedBench records")
            logger.info(
                f"  - Reset {len(set(img[0].bench_candidate_id for img in indoor_images))} "
                f"bench candidates to pending status"
            )
            return

        # Process indoor images
        logger.info("\n" + "=" * 60)
        logger.info("Processing indoor images...")
        logger.info("=" * 60)

        moved_count = 0
        deleted_count = 0
        reset_bench_candidates = set()

        for image, file_path, text in indoor_images:
            try:
                # Move image file
                if file_path.exists():
                    dest_path = indoor_path / file_path.name
                    relative_src = get_relative_path(
                        file_path, images_path, project_root_local
                    )
                    relative_dest = get_relative_path(
                        dest_path, images_path, project_root_local
                    )
                    if dest_path.exists():
                        logger.warning(
                            f"Destination file already exists: {relative_dest}, skipping move"
                        )
                    else:
                        shutil.move(str(file_path), str(dest_path))
                        logger.debug(f"Moved {relative_src} to {relative_dest}")
                        moved_count += 1

                # Delete image record from database
                bench_candidate_id = image.bench_candidate_id
                session.delete(image)
                deleted_count += 1
                logger.debug(f"Deleted image record {image.id}")

                # Track bench candidates that need status reset
                reset_bench_candidates.add(bench_candidate_id)

            except Exception as e:
                logger.error(
                    f"Error processing indoor image {image.id} ({file_path}): {e}"
                )
                continue

        # Handle ProcessedBench records that reference deleted images
        deleted_image_ids = [img[0].id for img in indoor_images]
        processed_bench_updated = 0

        if deleted_image_ids:
            # Find ProcessedBench records that reference deleted images
            processed_benches = (
                session.query(ProcessedBench)
                .filter(ProcessedBench.best_image_id.in_(deleted_image_ids))
                .all()
            )

            for processed_bench in processed_benches:
                # Clear the best_image_id and best_detection_id, or delete the record
                # Setting detection_status to "no_bench" since we're removing the best image
                processed_bench.best_image_id = None
                processed_bench.best_detection_id = None
                processed_bench.detection_status = "no_bench"
                processed_bench_updated += 1
                logger.debug(
                    f"Updated ProcessedBench {processed_bench.id} for bench candidate {processed_bench.bench_candidate_id}"
                )

        # Reset bench candidate statuses
        reset_count = 0
        for bench_candidate_id in reset_bench_candidates:
            try:
                bench_candidate = (
                    session.query(BenchCandidate)
                    .filter(BenchCandidate.id == bench_candidate_id)
                    .first()
                )
                if bench_candidate:
                    bench_candidate.status = BenchCandidateStatus.PENDING
                    reset_count += 1
                    logger.debug(
                        f"Reset bench candidate {bench_candidate_id} to pending status"
                    )
            except Exception as e:
                logger.error(
                    f"Error resetting bench candidate {bench_candidate_id}: {e}"
                )

        # Commit all changes
        session.commit()

        logger.info("\n" + "=" * 60)
        logger.info("Processing complete!")
        logger.info("=" * 60)
        logger.info(f"  - Images moved: {moved_count}")
        logger.info(f"  - Image records deleted: {deleted_count}")
        logger.info(f"  - ProcessedBench records updated: {processed_bench_updated}")
        logger.info(f"  - Bench candidates reset: {reset_count}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Find and remove indoor Street View images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only report what would be done without making changes",
    )
    parser.add_argument(
        "--images-dir",
        type=str,
        default=None,
        help=f"Directory where images are stored (default: {IMAGES_DIR})",
    )
    parser.add_argument(
        "--indoor-dir",
        type=str,
        default=None,
        help="Directory to move indoor images to (default: images_dir/indoor)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of images to process before logging progress (default: 100)",
    )

    args = parser.parse_args()

    try:
        process_indoor_images(
            dry_run=args.dry_run,
            images_dir=args.images_dir,
            indoor_dir=args.indoor_dir,
            batch_size=args.batch_size,
        )
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user. Exiting.")
        sys.exit(1)
    except Exception:
        logger.exception("Unexpected error occurred")
        sys.exit(1)


if __name__ == "__main__":
    main()
