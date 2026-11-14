"""Facing direction, fusion, priors and hero-image selection (Phase 3.3).

Pure functions plus one DB writer. No model calls happen here.

Sign convention (all bearings are compass degrees, clockwise from north)
------------------------------------------------------------------------
``camera_bearing_deg`` is the bearing FROM the camera TO the bench (the direction the
camera looks). ``facing`` is the direction a seated person looks, i.e. out of the seat.

1. Camera sees the BACK of the bench: the camera looks the same way the sitter does,
   so ``facing = bearing + 0``. Camera sees the FRONT: the sitter looks at the camera,
   so ``facing = bearing + 180``.
2. Camera on the sitter's LEFT: the camera stands at ``facing - 90`` from the bench and
   looks back toward it, so ``bearing = facing + 90`` and ``facing = bearing - 90``.
   Right side is the mirror image: ``facing = bearing + 90``.
3. Diagonals sit halfway: back-left -45, back-right +45, front-left -135, front-right +135.

``left``/``right`` are the sitter's left/right, matching the prompts in
``bench_finder.clients.view_classifier``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import sqlite3


# Offset added to camera_bearing_deg to get the facing, per view_relation.
VIEW_OFFSET_DEG: dict[str, float] = {
    "back": 0.0,
    "back-right": 45.0,
    "right": 90.0,
    "front-right": 135.0,
    "front": 180.0,
    "front-left": -135.0,
    "left": -90.0,
    "back-left": -45.0,
}

WIND_DEG: dict[str, float] = {
    name: i * 22.5
    for i, name in enumerate(
        [
            "N",
            "NNE",
            "NE",
            "ENE",
            "E",
            "ESE",
            "SE",
            "SSE",
            "S",
            "SSW",
            "SW",
            "WSW",
            "W",
            "WNW",
            "NW",
            "NNW",
        ]
    )
}
WORD_TO_WIND = {
    "north": "N",
    "northeast": "NE",
    "east": "E",
    "southeast": "SE",
    "south": "S",
    "southwest": "SW",
    "west": "W",
    "northwest": "NW",
}

REAR_RELATIONS = ("back", "back-left", "back-right")
FRONT_RELATIONS = ("front", "front-left", "front-right")
# Types that have a facing; others (backless, picnic, other) only get an axis.
FACING_TYPES = ("backrest",)

DISAGREEMENT_FACING_DEG = 90.0
DISAGREEMENT_AXIS_DEG = 45.0  # axes differ by at most 90, so 90 would never fire
GEOMETRY_TIEBREAK_R = 0.25  # below this VLM resultant length the geometry prior wins


# ----------------------------------------------------------------------------- angles


def normalize_deg(deg: float) -> float:
    return deg % 360.0


def angle_diff(a: float, b: float) -> float:
    """Smallest absolute difference between two bearings, 0..180."""
    d = abs(normalize_deg(a) - normalize_deg(b))
    return min(d, 360.0 - d)


def axis_diff(a: float, b: float) -> float:
    """Smallest difference between two undirected axes, 0..90."""
    d = abs((a % 180.0) - (b % 180.0))
    return min(d, 180.0 - d)


def view_facing(camera_bearing_deg: float, view_relation: str) -> float | None:
    """Facing implied by one view, or ``None`` for ``unknown``/unrecognised relations."""
    off = VIEW_OFFSET_DEG.get(view_relation)
    return None if off is None else normalize_deg(camera_bearing_deg + off)


def parse_osm_direction(value: Any) -> float | None:
    """OSM ``direction`` tag as degrees: ``"90"``, ``"135.5"``, ``"NNE"``, ``"north"``.

    Returns ``None`` for anything else (``forward``/``backward``, ranges, junk).
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        deg = float(s.rstrip("°").strip())
    except ValueError:
        key = s.upper().replace(" ", "")
        key = WORD_TO_WIND.get(s.lower().replace(" ", ""), key)
        return WIND_DEG.get(key)
    return normalize_deg(deg) if math.isfinite(deg) else None


def circular_mean(
    angles_deg: list[float], weights: list[float]
) -> tuple[float, float] | None:
    """Weighted circular mean; returns ``(mean_deg, resultant_length)`` with R in 0..1.

    ``None`` when there is no weight. R = |sum w e^{i theta}| / sum w.
    """
    total = sum(weights)
    if total <= 0:
        return None
    x = sum(
        w * math.cos(math.radians(a)) for a, w in zip(angles_deg, weights, strict=True)
    )
    y = sum(
        w * math.sin(math.radians(a)) for a, w in zip(angles_deg, weights, strict=True)
    )
    r = math.hypot(x, y) / total
    return normalize_deg(math.degrees(math.atan2(y, x))), min(1.0, r)


def axial_mean(
    angles_deg: list[float], weights: list[float]
) -> tuple[float, float] | None:
    """Weighted mean of undirected axes via doubled angles; axis in [0, 180)."""
    res = circular_mean([2.0 * a for a in angles_deg], weights)
    if res is None:
        return None
    mean2, r = res
    return (mean2 / 2.0) % 180.0, r


# ----------------------------------------------------------------------------- inputs


@dataclass
class ViewInput:
    """One classified view, decoupled from the classifier's pydantic model."""

    image_id: int
    camera_bearing_deg: float | None
    view_relation: str
    view_relation_probs: dict[str, float] | None = None
    quality: float = 1.0
    confidence: float | None = None  # model confidence for view_relation, None = 1
    bench_type: str | None = None
    bench_visible: bool = True
    occluded: bool = False
    faces_category: str | None = None
    faces_text: str | None = None
    pano_id: str | None = None

    @classmethod
    def from_labels(
        cls,
        image_id: int,
        camera_bearing_deg: float | None,
        labels: Any,
        pano_id: str | None = None,
    ) -> ViewInput:
        """Build from a ``view_classifier.ViewLabels``."""
        return cls(
            image_id=image_id,
            camera_bearing_deg=camera_bearing_deg,
            view_relation=labels.view_relation,
            view_relation_probs=labels.view_relation_probs,
            quality=labels.quality,
            confidence=labels.confidence.get("view_relation"),
            bench_type=labels.bench_type,
            bench_visible=labels.bench_visible,
            occluded=labels.occluded,
            faces_category=labels.faces_category,
            faces_text=labels.faces_text,
            pano_id=pano_id,
        )

    @property
    def weight(self) -> float:
        """quality x confidence; the distribution case already carries its confidence."""
        if not self.bench_visible or self.camera_bearing_deg is None:
            return 0.0
        conf = 1.0 if self.confidence is None else self.confidence
        return max(0.0, self.quality) * max(0.0, conf)

    @property
    def top_relation(self) -> str:
        if self.view_relation_probs:
            return max(self.view_relation_probs, key=self.view_relation_probs.get)
        return self.view_relation


def _facing_votes(views: list[ViewInput]) -> tuple[list[float], list[float]]:
    """Angles and weights for the fusion. A view with a full distribution votes with every
    non-``unknown`` option (probabilities renormalised); otherwise with its single answer."""
    angles: list[float] = []
    weights: list[float] = []
    for v in views:
        w = v.weight
        if w <= 0 or v.camera_bearing_deg is None:
            continue
        if v.view_relation_probs:
            known = {
                k: p
                for k, p in v.view_relation_probs.items()
                if k in VIEW_OFFSET_DEG and p > 0
            }
            mass = sum(known.values())
            if mass <= 0:
                continue
            for rel, p in known.items():
                angles.append(
                    normalize_deg(v.camera_bearing_deg + VIEW_OFFSET_DEG[rel])
                )
                weights.append(w * p / mass)
        else:
            f = view_facing(v.camera_bearing_deg, v.view_relation)
            if f is not None:
                angles.append(f)
                weights.append(w)
    return angles, weights


# ----------------------------------------------------------------------------- priors


def geometry_prior_check(
    facing_deg: float, prior_bearing_deg: float | None, axis_only: bool = False
) -> tuple[float | None, bool]:
    """Hook for the geometry prior (perpendicular to path / water edge / wall).

    ``prior_bearing_deg`` is precomputed elsewhere (Overpass geometry). Returns
    ``(disagreement_deg, needs_review)``; flagged when >90 deg for a facing, >45 deg for an
    axis (axes can differ by at most 90).
    """
    if prior_bearing_deg is None:
        return None, False
    if axis_only:
        d = axis_diff(facing_deg, prior_bearing_deg)
        return d, d > DISAGREEMENT_AXIS_DEG
    d = angle_diff(facing_deg, prior_bearing_deg)
    return d, d > DISAGREEMENT_FACING_DEG


# ----------------------------------------------------------------------------- hero


def select_hero(
    views: list[ViewInput], backrest: bool | None
) -> tuple[ViewInput | None, str | None]:
    """Backrest benches: best-quality rear view; otherwise (or if none) best front view.

    Falls back to the best-quality visible view. Returns ``(view, hero_reason)``.
    """

    def best(rels: tuple[str, ...] | None) -> ViewInput | None:
        pool = [
            v
            for v in views
            if v.bench_visible and (rels is None or v.top_relation in rels)
        ]
        if not pool:
            return None
        return max(pool, key=lambda v: (v.quality, v.confidence or 0.0, -v.image_id))

    if backrest:
        v = best(REAR_RELATIONS)
        if v:
            return v, "backrest_rear_view"
    v = best(FRONT_RELATIONS)
    if v:
        return v, "backrest_no_rear_best_front" if backrest else "best_front_view"
    v = best(None)
    return (v, "best_quality_fallback") if v else (None, None)


# ----------------------------------------------------------------------------- fusion


@dataclass
class FusedResult:
    facing_deg: float | None = None  # axis in [0, 180) when axis_only
    facing_confidence: float | None = None
    facing_method: str | None = None  # osm_tag | vlm | geometry
    axis_only: bool = False
    bench_type: str | None = None
    backrest: bool | None = None
    faces_category: str | None = None
    faces_text: str | None = None
    hero_image_id: int | None = None
    hero_reason: str | None = None
    embed_pano_id: str | None = None
    embed_heading_deg: float | None = None
    vlm_facing_deg: float | None = None
    disagreement_deg: float | None = None
    needs_review: bool = False
    n_views: int = 0
    notes: list[str] = field(default_factory=list)


def _weighted_vote(items: list[tuple[str | None, float]]) -> str | None:
    tally: dict[str, float] = {}
    for key, w in items:
        if key:
            tally[key] = tally.get(key, 0.0) + w
    return max(tally, key=tally.get) if tally else None


def fuse_views(
    views: list[ViewInput],
    osm_direction: Any = None,
    geometry_prior_deg: float | None = None,
) -> FusedResult:
    """Fuse per-view classifications into one set of bench attributes.

    * bench type: weighted vote (weight = quality x confidence, floor 1e-6 so a lone
      zero-quality view still counts); ``backrest`` iff the winner is ``backrest``.
    * facing: weighted circular mean of ``camera_bearing + offset(view_relation)``
      (full-distribution voting when probabilities exist); confidence = resultant length.
      Non-backrest benches get an axis (doubled-angle mean) and ``axis_only=True``.
    * priors: an OSM ``direction`` tag wins; the geometry prior replaces a VLM facing with
      resultant length < ``GEOMETRY_TIEBREAK_R`` and is otherwise only compared, flagging
      disagreements (>90 deg, or >45 deg for axes) for review.
    * hero image and ``embed_heading_deg`` (= facing) follow.
    """
    out = FusedResult(n_views=len(views))
    visible = [v for v in views if v.bench_visible]
    vote_w = lambda v: max(v.weight, 1e-6)  # noqa: E731
    out.bench_type = _weighted_vote([(v.bench_type, vote_w(v)) for v in visible])
    out.backrest = None if out.bench_type is None else out.bench_type in FACING_TYPES
    out.faces_category = _weighted_vote(
        [(v.faces_category, vote_w(v)) for v in visible]
    )
    texts = [v for v in visible if v.faces_text]
    if texts:
        out.faces_text = max(texts, key=lambda v: v.weight).faces_text

    axis_only = out.backrest is False  # known non-backrest type
    angles, weights = _facing_votes(views)
    est = axial_mean(angles, weights) if axis_only else circular_mean(angles, weights)
    if est is not None:
        out.vlm_facing_deg, r = est
        out.facing_deg, out.facing_confidence = out.vlm_facing_deg, r
        out.facing_method = "vlm"
        out.axis_only = axis_only
    else:
        out.notes.append("no usable view")

    osm = parse_osm_direction(osm_direction)
    if osm is not None:
        if out.vlm_facing_deg is not None:
            d, flag = geometry_prior_check(osm, out.vlm_facing_deg, out.axis_only)
            out.disagreement_deg, out.needs_review = d, flag
            if flag:
                out.notes.append("osm_tag disagrees with vlm")
        out.facing_deg, out.facing_confidence = osm, 1.0
        out.facing_method, out.axis_only = "osm_tag", False
    elif geometry_prior_deg is not None:
        prior = normalize_deg(geometry_prior_deg)
        if out.facing_deg is None or (out.facing_confidence or 0) < GEOMETRY_TIEBREAK_R:
            out.facing_deg, out.facing_confidence = prior, 0.3
            out.facing_method, out.axis_only = "geometry", False
            out.notes.append("geometry prior used")
            out.needs_review = True
        else:
            d, flag = geometry_prior_check(out.facing_deg, prior, out.axis_only)
            out.disagreement_deg, out.needs_review = d, flag
            if flag:
                out.notes.append("geometry prior disagrees with vlm")

    hero, reason = select_hero(views, out.backrest)
    if hero:
        out.hero_image_id, out.hero_reason, out.embed_pano_id = (
            hero.image_id,
            reason,
            hero.pano_id,
        )
    out.embed_heading_deg = None if out.axis_only else out.facing_deg
    return out


# ----------------------------------------------------------------------------- persistence


def write_bench_attributes(
    conn: sqlite3.Connection, bench_candidate_id: int, fused: FusedResult
) -> None:
    """Upsert the ``bench_attributes`` row (unique on ``bench_candidate_id``)."""
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
    conn.execute(
        "INSERT INTO bench_attributes (bench_candidate_id, facing_deg, facing_confidence, "
        "facing_method, axis_only, bench_type, backrest, faces_category, faces_text, "
        "hero_image_id, hero_reason, embed_pano_id, embed_heading_deg, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(bench_candidate_id) DO UPDATE SET "
        "facing_deg=excluded.facing_deg, facing_confidence=excluded.facing_confidence, "
        "facing_method=excluded.facing_method, axis_only=excluded.axis_only, "
        "bench_type=excluded.bench_type, backrest=excluded.backrest, "
        "faces_category=excluded.faces_category, faces_text=excluded.faces_text, "
        "hero_image_id=excluded.hero_image_id, hero_reason=excluded.hero_reason, "
        "embed_pano_id=excluded.embed_pano_id, embed_heading_deg=excluded.embed_heading_deg, "
        "updated_at=excluded.updated_at",
        (
            bench_candidate_id,
            fused.facing_deg,
            fused.facing_confidence,
            fused.facing_method,
            int(fused.axis_only),
            fused.bench_type,
            None if fused.backrest is None else int(fused.backrest),
            fused.faces_category,
            fused.faces_text,
            fused.hero_image_id,
            fused.hero_reason,
            fused.embed_pano_id,
            fused.embed_heading_deg,
            now,
        ),
    )
    conn.commit()
