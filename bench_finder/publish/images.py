"""AVIF + WebP derivative generation with content-hashed names (incremental)."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps


WIDTHS = (400, 800, 1600)
FORMATS = ("avif", "webp")
# Bump to invalidate every derivative when encoder settings change.
ENCODER_SALT = b"v1-avif-q55-webp-q78"
QUALITY = {"avif": 55, "webp": 78}


@dataclass(frozen=True)
class ImageResult:
    """Outcome for one source image. ``widths`` are the real (never upscaled) widths."""

    hash: str
    widths: tuple[int, ...]
    width: int
    height: int
    generated: int  # derivative files actually written (0 when fully cached)


# Hi-res re-cuts (bench_finder.recut) live beside the originals: images/hires/<name>.
HIRES_DIRNAME = "hires"


def hires_path(original: Path) -> Path:
    """Where the hi-res re-cut of ``original`` lives (``<dir>/hires/<same name>``)."""
    return original.parent / HIRES_DIRNAME / original.name


def render_source(original: Path) -> Path:
    """The file to cut renditions from: the hi-res re-cut if present, else the original."""
    hires = hires_path(original)
    try:
        if hires.is_file() and hires.stat().st_size > 0:
            return hires
    except OSError:
        pass
    return original


def content_hash(src: Path) -> str:
    h = hashlib.sha256(ENCODER_SALT)
    with src.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def target_widths(source_width: int) -> tuple[int, ...]:
    """Standard widths <= source; just the native width if smaller than all. Never upscales."""
    widths = tuple(w for w in WIDTHS if w <= source_width)
    return widths if widths else (source_width,)


def derivative_name(digest: str, width: int, fmt: str) -> str:
    return f"img/{digest}-{width}.{fmt}"


def process_image(src: str, out_dir: str) -> ImageResult:
    """Create missing derivatives for ``src`` under ``out_dir/img``; skip existing ones."""
    src_path, out = Path(src), Path(out_dir)
    digest = content_hash(src_path)
    generated = 0
    with Image.open(src_path) as raw:
        img = ImageOps.exif_transpose(raw).convert("RGB")
        sw, sh = img.size
        widths = target_widths(sw)
        (out / "img").mkdir(parents=True, exist_ok=True)
        for w in widths:
            todo = [
                f for f in FORMATS if not (out / derivative_name(digest, w, f)).exists()
            ]
            if not todo:
                continue
            resized = (
                img if w == sw else img.resize((w, round(sh * w / sw)), Image.LANCZOS)
            )
            for fmt in todo:
                dest = out / derivative_name(digest, w, fmt)
                tmp = dest.with_suffix(f"{dest.suffix}.{os.getpid()}.tmp")
                resized.save(tmp, format=fmt.upper(), quality=QUALITY[fmt])
                tmp.replace(dest)
                generated += 1
        top = widths[-1]
        return ImageResult(digest, widths, top, round(sh * top / sw), generated)
