"""View classifier tests. Everything is mocked: no network, no API keys."""

import io
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from bench_finder.clients import view_classifier as vc
from bench_finder.migrate import migrate


CLAUDE_JSON = {
    "bench_visible": True,
    "bench_visible_confidence": 0.9,
    "bench_type": "backrest",
    "bench_type_confidence": 0.8,
    "view_relation": "back-left",
    "view_relation_confidence": 0.7,
    "occluded": False,
    "quality": 0.75,
    "faces_category": "water",
    "faces_category_confidence": 0.6,
    "faces_text": "the river",
}

ANSWERS = {
    "bench_visible": {"type": "noul", "noul": 0.97, "confidence": 0.97},
    "occluded": {"type": "noul", "noul": 0.1},  # TypeSafe: no confidence field
    "bench_type": {
        "type": "choice",
        "choice": "backrest",
        "probabilities": {"backrest": 0.8, "backless": 0.2},
        "confidence": 0.8,
    },
    "view_relation": {
        "type": "choice",
        "choice": "back",
        "probabilities": {"back": 0.6, "back-left": 0.3, "front": 0.1},
        "confidence": 0.6,
    },
    "faces_category": {
        "type": "choice",
        "choice": "park",
        "probabilities": {"park": 1.0},
        "confidence": 1.0,
    },
    "quality": {"type": "score", "score": 3.0, "confidence": 0.7},
}


@pytest.fixture
def img(tmp_path):
    p = tmp_path / "a.jpg"
    Image.new("RGB", (2000, 1000), "gray").save(p)
    return p


def test_schema_validation():
    with pytest.raises(ValueError):
        vc.ViewLabels(
            bench_visible=True,
            bench_type="x",
            view_relation="back",
            occluded=False,
            quality=0.5,
            faces_category="park",
        )
    with pytest.raises(ValueError):
        vc.ViewLabels(
            bench_visible=True,
            bench_type="other",
            view_relation="back",
            occluded=False,
            quality=1.5,
            faces_category="park",
        )


def test_missing_keys(monkeypatch, img):
    for var in (
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
        "GEMINI_API_KEY",
        "TYPESAFE_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    # Claude without a key falls back to the SDK's own resolution (an
    # `ant auth login` profile), so it has no missing-key error to test.
    with pytest.raises(vc.MissingApiKeyError, match="GEMINI_API_KEY"):
        vc.GeminiViewClassifier().classify(img)
    with pytest.raises(vc.MissingApiKeyError, match="TYPESAFE_API_KEY"):
        vc.TypeSafeViewClassifier().classify(img)


def _msg(data):
    block = SimpleNamespace(type="text", text=json.dumps(data))
    return SimpleNamespace(stop_reason="end_turn", content=[block])


def test_claude_classify_sends_structured_output(img):
    calls = []

    class Messages:
        def create(self, **kw):
            calls.append(kw)
            return _msg(CLAUDE_JSON)

    clf = vc.ClaudeViewClassifier(client=SimpleNamespace(messages=Messages()))
    out = clf.classify(img)
    assert out.view_relation == "back-left"
    assert out.confidence["view_relation"] == 0.7
    assert out.model == "claude-haiku-5-5" and out.faces_text == "the river"
    kw = calls[0]
    assert kw["model"] == "claude-haiku-5-5"
    assert kw["extra_body"]["output_config"]["format"]["type"] == "json_schema"
    assert kw["messages"][0]["content"][0]["source"]["media_type"] == "image/jpeg"


def test_claude_batch_keyed_by_custom_id(img):
    created = {}

    class Batches:
        def create(self, requests):
            created["ids"] = [r["custom_id"] for r in requests]
            return SimpleNamespace(id="b1")

        def retrieve(self, bid):
            return SimpleNamespace(id=bid, processing_status="ended")

        def results(self, bid):
            ok = SimpleNamespace(type="succeeded", message=_msg(CLAUDE_JSON))
            bad = SimpleNamespace(type="errored")
            # reversed order: results must be keyed, not positional
            return [
                SimpleNamespace(custom_id="2", result=bad),
                SimpleNamespace(custom_id="1", result=ok),
            ]

    client = SimpleNamespace(messages=SimpleNamespace(batches=Batches()))
    clf = vc.ClaudeViewClassifier(client=client)
    out = clf.classify_batch([("1", img, None), ("2", img, None)], sleep=lambda s: None)
    assert created["ids"] == ["1", "2"]
    assert out["1"].bench_type == "backrest"
    assert isinstance(out["2"], Exception)


def test_gemini_request_and_parse(img):
    seen = {}

    class Decisions:
        def create(self, **kw):
            seen.update(kw)
            return SimpleNamespace(answers=ANSWERS)

    clf = vc.GeminiViewClassifier(
        client=SimpleNamespace(decisions=Decisions()), resolution="low"
    )
    out = clf.classify(img)
    assert seen["model"] == "gemini-decision-1"
    assert (
        seen["input"][1]["resolution"] == "low" and seen["input"][1]["type"] == "image"
    )
    assert set(seen["questions"]) == {
        "bench_visible",
        "occluded",
        "bench_type",
        "view_relation",
        "faces_category",
        "quality",
    }
    assert out.view_relation == "back" and out.view_relation_probs["back-left"] == 0.3
    assert out.quality == pytest.approx(0.75)  # score 3 of 0..4
    assert out.confidence["occluded"] == pytest.approx(0.9)  # derived max(p, 1-p)
    assert out.occluded is False and out.faces_text is None


def test_typesafe_resizes_and_posts_multipart(tmp_path):
    big = tmp_path / "big.jpg"
    Image.new("RGB", (4000, 3000), "gray").save(big)
    small = tmp_path / "small.jpg"
    Image.new("RGB", (100, 100), "gray").save(small)
    posted = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"model": "jev-1.14.0", "answers": ANSWERS}

    class Session:
        def post(self, url, headers, files, timeout):
            posted.update(url=url, headers=headers, files=files)
            return Resp()

    clf = vc.TypeSafeViewClassifier(api_key="k", session=Session())
    out = clf.classify(big)
    assert posted["headers"]["TypeSafe-Danger-Zone-Images"] == "true"
    body = json.loads(posted["files"]["request"][1])
    assert body["model"] == "jev-1.14.0"
    assert next(iter(body["assets"].values()))["part"] == "photo-file"
    with Image.open(io.BytesIO(posted["files"]["photo-file"][1])) as im:
        assert max(im.size) == 1568
    _, _, size = vc.prepare_image(small, max_side=1568, min_side=280)
    assert min(size) == 280
    assert out.model == "jev-1.14.0"


def test_dry_run_requests_and_cost(img):
    for clf in (
        vc.ClaudeViewClassifier(),
        vc.GeminiViewClassifier(),
        vc.TypeSafeViewClassifier(),
    ):
        req = vc.redact_payload(clf.build_request(img))
        assert "base64 " in json.dumps(req) or clf.model.startswith("jev")
        est = clf.estimate_cost([img, img])
        assert est.images == 2 and est.input_tokens > 0 and est.usd > 0
    assert vc.ClaudeViewClassifier().estimate_cost([img]).usd_batched is not None


def test_persist_upserts_one_row_per_label(tmp_path, img):
    db = str(tmp_path / "t.db")
    migrate(db)
    conn = sqlite3.connect(db)
    conn.execute(
        "INSERT INTO searches (id, query, start_lat, start_lng, search_radius, status, created_at) "
        "VALUES (1,'q',0,0,1,'done','2025-01-01')"
    )
    conn.execute(
        "INSERT INTO bench_candidates (id, search_id, lat, lng, tags, source, status, created_at) "
        "VALUES (1,1,1,1,'{}','overpass','pending','2025-01-01')"
    )
    conn.execute(
        "INSERT INTO images (id, bench_candidate_id, heading, filepath, capture_success, created_at, kind) "
        f"VALUES (1,1,0,'{img}',1,'2025-01-01','legacy')"
    )
    labels = vc.claude_labels_from_json(CLAUDE_JSON, "claude-haiku-5-5")
    n = vc.save_view_labels(conn, 1, labels)
    vc.save_view_labels(conn, 1, labels.model_copy(update={"view_relation": "front"}))
    rows = conn.execute(
        "SELECT label_type, value FROM image_annotations WHERE annotator='claude-haiku-5-5'"
    ).fetchall()
    assert len(rows) == n  # second save updated in place
    assert {r[0]: json.loads(r[1]) for r in rows if isinstance(r[1], str)}[
        "view_relation"
    ] == "front"
    conn.row_factory = sqlite3.Row
    assert vc.select_images(conn, "claude-haiku-5-5", None, Path(".")) == []
    assert len(vc.select_images(conn, "other-model", None, Path("."))) == 1


def test_google_generate_content_structured_output_and_usage(img):
    seen, sleeps = [], []

    class RateLimitError(Exception):
        code = 429

    class Models:
        def generate_content(self, **kw):
            seen.append(kw)
            if len(seen) == 1:
                raise RateLimitError("per minute. Please retry in 2.5s.")
            um = SimpleNamespace(
                prompt_token_count=1700,
                candidates_token_count=200,
                thoughts_token_count=100,
            )
            return SimpleNamespace(text=json.dumps(CLAUDE_JSON), usage_metadata=um)

    usage = vc.Usage()
    clf = vc.GoogleViewClassifier(
        model="gemini-3.8-flash",
        client=SimpleNamespace(models=Models()),
        usage=usage,
        sleep=sleeps.append,
    )
    out = clf.classify(img)
    assert out.view_relation == "back-left" and out.model == "gemini-3.8-flash"
    assert sleeps == [3.5]  # retried after the server's retryDelay
    kw = seen[-1]
    assert kw["model"] == "gemini-3.8-flash"
    assert kw["config"]["response_mime_type"] == "application/json"
    assert kw["config"]["response_json_schema"] is vc.CLAUDE_SCHEMA
    assert kw["config"]["system_instruction"] == vc.CLAUDE_SYSTEM
    part = kw["contents"][0]["parts"][0]["inline_data"]
    assert part["mime_type"] == "image/jpeg" and isinstance(part["data"], bytes)
    assert (usage.calls, usage.input_tokens, usage.output_tokens) == (1, 1700, 300)
    assert usage.usd("gemini-3.8-flash") == pytest.approx(
        (1700 * 0.75 + 300 * 3.75) / 1e6
    )


def test_google_daily_quota_not_retried(img):
    class DailyQuotaError(Exception):
        code = 429

    class Models:
        def generate_content(self, **kw):
            raise DailyQuotaError("GenerateRequestsPerDayPerProjectPerModel-FreeTier")

    clf = vc.GoogleViewClassifier(
        client=SimpleNamespace(models=Models()), sleep=pytest.fail
    )
    with pytest.raises(DailyQuotaError):
        clf.classify(img)


def test_local_ollama_format_schema(img):
    posted = []

    class Resp:
        def __init__(self, status, body):
            self.status_code, self._body, self.text = status, body, json.dumps(body)

        def raise_for_status(self):
            assert self.status_code == 200

        def json(self):
            return self._body

    class Session:
        def post(self, url, json, timeout):
            posted.append((url, dict(json)))
            if "think" in json:
                return Resp(400, {"error": "model does not support think"})
            # some Ollama builds put the structured answer in "thinking"
            return Resp(
                200, {"message": {"content": "", "thinking": _dumps(CLAUDE_JSON)}}
            )

    _dumps = json.dumps
    clf = vc.LocalViewClassifier(model="qwen3-vl:8b", session=Session())
    out = clf.classify(img)
    assert out.model == "qwen3-vl:8b" and out.faces_category == "water"
    url, body = posted[0]
    assert url == "http://localhost:11434/api/chat"
    assert body["format"] is vc.CLAUDE_SCHEMA and body["stream"] is False
    assert body["messages"][0]["content"] == vc.CLAUDE_SYSTEM
    assert len(body["messages"][1]["images"]) == 1
    assert "think" not in posted[1][1]  # retried without the unsupported parameter


def test_make_classifier_new_backends():
    assert (
        vc.make_classifier("google", model="gemini-4-hydrogen").model
        == "gemini-4-hydrogen"
    )
    assert vc.make_classifier("local", model="qwen3-vl:30b").model == "qwen3-vl:30b"
    assert vc.make_classifier("local").estimate_cost(["x"]).usd == 0.0
