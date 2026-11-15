"""Per-view bench classification (Phase 3.1): one interface, five backends.

Every backend answers the same closed-set questions about one image and returns a
:class:`ViewLabels`:

* ``claude``    - Anthropic Messages API, structured output (``output_config.format``),
                  Message Batches for bulk runs keyed by ``custom_id``.
* ``gemini``    - Gemini Decisions API (``gemini-decision-1``) via ``google-genai``;
                  one request per image carrying all questions, per-option probabilities.
* ``typesafe``  - TypeSafe Jev (``jev-1.14.0``) over REST with the
                  ``TypeSafe-Danger-Zone-Images`` header; images are resized to the
                  documented limits first.
* ``google``    - plain Gemini ``generate_content`` (any model id) with the Claude prompt
                  and JSON schema as structured output; token usage tracked for spend caps.
* ``local``     - a local vision model (e.g. ``qwen3-vl:8b``) through Ollama's HTTP API,
                  structured output via ``format`` = the Claude JSON schema.

Documentation status (checked 2026-11-14):

* Gemini: request/response shape, ``client.decisions.create`` and the
  ``noul``/``choice``/``score`` answer fields are taken from
  https://aistudio.google.com/docs/decisions-api. Not verified against an installed SDK
  (google-genai is not a dependency here), see TODO(gemini) markers. Pricing and image
  token counts are NOT published on that page.
* TypeSafe: endpoint, headers, assets, size limits, and noul/choice/score answers are from
  docs.typesafe.ai (images, noul, choice, score, box pages). Image token counts and the
  price are not published; see TODO(typesafe).

No network call happens at import time or in ``build_request`` / ``estimate_cost``.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, Field, field_validator


if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path


BenchType = Literal["backrest", "backless", "picnic", "other"]
ViewRelation = Literal[
    "front",
    "front-left",
    "left",
    "back-left",
    "back",
    "back-right",
    "right",
    "front-right",
    "unknown",
]
FacesCategory = Literal[
    "water",
    "park",
    "residential_street",
    "busy_street",
    "square",
    "courtyard",
    "playground",
    "other",
]

BENCH_TYPES: tuple[str, ...] = ("backrest", "backless", "picnic", "other")
VIEW_RELATIONS: tuple[str, ...] = (
    "front",
    "front-left",
    "left",
    "back-left",
    "back",
    "back-right",
    "right",
    "front-right",
    "unknown",
)
FACES_CATEGORIES: tuple[str, ...] = (
    "water",
    "park",
    "residential_street",
    "busy_street",
    "square",
    "courtyard",
    "playground",
    "other",
)
QUALITY_LEVELS: tuple[str, ...] = (
    "Unusable: bench not identifiable (blur, darkness, extreme distance, blocked).",
    "Poor: bench tiny or heavily obstructed; orientation is a guess.",
    "Fair: bench visible but small, partly hidden or oblique; orientation is probable.",
    "Good: bench clearly visible and large enough to judge orientation.",
    "Excellent: bench large, sharp, unobstructed; orientation is unambiguous.",
)

DEFAULT_CLAUDE_MODEL = "claude-haiku-5-5"
GEMINI_MODEL = "gemini-decision-1"
TYPESAFE_MODEL = "jev-1.14.0"

# Definitions shared by every backend. "Seated person" is the reference frame.
VIEW_RELATION_DESCRIPTIONS: dict[str, str] = {
    "front": "The camera is in front of the bench: a seated person would face the camera.",
    "front-left": "Camera is diagonally in front, on the seated person's left.",
    "left": "Camera is at the side of the bench, on the seated person's left.",
    "back-left": "Camera is diagonally behind the bench, on the seated person's left.",
    "back": "The camera is behind the bench: a seated person would face away from the camera.",
    "back-right": "Camera is diagonally behind the bench, on the seated person's right.",
    "right": "Camera is at the side of the bench, on the seated person's right.",
    "front-right": "Camera is diagonally in front, on the seated person's right.",
    "unknown": "Bench not visible or orientation cannot be judged.",
}
BENCH_TYPE_DESCRIPTIONS: dict[str, str] = {
    "backrest": "A bench with a backrest.",
    "backless": "A bench seat without any backrest.",
    "picnic": "A picnic table with attached or adjacent seating.",
    "other": "Anything else (bench not visible, ledge, stool, etc.).",
}
FACES_DESCRIPTIONS: dict[str, str] = {
    "water": "A canal, river, lake, pond, harbour or fountain.",
    "park": "A park, lawn, trees, garden or other green space.",
    "residential_street": "A quiet residential street: houses or flats, little traffic.",
    "busy_street": "A busy road or shopping street: traffic, trams, shops.",
    "square": "A plaza, pedestrian square or paved open area.",
    "courtyard": "An inner courtyard or the grounds of an apartment complex.",
    "playground": "A playground or sports field.",
    "other": "None of the above (a wall, car park, building entrance, ...).",
}

TASK_TEXT = (
    "The image is a street-level view aimed at one bench (the one at the image centre "
    "unless a box is given). Judge only that bench. 'Left' and 'right' are from the point "
    "of view of a person sitting on the bench and facing out from its seat."
)

# Order and keys of the closed-set questions (used by gemini/typesafe).
Q_BENCH_VISIBLE = "bench_visible"
Q_OCCLUDED = "occluded"
Q_BENCH_TYPE = "bench_type"
Q_VIEW_RELATION = "view_relation"
Q_FACES = "faces_category"
Q_QUALITY = "quality"


class ViewLabels(BaseModel):
    """Schema-valid labels for one view of a bench."""

    bench_visible: bool
    bench_type: BenchType
    view_relation: ViewRelation
    view_relation_probs: dict[str, float] | None = None
    occluded: bool
    quality: float = Field(ge=0.0, le=1.0)
    faces_category: FacesCategory
    faces_text: str | None = None
    confidence: dict[str, float] = Field(default_factory=dict)
    model: str = ""

    @field_validator("faces_text")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return v.strip() or None if v else None

    @field_validator("confidence")
    @classmethod
    def _clip_conf(cls, v: dict[str, float]) -> dict[str, float]:
        return {k: min(1.0, max(0.0, float(x))) for k, x in v.items()}


@dataclass
class ViewContext:
    """Optional hints about the image (never the camera bearing: it would bias the answer)."""

    image_id: int | None = None
    target_box: tuple[float, float, float, float] | None = (
        None  # top, bottom, left, right (0-1)
    )
    extra: dict[str, Any] = field(default_factory=dict)

    def prompt(self) -> str:
        if self.target_box is None:
            return TASK_TEXT
        t, b, left, r = self.target_box
        return (
            f"{TASK_TEXT} The bench of interest is inside the box top={t:.2f}, bottom={b:.2f}, "
            f"left={left:.2f}, right={r:.2f} (fractions of image height/width)."
        )


class MissingApiKeyError(RuntimeError):
    """Raised when the environment variable for a backend is not set."""


def require_key(env_var: str, explicit: str | None = None) -> str:
    key = explicit or os.environ.get(env_var)
    if not key:
        raise MissingApiKeyError(
            f"{env_var} is not set. Export it (or put it in .env) to use this backend; "
            "use --dry-run to inspect requests without a key."
        )
    return key


# --------------------------------------------------------------------------- images


def prepare_image(
    path: str | Path,
    max_side: int = 1568,
    min_side: int = 0,
    fmt: Literal["JPEG", "PNG"] = "JPEG",
) -> tuple[bytes, str, tuple[int, int]]:
    """Return ``(bytes, mime, (w, h))`` after EXIF-upright, RGB, and resize.

    The longest side is scaled to at most ``max_side``; if ``min_side`` is set and the
    shorter side is below it the image is scaled up (never beyond ``max_side``).
    """
    from PIL import Image, ImageOps

    with Image.open(path) as src:
        im = ImageOps.exif_transpose(src).convert("RGB")
        w, h = im.size
        scale = 1.0
        if max(w, h) > max_side:
            scale = max_side / max(w, h)
        if min_side and min(w, h) * scale < min_side:
            scale = min_side / min(w, h)
            if max(w, h) * scale > max_side:
                raise ValueError(
                    f"{path}: aspect ratio {w}x{h} cannot satisfy {min_side}..{max_side} px limits"
                )
        if scale != 1.0:
            im = im.resize(
                (max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS
            )
        buf = io.BytesIO()
        if fmt == "JPEG":
            im.save(buf, "JPEG", quality=90)
            mime = "image/jpeg"
        else:
            im.save(buf, "PNG")
            mime = "image/png"
        return buf.getvalue(), mime, im.size


# --------------------------------------------------------------------------- cost

# $ per 1M tokens (input, output). Claude from the claude-api skill table (cached 2026-11-03).
# Gemini/Jev prices are the figures in docs/RESURRECTION_PLAN.md (secondary sources, unverified).
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
    GEMINI_MODEL: (0.10, 0.0),  # TODO(gemini): confirm at /docs/pricing#gemini-decision
    TYPESAFE_MODEL: (0.084, 0.0),  # TODO(typesafe): confirm price in the models docs
    # generate_content models: aistudio.google.com/docs/pricing (checked 2026-11-14; output
    # includes thinking). 3.8/3.6 Flash double on 2027-01-01, Gemini 4 Argon/Carbon on 2026-12-01.
    "gemini-3.1-flash-lite": (0.25, 1.50),
    "gemini-3.5-flash-lite": (0.30, 2.50),
    "gemini-3.6-flash": (0.75, 3.75),
    "gemini-3.8-flash": (0.75, 3.75),
    "gemini-4-hydrogen": (1.50, 7.50),
    "gemini-4-argon": (2.00, 10.00),
    "gemini-4-carbon": (2.00, 10.00),
    "gemini-2.5-pro": (1.25, 10.00),
}


@dataclass
class CostEstimate:
    model: str
    images: int
    input_tokens: int
    output_tokens: int
    usd: float
    usd_batched: float | None
    notes: str = ""

    def line(self) -> str:
        batch = (
            f", ~${self.usd_batched:.4f} batched"
            if self.usd_batched is not None
            else ""
        )
        return (
            f"{self.model}: {self.images} image(s), ~{self.input_tokens} input + "
            f"~{self.output_tokens} output tokens = ~${self.usd:.4f}{batch}. {self.notes}"
        )


def _estimate(
    model: str,
    sizes: list[tuple[int, int]],
    per_image_text: int,
    out_tokens: int,
    tokens_fn,
    notes,
) -> CostEstimate:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    tin = sum(tokens_fn(w, h) + per_image_text for w, h in sizes)
    tout = out_tokens * len(sizes)
    usd = (tin * pin + tout * pout) / 1e6
    return CostEstimate(
        model,
        len(sizes),
        tin,
        tout,
        usd,
        usd / 2 if model.startswith("claude") else None,
        notes,
    )


# --------------------------------------------------------------------------- interface


class ViewClassifier(Protocol):
    model: str

    def classify(
        self, image_path: str | Path, context: ViewContext | None = None
    ) -> ViewLabels: ...

    def classify_batch(
        self, items: list[tuple[str, str | Path, ViewContext | None]]
    ) -> dict[str, ViewLabels | Exception]: ...

    def build_request(
        self, image_path: str | Path, context: ViewContext | None = None
    ) -> dict: ...

    def estimate_cost(self, image_paths: list[str | Path]) -> CostEstimate: ...


class _BaseClassifier:
    model = ""

    def classify(
        self, image_path, context=None
    ) -> ViewLabels:  # pragma: no cover - abstract
        raise NotImplementedError

    def classify_batch(self, items):
        """Default: sequential, errors captured per key (keys are caller-chosen ids)."""
        out: dict[str, ViewLabels | Exception] = {}
        for key, path, ctx in items:
            try:
                out[key] = self.classify(path, ctx)
            except Exception as e:
                out[key] = e
        return out

    def _sizes(self, paths, **kw) -> list[tuple[int, int]]:
        sizes = []
        for p in paths:
            try:
                _, _, size = prepare_image(p, **kw)
            except Exception:
                size = (1024, 768)
            sizes.append(size)
        return sizes


# --------------------------------------------------------------------------- Claude

CLAUDE_SYSTEM = (
    TASK_TEXT
    + "\n\nField definitions:\n"
    + "view_relation - where the camera is relative to the bench:\n"
    + "\n".join(f"  {k}: {v}" for k, v in VIEW_RELATION_DESCRIPTIONS.items())
    + "\nbench_type:\n"
    + "\n".join(f"  {k}: {v}" for k, v in BENCH_TYPE_DESCRIPTIONS.items())
    + "\nfaces_category - what a person sitting on the bench would be looking at:\n"
    + "\n".join(f"  {k}: {v}" for k, v in FACES_DESCRIPTIONS.items())
    + "\nquality (0-1): how well this image supports judging the bench's orientation "
    + "(0 unusable, 1 excellent)."
    + "\noccluded: true if the bench is substantially hidden by people, cars, plants or objects."
    + "\nfaces_text: short free text (a few words) naming what the bench faces, or null."
    + "\n*_confidence: your probability, 0-1, that the answer is right."
    + "\nIf the bench is not visible, set bench_visible false, view_relation unknown, quality low."
)


def _enum(values) -> dict:
    return {"type": "string", "enum": list(values)}


CLAUDE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "bench_visible": {"type": "boolean"},
        "bench_visible_confidence": {"type": "number"},
        "bench_type": _enum(BENCH_TYPES),
        "bench_type_confidence": {"type": "number"},
        "view_relation": _enum(VIEW_RELATIONS),
        "view_relation_confidence": {"type": "number"},
        "occluded": {"type": "boolean"},
        "quality": {"type": "number"},
        "faces_category": _enum(FACES_CATEGORIES),
        "faces_category_confidence": {"type": "number"},
        "faces_text": {"type": ["string", "null"]},
    },
    "required": [
        "bench_visible",
        "bench_visible_confidence",
        "bench_type",
        "bench_type_confidence",
        "view_relation",
        "view_relation_confidence",
        "occluded",
        "quality",
        "faces_category",
        "faces_category_confidence",
        "faces_text",
    ],
    "additionalProperties": False,
}


def claude_labels_from_json(data: dict[str, Any], model: str) -> ViewLabels:
    conf = {
        k.removesuffix("_confidence"): v
        for k, v in data.items()
        if k.endswith("_confidence")
    }
    return ViewLabels(
        bench_visible=data["bench_visible"],
        bench_type=data["bench_type"],
        view_relation=data["view_relation"],
        occluded=data["occluded"],
        quality=min(1.0, max(0.0, float(data["quality"]))),
        faces_category=data["faces_category"],
        faces_text=data.get("faces_text"),
        confidence=conf,
        model=model,
    )


class ClaudeViewClassifier(_BaseClassifier):
    """Claude via the ``anthropic`` SDK.

    ``output_config`` is sent through ``extra_body`` so this works with any SDK release
    (the installed one may predate the typed parameter). Thinking and effort follow the
    claude-api skill: Haiku 5.5 is adaptive-thinking by default, so effort is pinned low
    for a classification task.
    """

    def __init__(
        self,
        model: str | None = None,
        client: Any = None,
        api_key: str | None = None,
        max_tokens: int = 2000,
        effort: str = "low",
        max_side: int = 1568,
    ):
        self.model = model or os.environ.get(
            "VIEW_CLASSIFIER_CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL
        )
        self._client = client
        self._api_key = api_key
        self.max_tokens = max_tokens
        self.effort = effort
        self.max_side = max_side

    @property
    def client(self):
        if self._client is None:
            import anthropic

            if self._api_key or os.environ.get("ANTHROPIC_API_KEY"):
                self._client = anthropic.Anthropic(
                    api_key=require_key("ANTHROPIC_API_KEY", self._api_key)
                )
            else:  # OpenRouter's Anthropic-compatible endpoint, model ids "anthropic/..."
                self._client = anthropic.Anthropic(
                    api_key=None,
                    auth_token=require_key(
                        "ANTHROPIC_API_KEY (or OPENROUTER_API_KEY)",
                        os.environ.get("OPENROUTER_API_KEY"),
                    ),
                    base_url="https://openrouter.ai/api",
                )
        return self._client

    def _params(self, image_path, context) -> dict:
        data, mime, _ = prepare_image(image_path, max_side=self.max_side)
        ctx = context or ViewContext()
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": CLAUDE_SYSTEM,
            "output_config": {
                "effort": self.effort,
                "format": {"type": "json_schema", "schema": CLAUDE_SCHEMA},
            },
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": base64.standard_b64encode(data).decode(),
                            },
                        },
                        {"type": "text", "text": ctx.prompt() + " Classify this view."},
                    ],
                }
            ],
        }

    def build_request(self, image_path, context=None) -> dict:
        return self._params(image_path, context)

    def _parse(self, message: Any) -> ViewLabels:
        stop = getattr(message, "stop_reason", None)
        if stop in ("refusal", "max_tokens"):
            raise ValueError(f"Claude stopped with {stop}")
        text = next(
            (b.text for b in message.content if getattr(b, "type", "") == "text"), None
        )
        if text is None:
            raise ValueError("Claude response has no text block")
        return claude_labels_from_json(json.loads(text), self.model)

    def classify(self, image_path, context=None) -> ViewLabels:
        p = self._params(image_path, context)
        output_config = p.pop("output_config")
        msg = self.client.messages.create(
            **p, extra_body={"output_config": output_config}
        )
        return self._parse(msg)

    def classify_batch(self, items, poll_seconds: float = 30.0, sleep=time.sleep):
        """Message Batches (50% cost). Results are keyed by ``custom_id`` = the caller's key."""
        requests = []
        out: dict[str, ViewLabels | Exception] = {}
        for key, path, ctx in items:
            try:
                requests.append(
                    {"custom_id": str(key), "params": self._params(path, ctx)}
                )
            except Exception as e:
                out[str(key)] = e
        if not requests:
            return out
        batch = self.client.messages.batches.create(requests=requests)
        while True:
            batch = self.client.messages.batches.retrieve(batch.id)
            if batch.processing_status == "ended":
                break
            sleep(poll_seconds)
        for entry in self.client.messages.batches.results(batch.id):
            rtype = entry.result.type
            if rtype == "succeeded":
                try:
                    out[entry.custom_id] = self._parse(entry.result.message)
                except Exception as e:
                    out[entry.custom_id] = e
            else:
                out[entry.custom_id] = RuntimeError(f"batch item {rtype}")
        return out

    def estimate_cost(self, image_paths) -> CostEstimate:
        sizes = self._sizes(image_paths, max_side=self.max_side)
        sys_tokens = len(CLAUDE_SYSTEM) // 4 + len(json.dumps(CLAUDE_SCHEMA)) // 4 + 40
        return _estimate(
            self.model,
            sizes,
            sys_tokens,
            200,
            lambda w, h: int(w * h / 750),  # documented Claude rule of thumb
            "Local estimate (image ~ w*h/750 tokens); adaptive thinking not included.",
        )


# --------------------------------------------------------------------------- shared questions


def _qs_instruction(text: str) -> str:
    return f"{TASK_TEXT} {text}"


def build_questions() -> dict[str, dict[str, Any]]:
    """Questions in the shape shared by the Decisions API and TypeSafe (noul/choice/score)."""
    return {
        Q_BENCH_VISIBLE: {
            "type": "noul",
            "instructions": _qs_instruction(
                "Is a bench or picnic table clearly visible in the image?"
            ),
        },
        Q_OCCLUDED: {
            "type": "noul",
            "instructions": _qs_instruction(
                "Is the bench substantially hidden by people, vehicles, plants or other objects?"
            ),
        },
        Q_BENCH_TYPE: {
            "type": "choice",
            "instructions": _qs_instruction("What type of bench is it?"),
            "criteria": dict(BENCH_TYPE_DESCRIPTIONS),
        },
        Q_VIEW_RELATION: {
            "type": "choice",
            "instructions": _qs_instruction(
                "From which side of the bench was this photo taken, relative to a person sitting on it?"
            ),
            "criteria": dict(VIEW_RELATION_DESCRIPTIONS),
        },
        Q_FACES: {
            "type": "choice",
            "instructions": _qs_instruction(
                "What would a person sitting on the bench be looking at?"
            ),
            "criteria": dict(FACES_DESCRIPTIONS),
        },
        Q_QUALITY: {
            "type": "score",
            "instructions": _qs_instruction(
                "How well does this image support judging which way the bench faces?"
            ),
            "criteria": list(QUALITY_LEVELS),
        },
    }


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def labels_from_answers(answers: Any, model: str) -> ViewLabels:
    """Build :class:`ViewLabels` from noul/choice/score answers (Gemini and TypeSafe share them).

    Noul answers carry ``noul`` (P(yes)); choice answers carry ``choice``, ``probabilities``
    and ``confidence``; score answers carry ``score`` (0..n-1) and ``confidence``. Noul
    confidence is ``max(p, 1-p)`` when the backend omits it (TypeSafe).
    """

    def noul(key: str) -> tuple[bool, float]:
        a = answers[key]
        p = float(_get(a, "noul"))
        c = _get(a, "confidence")
        return p >= 0.5, float(c) if c is not None else max(p, 1 - p)

    def choice(key: str) -> tuple[str, dict[str, float] | None, float | None]:
        a = answers[key]
        probs = _get(a, "probabilities")
        c = _get(a, "confidence")
        return (
            _get(a, "choice"),
            {k: float(v) for k, v in dict(probs).items()} if probs else None,
            float(c) if c is not None else None,
        )

    visible, c_vis = noul(Q_BENCH_VISIBLE)
    occluded, c_occ = noul(Q_OCCLUDED)
    btype, _, c_type = choice(Q_BENCH_TYPE)
    rel, rel_probs, c_rel = choice(Q_VIEW_RELATION)
    faces, _, c_faces = choice(Q_FACES)
    score = float(_get(answers[Q_QUALITY], "score"))
    c_q = _get(answers[Q_QUALITY], "confidence")
    conf = {
        "bench_visible": c_vis,
        "occluded": c_occ,
        "bench_type": c_type,
        "view_relation": c_rel,
        "faces_category": c_faces,
        "quality": c_q,
    }
    return ViewLabels(
        bench_visible=visible,
        bench_type=btype,
        view_relation=rel,
        view_relation_probs=rel_probs,
        occluded=occluded,
        quality=min(1.0, max(0.0, score / (len(QUALITY_LEVELS) - 1))),
        faces_category=faces,
        faces_text=None,  # closed-set models cannot produce free text
        confidence={k: float(v) for k, v in conf.items() if v is not None},
        model=model,
    )


def _redact(obj: Any) -> Any:
    """Copy of a payload with base64 blobs shortened, for --dry-run printing."""
    if isinstance(obj, dict):
        return {
            k: (
                f"<base64 {len(v)} chars>"
                if k in ("data", "data_base64") and isinstance(v, str)
                else _redact(v)
            )
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact(x) for x in obj]
    return obj


def redact_payload(payload: dict) -> dict:
    return _redact(payload)


# --------------------------------------------------------------------------- Gemini


class GeminiViewClassifier(_BaseClassifier):
    """Gemini Decisions API: ``client.decisions.create(model=..., input=[...], questions={...})``.

    Confirmed from the docs: method name, ``input`` image block (``type``, ``data``,
    ``mime_type``, ``resolution``), question types, ``answers`` shape and ``usage``.
    TODO(gemini): the docs show only ``genai.Client(http_options={"api_version": "v1beta"})``
    reading the key from the environment; passing ``api_key=`` explicitly is the standard
    google-genai constructor argument but is not shown on the Decisions page. The SDK
    (3.2+) is not installed in this repo, so the call path is exercised with a fake client
    only. No batch/caching support exists for this API, so ``classify_batch`` is sequential.
    """

    def __init__(
        self,
        client: Any = None,
        api_key: str | None = None,
        resolution: Literal["low", "medium", "high", "ultra_high"] = "medium",
        max_side: int = 1568,
    ):
        self.model = GEMINI_MODEL
        self._client = client
        self._api_key = api_key
        self.resolution = resolution
        self.max_side = max_side

    @property
    def client(self):
        if self._client is None:
            key = require_key("GEMINI_API_KEY", self._api_key)
            try:
                from google import genai
            except ImportError as e:  # pragma: no cover
                raise RuntimeError(
                    "pip install -U 'google-genai>=3.2' for the gemini backend"
                ) from e
            self._client = genai.Client(
                api_key=key, http_options={"api_version": "v1beta"}
            )
        return self._client

    def build_request(self, image_path, context=None) -> dict:
        data, mime, _ = prepare_image(image_path, max_side=self.max_side)
        ctx = context or ViewContext()
        return {
            "model": self.model,
            "input": [
                {"type": "text", "text": ctx.prompt()},
                {
                    "type": "image",
                    "data": base64.b64encode(data).decode(),
                    "mime_type": mime,
                    "resolution": self.resolution,
                },
            ],
            "questions": build_questions(),
        }

    def classify(self, image_path, context=None) -> ViewLabels:
        req = self.build_request(image_path, context)
        result = self.client.decisions.create(**req)
        return labels_from_answers(_get(result, "answers"), self.model)

    def estimate_cost(self, image_paths) -> CostEstimate:
        sizes = self._sizes(image_paths, max_side=self.max_side)
        qtext = len(json.dumps(build_questions())) // 4 + 40
        # TODO(gemini): image token counts are not published; ~1100 tokens/image is a placeholder.
        return _estimate(
            self.model,
            sizes,
            qtext,
            0,
            lambda w, h: 1100,
            "Image tokens UNKNOWN (placeholder 1100/image, resolution="
            f"{self.resolution}); price $0.10/M input is an announcement figure, output is free.",
        )


# --------------------------------------------------------------------------- TypeSafe

TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
TS_MIN_SIDE, TS_MAX_SIDE = 280, 1568


class TypeSafeViewClassifier(_BaseClassifier):
    """TypeSafe Jev over REST (multipart upload, the recommended path in the docs).

    Confirmed from the docs: URL, bearer auth, ``TypeSafe-Danger-Zone-Images: true``,
    ``assets`` references in ``state``, multipart rules, image limits (PNG/JPEG,
    280-1568 px per side, 16 MiB, not resized server-side), noul/choice/score answers.
    Noul answers have no ``confidence`` field (derived as max(p, 1-p) here).
    TODO(typesafe): image token counts and per-token price are not on the images page.
    TODO(typesafe): the docs examples use ``jev-latest``; ``jev-1.14.0`` appears in
    responses, so it is sent as the model id but unverified as an accepted request value.
    """

    def __init__(
        self,
        model: str = TYPESAFE_MODEL,
        api_key: str | None = None,
        session: Any = None,
    ):
        self.model = model
        self._api_key = api_key
        self._session = session

    def _image(self, image_path) -> tuple[bytes, str, tuple[int, int]]:
        return prepare_image(image_path, max_side=TS_MAX_SIDE, min_side=TS_MIN_SIDE)

    def _request_json(self, ref: str, part: str, context: ViewContext | None) -> dict:
        ctx = context or ViewContext()
        questions = build_questions()
        # The image goes in `state` once; each question refers to it by name.
        for q in questions.values():
            q["instructions"] += " The image is `photo`."
        return {
            "model": self.model,
            "state": {"photo": ref, "task": ctx.prompt()},
            "assets": {ref: {"type": "image", "part": part}},
            "questions": questions,
        }

    def build_request(self, image_path, context=None) -> dict:
        data, mime, _ = self._image(image_path)
        ref, part = "6e1d0b7c-bench-view", "photo-file"
        return {
            "url": TYPESAFE_URL,
            "headers": {
                "Authorization": "Bearer <TYPESAFE_API_KEY>",
                "TypeSafe-Danger-Zone-Images": "true",
            },
            "request": self._request_json(ref, part, context),
            "files": {part: f"<{mime} {len(data)} bytes>"},
        }

    def classify(self, image_path, context=None) -> ViewLabels:
        key = require_key("TYPESAFE_API_KEY", self._api_key)
        data, mime, _ = self._image(image_path)
        ref, part = "6e1d0b7c-bench-view", "photo-file"
        body = self._request_json(ref, part, context)
        if self._session is None:
            import requests

            self._session = requests.Session()
        resp = self._session.post(
            TYPESAFE_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "TypeSafe-Danger-Zone-Images": "true",
            },
            files={
                "request": (None, json.dumps(body), "application/json"),
                part: ("photo.jpg", data, mime),
            },
            timeout=120,
        )
        resp.raise_for_status()
        return labels_from_answers(resp.json()["answers"], self.model)

    def estimate_cost(self, image_paths) -> CostEstimate:
        sizes = self._sizes(image_paths, max_side=TS_MAX_SIDE, min_side=TS_MIN_SIDE)
        qtext = len(json.dumps(build_questions())) // 4 + 40
        # TODO(typesafe): image token count unknown; w*h/750 (Claude's rule) is a placeholder.
        return _estimate(
            self.model,
            sizes,
            qtext,
            0,
            lambda w, h: int(w * h / 750),
            "Image tokens UNKNOWN (placeholder w*h/750); $0.084/M input from a third-party guide.",
        )


# --------------------------------------------------------------------------- Google (generate_content)

DEFAULT_GOOGLE_MODEL = "gemini-3.1-flash-lite"


class Usage:
    """Thread-safe token tally (input, output incl. thinking) for spend tracking."""

    def __init__(self):
        import threading

        self._lock = threading.Lock()
        self.calls = self.input_tokens = self.output_tokens = 0

    def add(self, tin: int, tout: int) -> None:
        with self._lock:
            self.calls += 1
            self.input_tokens += tin
            self.output_tokens += tout

    def usd(self, model: str) -> float:
        pin, pout = PRICES.get(model, (0.0, 0.0))
        return (self.input_tokens * pin + self.output_tokens * pout) / 1e6


class GoogleViewClassifier(_BaseClassifier):
    """Plain Gemini ``models.generate_content`` with the Claude prompt and JSON schema.

    Structured output via ``response_mime_type="application/json"`` +
    ``response_json_schema`` (google-genai >= 1.x accepts a raw JSON schema there,
    including ``["string", "null"]`` types). Thinking is pinned to ``thinking_level`` (low by
    default) because thinking tokens are billed as output. Token usage from
    ``usage_metadata`` is accumulated in ``self.usage`` (shared when passed in) so callers
    can enforce a spend cap.
    """

    def __init__(
        self,
        model: str | None = None,
        client: Any = None,
        api_key: str | None = None,
        thinking_level: str | None = "low",
        max_side: int = 1568,
        usage: Usage | None = None,
        max_retries: int = 8,
        sleep=time.sleep,
    ):
        self.model = model or os.environ.get(
            "VIEW_CLASSIFIER_GOOGLE_MODEL", DEFAULT_GOOGLE_MODEL
        )
        self.max_retries = max_retries
        self._sleep = sleep
        self._client = client
        self._api_key = api_key
        self.thinking_level = thinking_level
        self.max_side = max_side
        self.usage = usage or Usage()

    @property
    def client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client(
                api_key=require_key("GEMINI_API_KEY", self._api_key)
            )
        return self._client

    def _config(self) -> dict:
        cfg: dict[str, Any] = {
            "system_instruction": CLAUDE_SYSTEM,
            "response_mime_type": "application/json",
            "response_json_schema": CLAUDE_SCHEMA,
            "temperature": 0.0,
        }
        if self.thinking_level:
            cfg["thinking_config"] = {"thinking_level": self.thinking_level}
        return cfg

    def build_request(self, image_path, context=None) -> dict:
        data, mime, _ = prepare_image(image_path, max_side=self.max_side)
        ctx = context or ViewContext()
        return {
            "model": self.model,
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"inline_data": {"mime_type": mime, "data": data}},
                        {"text": ctx.prompt() + " Classify this view."},
                    ],
                }
            ],
            "config": self._config(),
        }

    def classify(self, image_path, context=None) -> ViewLabels:
        req = self.build_request(image_path, context)
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.client.models.generate_content(**req)
                break
            except Exception as e:
                msg = str(e)
                code = getattr(e, "code", None)
                # per-minute 429s and 503 "high demand" are transient; daily quotas are not
                transient = (code == 429 and "PerDay" not in msg) or code == 503
                if not transient or attempt == self.max_retries:
                    raise
                m = re.search(r"retry in ([0-9.]+)s", msg)
                self._sleep(float(m.group(1)) + 1 if m else 15.0)
        um = getattr(resp, "usage_metadata", None)
        if um is not None:
            self.usage.add(
                int(getattr(um, "prompt_token_count", 0) or 0),
                int(getattr(um, "candidates_token_count", 0) or 0)
                + int(getattr(um, "thoughts_token_count", 0) or 0),
            )
        text = getattr(resp, "text", None)
        if not text:
            raise ValueError("Gemini response has no text")
        return claude_labels_from_json(json.loads(text), self.model)

    def estimate_cost(self, image_paths) -> CostEstimate:
        n = len(list(image_paths))
        return _estimate(
            self.model,
            [(0, 0)] * n,
            1700,
            300,
            lambda w, h: 0,
            "~1700 input tokens/image (measured order of magnitude) and ~300 output "
            "incl. low thinking; see usage_metadata for actuals.",
        )


# --------------------------------------------------------------------------- local (Ollama)

OLLAMA_URL = "http://localhost:11434"
DEFAULT_LOCAL_MODEL = "qwen3-vl:8b"


class LocalViewClassifier(_BaseClassifier):
    """Local vision model via Ollama's ``/api/chat`` with ``format`` = the Claude JSON schema.

    ``think`` is sent as false (thinking models otherwise spend minutes per image); if the
    model rejects the parameter the request is retried without it.
    """

    def __init__(
        self,
        model: str | None = None,
        url: str | None = None,
        session: Any = None,
        max_side: int = 1568,
        think: bool | None = False,
        timeout: float = 600,
    ):
        self.model = model or os.environ.get(
            "VIEW_CLASSIFIER_LOCAL_MODEL", DEFAULT_LOCAL_MODEL
        )
        self.url = (url or os.environ.get("OLLAMA_HOST") or OLLAMA_URL).rstrip("/")
        if not self.url.startswith("http"):
            self.url = "http://" + self.url
        self._session = session
        self.max_side = max_side
        self.think = think
        self.timeout = timeout

    @property
    def session(self):
        if self._session is None:
            import requests

            self._session = requests.Session()
        return self._session

    def build_request(self, image_path, context=None) -> dict:
        data, _, _ = prepare_image(image_path, max_side=self.max_side)
        ctx = context or ViewContext()
        body: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "format": CLAUDE_SCHEMA,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": CLAUDE_SYSTEM},
                {
                    "role": "user",
                    "content": ctx.prompt() + " Classify this view. Answer in JSON.",
                    "images": [base64.b64encode(data).decode()],
                },
            ],
        }
        if self.think is not None:
            body["think"] = self.think
        return body

    def classify(self, image_path, context=None) -> ViewLabels:
        body = self.build_request(image_path, context)
        resp = self.session.post(
            f"{self.url}/api/chat", json=body, timeout=self.timeout
        )
        if resp.status_code == 400 and "think" in body and "think" in resp.text:
            body.pop("think")
            resp = self.session.post(
                f"{self.url}/api/chat", json=body, timeout=self.timeout
            )
        resp.raise_for_status()
        msg = resp.json()["message"]
        # With think=false some Ollama builds put the structured answer in "thinking".
        content = msg.get("content") or msg.get("thinking") or ""
        if not content.strip():
            raise ValueError("Ollama response has no content")
        return claude_labels_from_json(json.loads(content), self.model)

    def estimate_cost(self, image_paths) -> CostEstimate:
        n = len(list(image_paths))
        return CostEstimate(self.model, n, 0, 0, 0.0, None, "Local model: no API cost.")


BACKENDS = {
    "claude": ClaudeViewClassifier,
    "gemini": GeminiViewClassifier,
    "typesafe": TypeSafeViewClassifier,
    "google": GoogleViewClassifier,
    "local": LocalViewClassifier,
}


def make_classifier(backend: str, model: str | None = None, **kw) -> ViewClassifier:
    if backend not in BACKENDS:
        raise ValueError(f"unknown backend {backend!r}; choose from {sorted(BACKENDS)}")
    if backend in ("claude", "google", "local"):
        return BACKENDS[backend](model=model, **kw)
    if backend == "typesafe" and model:
        return TypeSafeViewClassifier(model=model, **kw)
    return BACKENDS[backend](**kw)


# --------------------------------------------------------------------------- persistence


def _yn(v: bool) -> str:
    return "yes" if v else "no"


def labels_to_rows(labels: ViewLabels) -> list[tuple[str, Any, float | None]]:
    """``(label_type, value, confidence)`` rows. Values match the human labeling vocabulary."""
    c = labels.confidence
    rows: list[tuple[str, Any, float | None]] = [
        ("bench_present", _yn(labels.bench_visible), c.get("bench_visible")),
        ("bench_type", labels.bench_type, c.get("bench_type")),
        ("view_relation", labels.view_relation, c.get("view_relation")),
        ("occluded", labels.occluded, c.get("occluded")),
        ("quality", labels.quality, c.get("quality")),
        ("faces_category", labels.faces_category, c.get("faces_category")),
    ]
    if labels.view_relation_probs:
        rows.append(("view_relation_probs", labels.view_relation_probs, None))
    if labels.faces_text:
        rows.append(("faces_text", labels.faces_text, None))
    return rows


def save_view_labels(
    conn: sqlite3.Connection, image_id: int, labels: ViewLabels
) -> int:
    """Upsert one ``image_annotations`` row per label_type with ``annotator = labels.model``.

    Same update-then-insert pattern as ``bench_finder.labeling.store.save_labels``, which is
    not reused directly because it is fixed to the human annotator and its closed vocabulary
    (no floats, probabilities or per-label confidence).
    """
    if not labels.model:
        raise ValueError("labels.model is empty; it is the annotator id")
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")
    for label_type, value, conf in labels_to_rows(labels):
        payload = json.dumps(value)
        cur = conn.execute(
            "UPDATE image_annotations SET value = ?, confidence = ?, created_at = ? "
            "WHERE image_id = ? AND annotator = ? AND label_type = ?",
            (payload, conf, now, image_id, labels.model, label_type),
        )
        if cur.rowcount == 0:
            conn.execute(
                "INSERT INTO image_annotations (image_id, annotator, label_type, value, confidence, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (image_id, labels.model, label_type, payload, conf, now),
            )
    conn.commit()
    return len(labels_to_rows(labels))


def select_images(
    conn: sqlite3.Connection, annotator: str, limit: int | None, images_root: Path
) -> list[tuple[int, Path, ViewContext]]:
    """Successfully captured images with a readable file and no ``view_relation`` row by ``annotator``."""
    from bench_finder.labeling import store

    has_ann = (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'image_annotations'"
        ).fetchone()
        is not None
    )
    skip = (
        "AND NOT EXISTS (SELECT 1 FROM image_annotations a WHERE a.image_id = i.id "
        "AND a.annotator = ? AND a.label_type = 'view_relation') "
        if has_ann
        else ""
    )
    sql = (
        "SELECT i.id FROM images i WHERE i.capture_success = 1 AND i.filepath IS NOT NULL "
        f"AND i.filepath != '' {skip}ORDER BY i.id"
    )
    out: list[tuple[int, Path, ViewContext]] = []
    for row in conn.execute(sql, (annotator,) if has_ann else ()).fetchall():
        p = store.image_path(conn, row[0], images_root)
        if p is None:
            continue
        out.append((row[0], p, ViewContext(image_id=row[0])))
        if limit is not None and len(out) >= limit:
            break
    return out
