"""Unit tests for task 1.5 bug fixes (no network, no model downloads)."""

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from bench_finder import cli
from bench_finder.detection import BenchDetector
from bench_finder.generators.bench_generator import CandidateResult
from bench_finder.models.enums import BenchCandidateStatus, DataSource
from bench_finder.models.unified_models import (
    BenchCandidate,
    DetectionResult,
    Image,
)


# ---------------------------------------------------------------- detection


def _result(has_bench: bool, success: bool = True, error: str | None = None):
    return DetectionResult(
        image_path="x.jpg",
        success=success,
        has_bench=has_bench,
        bench_count=1 if has_bench else 0,
        max_confidence=0.9 if has_bench else 0.0,
        detections=[],
        backend_name="mock",
        model_id="mock-model",
        confidence_threshold=0.5,
        error=error,
    )


def _make_detector(tmp_path, detection_results):
    detector = object.__new__(BenchDetector)
    detector.detection_backend = "mock"
    detector.copy_bench_images = False
    detector.detection_client = MagicMock()
    detector.detection_client.confidence_threshold = 0.5
    detector.detection_client.detect_benches_in_image.side_effect = detection_results

    images = []
    for i in range(len(detection_results)):
        f = tmp_path / f"img{i}.jpg"
        f.write_bytes(b"x")
        images.append(Image(id=i + 1, filepath=str(f), heading=i * 90))

    candidate = SimpleNamespace(
        id=7, provider_id="osm_1", status=BenchCandidateStatus.IMAGE_DOWNLOAD_DONE
    )
    session = MagicMock()

    def query(model):
        q = MagicMock()
        if model is BenchCandidate:
            q.filter.return_value.first.return_value = candidate
        else:
            q.where.return_value.all.return_value = images
        return q

    session.query.side_effect = query
    db = MagicMock()
    db.get_session.return_value.__enter__.return_value = session
    detector.database = db
    detector._calculate_pixel_coverage = lambda r, p: 5.0 if r.has_bench else 0.0
    return detector


def _run(detector):
    bench = CandidateResult(provider_id="osm_1", lat=1.0, lng=2.0, source=DataSource.OSM)
    with (
        patch("bench_finder.detection.display_no_bench_detected"),
        patch("bench_finder.detection.display_bench_detection_results"),
        patch(
            "bench_finder.detection.create_combined_image_display", return_value=None
        ),
        patch("bench_finder.detection.render_detections"),
        patch("bench_finder.detection.AutoImage"),
    ):
        return detector._process_single_bench(bench)


def test_no_bench_does_not_create_detected_bench(tmp_path):
    detector = _make_detector(tmp_path, [_result(False), _result(False)])
    result = _run(detector)
    assert result.bench_detected is False
    detector.database.upsert_detected_bench.assert_not_called()
    # Analysis completed, so the candidate is still marked detection_done
    detector.database.update_bench_candidate_status.assert_called_once_with(
        7, BenchCandidateStatus.DETECTION_DONE
    )


def test_bench_found_creates_detected_bench(tmp_path):
    detector = _make_detector(tmp_path, [_result(False), _result(True)])
    result = _run(detector)
    assert result.bench_detected is True
    detector.database.upsert_detected_bench.assert_called_once()
    assert detector.database.upsert_detected_bench.call_args.kwargs["image_id"] == 2


def test_failed_detection_recorded_as_failure_and_status_not_advanced(tmp_path):
    detector = _make_detector(tmp_path, [_result(False, success=False, error="boom")])
    result = _run(detector)
    saved = detector.database.add_detection.call_args.args[0]
    assert saved.detection_success is False
    assert saved.detection_error == "boom"
    assert result.bench_detected is False
    detector.database.update_bench_candidate_status.assert_not_called()


def test_successful_detection_recorded_as_success(tmp_path):
    detector = _make_detector(tmp_path, [_result(True)])
    _run(detector)
    saved = detector.database.add_detection.call_args.args[0]
    assert saved.detection_success is True
    assert saved.detection_error is None


# --------------------------------------------------------------------- cli


def test_cli_imports_detector_from_package():
    src = inspect.getsource(cli.run_detections)
    assert "from bench_finder.detection import BenchDetector" in src
    assert "from detection import" not in src


def _sql(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


def test_fetch_images_statement_filters_by_search_id():
    sql = _sql(cli._build_fetch_images_statement("pending", force=False, search_id=42))
    assert "search_id = 42" in sql
    assert "status" in sql


def test_fetch_images_statement_force_ignores_status_keeps_search_id():
    sql = _sql(cli._build_fetch_images_statement("pending", force=True, search_id=3))
    assert "search_id = 3" in sql
    assert "bench_candidates.status =" not in sql


def test_fetch_images_statement_without_search_id_has_no_filter():
    sql = _sql(cli._build_fetch_images_statement("pending", search_id=None))
    assert "search_id =" not in sql


def test_fetch_images_statement_invalid_status():
    with pytest.raises(ValueError):
        cli._build_fetch_images_statement("bogus")


def test_fetch_images_command_exposes_search_id_option():
    import re

    from typer.testing import CliRunner

    out = CliRunner().invoke(cli.app, ["fetch-images", "--help"]).output
    # CI terminals get Rich styling: ANSI codes can split the option name.
    assert "--search-id" in re.sub(r"\x1b\[[0-9;]*m", "", out)


# ------------------------------------------------------------------- dedupe


def _c(pid, lat, lng, conf=None):
    return CandidateResult(
        provider_id=pid, lat=lat, lng=lng, source=DataSource.OSM, confidence=conf
    )


def test_dedupe_by_provider_id_even_when_far_apart():
    a = _c("p1", 40.0, -74.0)
    b = _c("p1", 40.01, -74.0)  # ~1 km away, same provider_id
    assert len(cli._deduplicate_bench_candidates([a, b])) == 1


def test_nearby_but_distinct_benches_are_kept():
    # ~5.5 m apart: previously merged by the 10 m rule
    a = _c("p1", 40.0, -74.0)
    b = _c("p2", 40.00005, -74.0)
    assert len(cli._deduplicate_bench_candidates([a, b])) == 2


def test_merge_candidates_closer_than_1_5m_prefers_higher_confidence():
    a = _c("p1", 40.0, -74.0, conf=0.4)
    b = _c("p2", 40.000005, -74.0, conf=0.8)  # ~0.55 m
    assert cli._deduplicate_bench_candidates([a, b]) == [b]


def test_is_better_candidate_has_no_source_branch():
    assert cli._is_better_candidate(_c("p1", 0, 0), _c("p2", 0, 0)) is False


# ------------------------------------------------------------- ultralytics


def test_ultralytics_model_loaded_once(tmp_path):
    from bench_finder.clients.ultralytics_client import UltralyticsClient

    yolo_cls = MagicMock()
    model = MagicMock()
    yolo_cls.return_value = model
    model.return_value = []

    client = object.__new__(UltralyticsClient)
    client.YOLO = yolo_cls
    client.local_model_path = tmp_path / "m.pt"
    client._local_model = None
    client.confidence_threshold = 0.5
    client.iou_threshold = 0.5
    client.image_size = 640
    client._process_local_detection_result = MagicMock(return_value="ok")

    assert client._detect_benches_local("a.jpg") == "ok"
    assert client._detect_benches_local("b.jpg") == "ok"
    assert yolo_cls.call_count == 1
    assert model.call_count == 2
