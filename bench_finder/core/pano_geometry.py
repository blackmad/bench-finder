"""
Pure geometry and selection helpers for aimed bench views.

Nothing here touches the network or the database, so everything is unit-testable
with synthetic data.

Conventions
-----------
* Compass bearings are degrees clockwise from north, 0-360.
* ``bearing`` of a panorama candidate is the bearing from the camera *to the bench*.
* An equirectangular panorama is described by ``center_compass_deg``: the compass
  bearing of the middle column of the image. Columns to the right of the middle are
  clockwise (east of north-facing) from it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np


# Enumeration / selection parameters (docs/RESURRECTION_PLAN.md task 2.1)
MAX_PANO_DISTANCE_M = 30.0
MIN_PANO_DISTANCE_M = 4.0
MAX_VIEWS_PER_BENCH = 6
NUM_BEARING_SECTORS = 6
MIN_FILL_SEPARATION_DEG = 20.0
OLD_PANO_YEAR = 2016

# View extraction parameters (task 2.2)
OUTPUT_SIZE_PX = 1024
FOV_MIN_DEG = 40.0
FOV_MAX_DEG = 90.0
BENCH_HALF_WIDTH_M = 3.0
# A panorama may be up to 15% narrower than the ideal width for the output size.
ZOOM_TOLERANCE = 0.85

EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlmb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial compass bearing from point 1 to point 2, 0-360 (0 = north)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlmb = math.radians(lon2 - lon1)
    y = math.sin(dlmb) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(
        dlmb
    )
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def angular_diff_deg(a: float, b: float) -> float:
    """Smallest absolute difference between two bearings, 0-180."""
    d = abs(a - b) % 360.0
    return 360.0 - d if d > 180.0 else d


def fov_for_distance(distance_m: float) -> float:
    """FOV so that a +-3 m wide scene around the bench fills the frame.

    ``clamp(2 * atan(3 m / d), 40 deg, 90 deg)``.
    """
    d = max(distance_m, 1e-6)
    fov = math.degrees(2.0 * math.atan(BENCH_HALF_WIDTH_M / d))
    return min(FOV_MAX_DEG, max(FOV_MIN_DEG, fov))


@dataclass
class PanoCandidate:
    """A panorama near a bench, with the geometry needed to choose among them."""

    pano_id: str
    lat: float
    lon: float
    distance_m: float
    bearing_deg: float  # camera -> bench
    source: str  # "google" or "apple"
    year: int | None = None
    month: int | None = None
    date_str: str | None = None
    is_third_party: bool = False
    is_indoor_meta: bool = False  # building-level metadata (inside a building)
    raw: Any = field(default=None, repr=False, compare=False)  # library pano object

    @property
    def date_ord(self) -> int:
        """Sortable date; 0 when unknown (sorts as oldest)."""
        if self.year is None:
            return 0
        return self.year * 12 + (self.month or 1)


def filter_candidates(
    cands: list[PanoCandidate],
    *,
    min_distance_m: float = MIN_PANO_DISTANCE_M,
    max_distance_m: float = MAX_PANO_DISTANCE_M,
    old_year: int = OLD_PANO_YEAR,
) -> list[PanoCandidate]:
    """Apply the 2.1 drop rules.

    Drops: distance outside [min, max], third-party, indoor metadata, and pre-``old_year``
    panoramas when at least one panorama from ``old_year`` or later remains.
    Duplicate pano ids are collapsed.
    """
    seen: set[str] = set()
    kept: list[PanoCandidate] = []
    for c in cands:
        if c.pano_id in seen:
            continue
        seen.add(c.pano_id)
        if c.distance_m < min_distance_m or c.distance_m > max_distance_m:
            continue
        if c.is_third_party or c.is_indoor_meta:
            continue
        kept.append(c)

    if any(c.year is not None and c.year >= old_year for c in kept):
        kept = [c for c in kept if c.year is not None and c.year >= old_year]
    return kept


def _preference_key(c: PanoCandidate) -> tuple[int, float]:
    """Newest first, then closest."""
    return (-c.date_ord, c.distance_m)


def select_views(
    cands: list[PanoCandidate],
    *,
    max_views: int = MAX_VIEWS_PER_BENCH,
    num_sectors: int = NUM_BEARING_SECTORS,
    min_fill_separation_deg: float = MIN_FILL_SEPARATION_DEG,
) -> list[PanoCandidate]:
    """Pick up to ``max_views`` panoramas spread across camera->bench bearing sectors.

    Pass 1 takes the preferred (newest, then nearest) panorama of each sector. Pass 2
    fills remaining slots with the next-preferred panoramas that are at least
    ``min_fill_separation_deg`` away in bearing from everything already chosen, so
    repeated captures of the same spot do not crowd out other angles.
    """
    if not cands or max_views <= 0:
        return []
    width = 360.0 / num_sectors
    by_sector: dict[int, list[PanoCandidate]] = {}
    for c in cands:
        by_sector.setdefault(int((c.bearing_deg % 360.0) // width), []).append(c)

    chosen = [min(group, key=_preference_key) for group in by_sector.values()]
    chosen.sort(key=_preference_key)
    chosen = chosen[:max_views]

    if len(chosen) < max_views:
        chosen_ids = {c.pano_id for c in chosen}
        for c in sorted(cands, key=_preference_key):
            if len(chosen) >= max_views:
                break
            if c.pano_id in chosen_ids:
                continue
            if all(
                angular_diff_deg(c.bearing_deg, o.bearing_deg)
                >= min_fill_separation_deg
                for o in chosen
            ):
                chosen.append(c)
                chosen_ids.add(c.pano_id)

    chosen.sort(key=lambda c: c.bearing_deg)
    return chosen


def choose_zoom(
    widths_by_zoom: list[int],
    fov_deg: float,
    out_px: int = OUTPUT_SIZE_PX,
    tolerance: float = ZOOM_TOLERANCE,
) -> int:
    """Lowest zoom level whose panorama gives about ``out_px`` px across ``fov_deg``.

    "About" means at least ``tolerance`` (default 85%) of the ideal width.

    ``widths_by_zoom[i]`` is the panorama width at zoom ``i`` (lowest to highest).
    Falls back to the highest level when none is wide enough.
    """
    if not widths_by_zoom:
        return 0
    needed = out_px * 360.0 / fov_deg * tolerance
    for zoom, width in enumerate(widths_by_zoom):
        if width >= needed:
            return zoom
    return len(widths_by_zoom) - 1


def google_center_compass(heading_rad: float | None) -> float:
    """Compass bearing of the middle column of a Google panorama image.

    This is streetlevel's ``heading`` in degrees. Verified empirically: on 42 aimed
    views over Amsterdam, a COCO bench detector found a bench near the frame centre in
    9 views with ``+heading`` versus 3 with ``-heading`` (and 1-3 for the 180 degree
    variants), so the opposite sign that the GPano export suggests is wrong here.
    """
    if heading_rad is None:
        return 0.0
    return math.degrees(heading_rad) % 360.0


def ccw_to_cw_heading(ccw_heading_deg: float) -> float:
    """Convert a heading measured counter-clockwise from north to clockwise."""
    return (360.0 - ccw_heading_deg) % 360.0


def apple_center_compass(heading_rad: float | None) -> float:
    """Compass bearing of the middle column of a stitched Apple Look Around equirect.

    The streetlevel heading is CCW from north and is the direction of travel; the
    stitched image is centred on the inverse direction of travel (looking backwards).
    Verified by rendering an Apple pano and the nearest Google pano at bearings
    0/90/180/270: the four view pairs show the same scene.
    """
    if heading_rad is None:
        return 0.0
    travel_cw = ccw_to_cw_heading(math.degrees(heading_rad))
    return (travel_cw + 180.0) % 360.0


def render_aimed_view(
    equirect: np.ndarray,
    *,
    center_compass_deg: float,
    aim_bearing_deg: float,
    fov_deg: float,
    out_size: int = OUTPUT_SIZE_PX,
    pitch_rad: float = 0.0,
    roll_rad: float = 0.0,
) -> np.ndarray:
    """Render a square rectilinear view from an equirectangular panorama.

    The virtual camera looks horizontally at compass bearing ``aim_bearing_deg``
    (the horizon is at the vertical centre). ``pitch_rad`` / ``roll_rad`` are the
    panorama's pose angles as streetlevel reports them (GPano PosePitch/PoseRoll):
    the tilt of the capture rig. The view is levelled by applying the inverse, which
    makes the horizon straight in the output. Verified on an Apple panorama with a
    20 degree pose pitch (only the inverse levels it); Google uses the same fields.
    Zero tilt is an exact no-op.

    Args:
        equirect: H x W x 3 uint8 image covering 360 x 180 degrees.
    """
    h, w = equirect.shape[:2]
    c = (out_size - 1) / 2.0
    f = c / math.tan(math.radians(fov_deg) / 2.0)

    # Camera frame relative to the panorama centre: x = right, y = forward, z = up.
    rel = math.radians((aim_bearing_deg - center_compass_deg + 180.0) % 360.0 - 180.0)
    fwd = np.array([math.sin(rel), math.cos(rel), 0.0])
    right = np.array([math.cos(rel), -math.sin(rel), 0.0])
    up = np.array([0.0, 0.0, 1.0])

    xs = np.arange(out_size, dtype=np.float64) - c
    ys = c - np.arange(out_size, dtype=np.float64)
    gx, gy = np.meshgrid(xs, ys)
    rays = (
        f * fwd[None, None, :]
        + gx[..., None] * right[None, None, :]
        + gy[..., None] * up[None, None, :]
    )

    if pitch_rad or roll_rad:
        # Level the panorama: undo the rig pose (pitch about the right axis, roll about forward).
        cp, sp = math.cos(-pitch_rad), math.sin(-pitch_rad)
        cr, sr = math.cos(-roll_rad), math.sin(-roll_rad)
        rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
        ry = np.array([[cr, 0, sr], [0, 1, 0], [-sr, 0, cr]])
        rays = np.einsum("hwj,ij->hwi", rays, ry @ rx)

    x, y, z = rays[..., 0], rays[..., 1], rays[..., 2]
    az = np.arctan2(x, y)  # 0 at centre, positive to the right
    lat = np.arctan2(z, np.hypot(x, y))
    map_x = ((0.5 + az / (2 * math.pi)) * w - 0.5).astype(np.float32)
    map_y = ((0.5 - lat / math.pi) * h - 0.5).astype(np.float32)
    return cv2.remap(
        equirect,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_WRAP,
    )
