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
import urllib.request
from pathlib import Path

import numpy as np
import torch
from PIL import Image as PILImage
from torchvision import transforms


try:
    from torchvision import models

    _TORCHVISION_AVAILABLE = True
except ImportError:
    _TORCHVISION_AVAILABLE = False
    models = None  # type: ignore[assignment]

from term_image.image import AutoImage, ITerm2Image


ITerm2Image.set_render_method("WHOLE")


# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from bench_finder.config import IMAGES_DIR  # noqa: E402
from bench_finder.models.enums import BenchCandidateStatus  # noqa: E402
from bench_finder.models.unified_models import Image  # noqa: E402
from bench_finder.services.database import BenchDatabase  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Reference image slice dimensions
REFERENCE_SLICE_WIDTH = 50
REFERENCE_SLICE_HEIGHT = 15

# Places365 URLs for downloading model and category files
PLACES365_MODEL_URL = (
    "http://places2.csail.mit.edu/models_places365/resnet18_places365.pth.tar"
)
PLACES365_CATEGORIES_URL = "https://raw.githubusercontent.com/CSAILVision/places365/master/categories_places365.txt"
PLACES365_IO_URL = (
    "https://raw.githubusercontent.com/CSAILVision/places365/master/IO_places365.txt"
)

# Cache directory for Places365 files
PLACES365_CACHE_DIR = Path.home() / ".cache" / "places365"
PLACES365_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def extract_reference_slice(
    image_path: str,
    width: int = REFERENCE_SLICE_WIDTH,
    height: int = REFERENCE_SLICE_HEIGHT,
) -> PILImage.Image:
    """
    Extract a fixed-size slice from the lower right corner of a reference image.

    Args:
        image_path: Path to the reference image file
        width: Width of the slice in pixels (default 50)
        height: Height of the slice in pixels (default 15)

    Returns:
        PIL Image of the extracted slice
    """
    with PILImage.open(image_path) as img:
        img_width, img_height = img.size

        # Extract from lower right corner
        left = img_width - width
        top = img_height - height
        right = img_width
        bottom = img_height

        # Crop and resize if needed (in case image is smaller than expected)
        corner = img.crop((left, top, right, bottom))
        if corner.size != (width, height):
            corner = corner.resize((width, height), PILImage.Resampling.LANCZOS)
        return corner.copy()


def extract_corner_slice(
    image_path: str,
    width: int = REFERENCE_SLICE_WIDTH,
    height: int = REFERENCE_SLICE_HEIGHT,
) -> PILImage.Image:
    """
    Extract a fixed-size slice from the lower right corner of an image for comparison.

    Args:
        image_path: Path to the image file
        width: Width of the slice in pixels (default 50)
        height: Height of the slice in pixels (default 15)

    Returns:
        PIL Image of the extracted slice
    """
    return extract_reference_slice(image_path, width, height)


def images_similar(
    img1: PILImage.Image, img2: PILImage.Image, threshold: float = 0.85
) -> tuple[bool, float]:
    """
    Compare two images using structural similarity and mean squared error.

    Args:
        img1: First PIL Image
        img2: Second PIL Image
        threshold: Similarity threshold (0.0 to 1.0, higher = more strict)

    Returns:
        Tuple of (is_similar, similarity_score)
    """
    try:
        from skimage.metrics import structural_similarity as ssim
    except ImportError:
        # Fallback to simpler comparison if scikit-image not available
        logger.warning("scikit-image not available, using basic pixel comparison")
        return _simple_image_comparison(img1, img2, threshold)

    # Convert to numpy arrays
    img1_array = np.array(img1.convert("RGB"))
    img2_array = np.array(img2.convert("RGB"))

    # Calculate structural similarity
    # Use a small window size for small images
    window_size = min(7, min(img1_array.shape[0], img1_array.shape[1]) - 1)
    if window_size < 3:
        # Image too small, use simple comparison
        return _simple_image_comparison(img1, img2, threshold)

    try:
        similarity_result = ssim(
            img1_array,
            img2_array,
            win_size=window_size,
            channel_axis=2 if len(img1_array.shape) == 3 else None,
            data_range=255,
            full=False,
        )
        # ssim can return just a float or a tuple, handle both
        similarity = (
            float(similarity_result[0])
            if isinstance(similarity_result, tuple)
            else float(similarity_result)
        )
        return (similarity >= threshold, similarity)
    except Exception:
        # Fallback to simple comparison on error
        return _simple_image_comparison(img1, img2, threshold)


def _simple_image_comparison(
    img1: PILImage.Image, img2: PILImage.Image, threshold: float = 0.85
) -> tuple[bool, float]:
    """
    Simple pixel-based comparison using mean squared error.

    Args:
        img1: First PIL Image
        img2: Second PIL Image
        threshold: Similarity threshold (0.0 to 1.0)

    Returns:
        Tuple of (is_similar, similarity_score)
    """
    # Convert to arrays
    arr1 = np.array(img1.convert("RGB"))
    arr2 = np.array(img2.convert("RGB"))

    # Calculate mean squared error
    mse = np.mean((arr1.astype(float) - arr2.astype(float)) ** 2)
    # Convert MSE to similarity score (0 = identical, higher = more different)
    # For 255 max value, max MSE is 255^2 = 65025
    max_mse = 65025.0
    similarity = 1.0 - (mse / max_mse)
    similarity = float(max(0.0, min(1.0, float(similarity))))  # Clamp to [0, 1]

    return (similarity >= threshold, similarity)


def download_file(url: str, dest_path: Path) -> None:
    """Download a file from URL to destination path."""
    if dest_path.exists():
        logger.debug(f"File already exists: {dest_path}")
        return

    logger.info(f"Downloading {url} to {dest_path}...")
    try:
        urllib.request.urlretrieve(url, dest_path)
        logger.info(f"Downloaded {dest_path.name}")
    except Exception as e:
        raise RuntimeError(f"Failed to download {url}: {e}") from e


def load_places365_categories() -> tuple[dict[int, str], dict[int, bool]]:
    """
    Load Places365 category labels and indoor/outdoor mappings.

    Returns:
        Tuple of (category_dict, indoor_outdoor_dict)
        - category_dict: Maps category index to category name
        - indoor_outdoor_dict: Maps category index to True (indoor) or False (outdoor)
    """
    categories_file = PLACES365_CACHE_DIR / "categories_places365.txt"
    io_file = PLACES365_CACHE_DIR / "IO_places365.txt"

    # Download category file if needed
    if not categories_file.exists():
        download_file(PLACES365_CATEGORIES_URL, categories_file)

    # Download indoor/outdoor file if needed
    if not io_file.exists():
        download_file(PLACES365_IO_URL, io_file)

    # Load categories (format: "0 /a/abbey" -> extract "abbey" by removing first 3 chars)
    category_dict = {}
    with open(categories_file) as class_file:
        for idx, line in enumerate(class_file):
            parts = line.strip().split(" ")
            if parts:
                # Extract category name by removing first 3 characters (e.g., "/a/")
                category_name = parts[0][3:] if len(parts[0]) > 3 else parts[0]
                category_dict[idx] = category_name

    # Load indoor/outdoor labels
    # Format: "0 1" where 1=indoor, 2=outdoor, so we subtract 1 to get 0=indoor, 1=outdoor
    indoor_outdoor_dict = {}
    with open(io_file) as f:
        for idx, line in enumerate(f):
            items = line.rstrip().split()
            if len(items) >= 2:
                # items[-1] is 1 or 2, subtract 1 to get 0 (indoor) or 1 (outdoor)
                io_label = int(items[-1]) - 1
                indoor_outdoor_dict[idx] = io_label == 0  # 0 = indoor, 1 = outdoor

    logger.info(f"Loaded {len(category_dict)} Places365 categories")
    return category_dict, indoor_outdoor_dict


def load_places365_model():
    """
    Load Places365-CNN model (ResNet18 trained on Places365 dataset).

    Returns:
        Tuple of (model, device, category_dict, indoor_outdoor_dict)

    Raises:
        ImportError: If torchvision is not available
        RuntimeError: If model cannot be loaded
    """
    if not _TORCHVISION_AVAILABLE or models is None:
        raise ImportError(
            "torchvision is required for Places365 classification. "
            "Install it with: pip install torchvision"
        )

    try:
        device = "cuda" if torch.cuda.is_available() else "cpu"

        # Load Places365 categories
        category_dict, indoor_outdoor_dict = load_places365_categories()

        # Create ResNet18 architecture
        model = models.resnet18(num_classes=365)  # Places365 has 365 categories

        # Download and load Places365 weights
        weights_file = PLACES365_CACHE_DIR / "resnet18_places365.pth.tar"
        if not weights_file.exists():
            download_file(PLACES365_MODEL_URL, weights_file)

        # Load the state dict (Places365 format uses checkpoint['state_dict'])
        checkpoint = torch.load(weights_file, map_location=lambda storage, loc: storage)

        # Remove 'module.' prefix if present (from DataParallel)
        state_dict = {
            str.replace(k, "module.", ""): v
            for k, v in checkpoint["state_dict"].items()
        }

        _ = model.load_state_dict(state_dict, strict=False)
        model.eval()
        model.to(device)

        logger.info(f"Loaded Places365 ResNet18 model (device: {device})")
        return model, device, category_dict, indoor_outdoor_dict

    except Exception as e:
        raise RuntimeError(f"Failed to load Places365 model: {e}") from e


def classify_indoor_outdoor_places365(
    image_path: str,
    model,
    category_dict: dict[int, str],
    indoor_outdoor_dict: dict[int, bool],
    device: str = "cpu",
) -> tuple[bool, str, float]:
    """
    Classify if an image is indoor or outdoor using Places365-CNN.

    Args:
        image_path: Path to the image file
        model: Places365 model (required)
        category_dict: Dictionary mapping category index to category name
        indoor_outdoor_dict: Dictionary mapping category index to indoor (True) or outdoor (False)
        device: Device to run model on ('cpu' or 'cuda')

    Returns:
        Tuple of (is_indoor, category_name, confidence)
        - is_indoor: True if indoor, False if outdoor
        - category_name: Top predicted category name
        - confidence: Confidence score of top prediction
    """
    if model is None:
        raise ValueError("Places365 model is required")

    try:
        # Load and preprocess image
        img = PILImage.open(image_path).convert("RGB")

        # Places365 preprocessing
        transform = transforms.Compose(
            [
                transforms.Resize((256, 256)),
                transforms.CenterCrop(224),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
                ),
            ]
        )

        img_tensor = transform(img)  # Returns torch.Tensor
        # Type check: transform always returns Tensor, not Image
        assert isinstance(img_tensor, torch.Tensor), "Transform should return Tensor"
        img_tensor = img_tensor.unsqueeze(0).to(device)

        # Run inference
        with torch.no_grad():
            outputs = model(img_tensor)
            probabilities = torch.nn.functional.softmax(outputs[0], dim=0)
            top_prob, top_idx = torch.topk(probabilities, 5)  # Get top 5 predictions

            # Get top prediction
            top_idx_val = int(top_idx[0].item())
            top_prob_val = float(top_prob[0].item())

            # Map to category name and indoor/outdoor
            category_name = category_dict.get(top_idx_val, f"unknown_{top_idx_val}")
            is_indoor = indoor_outdoor_dict.get(top_idx_val, False)

            return is_indoor, category_name, top_prob_val

    except Exception:
        logger.exception("Error classifying image with Places365")
        raise


def detect_indoor_by_pixel_comparison(
    image_path: str,
    reference_slice: PILImage.Image,
    similarity_threshold: float = 0.85,
    return_slice: bool = False,
) -> tuple[bool, float, PILImage.Image | None]:
    """
    Detect if an image is indoor by comparing its corner slice to a reference "Google" slice.

    Args:
        image_path: Path to the image file to check
        reference_slice: Reference PIL Image slice containing "Google" logo
        similarity_threshold: Threshold for similarity (default 0.85)
        return_slice: If True, also return the extracted slice

    Returns:
        Tuple of (is_indoor_candidate, similarity_score, corner_slice)
        - is_indoor_candidate: True if different from reference (potentially indoor), False if similar (outdoor)
        - similarity_score: Similarity score (0.0 to 1.0)
        - corner_slice: The extracted corner slice (if return_slice=True, else None)
    """
    try:
        # Extract the same slice from the candidate image
        candidate_slice = extract_corner_slice(image_path)

        # Compare with reference
        is_similar, similarity = images_similar(
            reference_slice, candidate_slice, similarity_threshold
        )

        # If similar to reference (Google), it's outdoor
        # If different from reference, it might be indoor (needs second check)
        is_indoor_candidate = not is_similar

        return (
            is_indoor_candidate,
            similarity,
            candidate_slice if return_slice else None,
        )

    except Exception as e:
        logger.debug(f"Error comparing image {image_path}: {e}")
        return False, 0.0, None


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
    reference_image: str | None = None,
    similarity_threshold: float = 0.85,
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

    # Load reference image slice (Google logo from outdoor Street View)
    if reference_image:
        reference_image_path = Path(reference_image)
        if not reference_image_path.is_absolute():
            reference_image_path = images_path / reference_image
    else:
        # Default reference image
        reference_image_path = images_path / "bench_3373237632_node_heading_0.jpg"

    if not reference_image_path.exists():
        logger.error(f"Reference image not found: {reference_image_path}")
        logger.error(
            "Please ensure the reference image exists to extract the 'Google' slice"
        )
        logger.error(
            "You can specify a different reference image with --reference-image"
        )
        sys.exit(1)

    logger.info(f"Loading reference slice from: {reference_image_path}")
    try:
        reference_slice = extract_reference_slice(str(reference_image_path))
        logger.info(
            f"Extracted reference slice: {reference_slice.size[0]}x{reference_slice.size[1]} pixels"
        )
    except Exception:
        logger.exception("Failed to extract reference slice")
        sys.exit(1)

    # Load Places365 model for second validation (required)
    logger.info("Loading Places365-CNN model for indoor/outdoor classification...")
    try:
        places365_model, device, category_dict, indoor_outdoor_dict = (
            load_places365_model()
        )
        logger.info("Places365 model loaded successfully")
    except (ImportError, RuntimeError):
        logger.exception("Failed to load Places365 model")
        logger.warning(
            "Places365 is required for this script. Please install torchvision."
        )
        sys.exit(1)

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
                # Step 1: Detect if different from reference using pixel comparison
                is_indoor_candidate, similarity_score, _corner_slice = (
                    detect_indoor_by_pixel_comparison(
                        str(file_path),
                        reference_slice,
                        similarity_threshold=similarity_threshold,
                        return_slice=True,
                    )
                )

                if is_indoor_candidate:
                    # Step 2: Verify with Places365-CNN
                    relative_path = get_relative_path(
                        file_path, images_path, project_root_local
                    )

                    # Run second check with Places365 (required)
                    is_indoor_confirmed, category_name, classification_confidence = (
                        classify_indoor_outdoor_places365(
                            str(file_path),
                            places365_model,
                            category_dict,
                            indoor_outdoor_dict,
                            device,
                        )
                    )

                    # Only mark as indoor if BOTH checks pass:
                    # 1. Pixel comparison says it's different from reference (indoor candidate)
                    # 2. Scene classification confirms it's indoor
                    is_indoor = is_indoor_candidate and (is_indoor_confirmed is True)

                    if is_indoor:
                        logger.info(
                            f"Indoor image detected: {relative_path} "
                            f"(pixel similarity: {similarity_score:.3f}, Places365 category: {category_name}, confidence: {classification_confidence:.3f})"
                        )

                        # Display the full image using termimage
                        if file_path.exists():
                            try:
                                # Load image as PIL Image first, then pass to AutoImage
                                pil_img = PILImage.open(str(file_path))
                                term_img = AutoImage(pil_img)
                                print(term_img)
                            except Exception as e:
                                logger.debug(
                                    f"Could not display image in terminal: {e}"
                                )
                        else:
                            logger.debug(f"Image file does not exist: {file_path}")

                        indoor_images.append(
                            (
                                image,
                                file_path,
                                similarity_score,
                                classification_confidence,
                            )
                        )
                    elif is_indoor_candidate:
                        logger.debug(
                            f"Pixel comparison flagged {relative_path} but Places365 classification says outdoor "
                            f"(similarity: {similarity_score:.3f}, Places365 category: {category_name}, confidence: {classification_confidence:.3f})"
                        )

                processed_count += 1

                if processed_count % batch_size == 0:
                    logger.info(f"Processed {processed_count} images...")

            except Exception:
                logger.exception(f"Error processing image {image.id}")
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
        logger.info(f"\n{'=' * 60}")
        logger.info("Summary of indoor images:")
        logger.info("=" * 60)
        for (
            image,
            file_path,
            similarity_score,
            classification_confidence,
        ) in indoor_images:
            relative_path = get_relative_path(
                file_path, images_path, project_root_local
            )
            logger.info(
                f"  - Image ID {image.id}: {relative_path} "
                f"(Bench Candidate ID: {image.bench_candidate_id}, "
                f"Pixel Similarity: {similarity_score:.3f}, "
                f"Scene Confidence: {classification_confidence:.3f})"
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
                f"  - Reset {len({img[0].bench_candidate_id for img in indoor_images})} "
                f"bench candidates to pending status"
            )
            return

        # Process indoor images
        logger.info(f"\n{'=' * 60}")
        logger.info("Processing indoor images...")
        logger.info("=" * 60)

        moved_count = 0
        deleted_count = 0
        reset_bench_candidates = set()

        for (
            image,
            file_path,
            _similarity_score,
            _classification_confidence,
        ) in indoor_images:
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

            except Exception:
                logger.exception(
                    f"Error processing indoor image {image.id} ({file_path})"
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
            except Exception:
                logger.exception(
                    f"Error resetting bench candidate {bench_candidate_id}"
                )

        # Commit all changes
        session.commit()

        logger.info(f"\n{'=' * 60}")
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
    parser.add_argument(
        "--reference-image",
        type=str,
        default=None,
        help="Path to reference image containing 'Google' logo (default: images/bench_3373237632_node_heading_0.jpg)",
    )
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.85,
        help="Similarity threshold for pixel comparison (0.0 to 1.0, default: 0.85)",
    )

    args = parser.parse_args()

    try:
        process_indoor_images(
            dry_run=args.dry_run,
            images_dir=args.images_dir,
            indoor_dir=args.indoor_dir,
            batch_size=args.batch_size,
            reference_image=args.reference_image,
            similarity_threshold=args.similarity_threshold,
        )
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user. Exiting.")
        sys.exit(1)
    except Exception:
        logger.exception("Unexpected error occurred")
        sys.exit(1)


if __name__ == "__main__":
    main()
