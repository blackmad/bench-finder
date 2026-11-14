"""
Indoor/outdoor classification with Places365 (ResNet18).

Moved out of ``tools/remove_indoor_images.py`` so the image pipeline can drop indoor
views at fetch time. ``torch``/``torchvision`` are imported lazily, so importing this
module is cheap.
"""

import logging
import threading
import urllib.request
from pathlib import Path

from PIL import Image as PILImage


logger = logging.getLogger(__name__)


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
    try:
        import torch
        from torchvision import models
    except ImportError as e:
        raise ImportError(
            "torchvision is required for Places365 classification. "
            "Install it with: pip install torchvision"
        ) from e

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
    image: "str | PILImage.Image",
    model,
    category_dict: dict[int, str],
    indoor_outdoor_dict: dict[int, bool],
    device: str = "cpu",
) -> tuple[bool, str, float]:
    """
    Classify if an image is indoor or outdoor using Places365-CNN.

    Args:
        image: Path to the image file, or a PIL image
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

    import torch
    from torchvision import transforms

    try:
        # Load and preprocess image
        if isinstance(image, PILImage.Image):
            img = image.convert("RGB")
        else:
            img = PILImage.open(image).convert("RGB")

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


class IndoorFilter:
    """Lazily loaded, thread-safe indoor/outdoor classifier for freshly rendered views.

    If the model cannot be loaded (no torch, no network for the first weights
    download) the filter disables itself and ``is_indoor`` returns False, so a missing
    classifier never blocks the pipeline.
    """

    def __init__(self, min_confidence: float = 0.5) -> None:
        self.min_confidence = min_confidence
        self._lock = threading.Lock()
        self._loaded = False
        self._disabled = False
        self._model = None
        self._device = "cpu"
        self._categories: dict[int, str] = {}
        self._indoor_map: dict[int, bool] = {}

    def _ensure_loaded(self) -> bool:
        with self._lock:
            if self._loaded:
                return True
            if self._disabled:
                return False
            try:
                (
                    self._model,
                    self._device,
                    self._categories,
                    self._indoor_map,
                ) = load_places365_model()
                self._loaded = True
            except Exception as e:
                logger.warning(f"Indoor filter disabled (Places365 unavailable): {e}")
                self._disabled = True
            return self._loaded

    def is_indoor(self, image: "PILImage.Image") -> tuple[bool, str, float]:
        """Return (is_indoor, top_category, confidence); (False, '', 0.0) if disabled."""
        if not self._ensure_loaded():
            return False, "", 0.0
        with self._lock:  # one forward pass at a time; the model is not thread-safe
            indoor, category, conf = classify_indoor_outdoor_places365(
                image, self._model, self._categories, self._indoor_map, self._device
            )
        return indoor and conf >= self.min_confidence, category, conf
