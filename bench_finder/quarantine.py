"""One-off data clean-up for the resurrected database (plan task 1.2).

Usage:
    uv run python -m bench_finder.quarantine [--db data/benches.db] [--archive data/archive.db]

What it does, in a single transaction on the main DB:

1. Quarantines (copies to the archive DB, then deletes from the main DB) every
   image row whose location is more than 50 m from its bench_candidate:
   - ``legacy_mapillary_mislinked``: rows with ``image_source IS NULL`` and a
     ``bench_mapillary_<imageid>_<n>_heading_*`` filename. They were created for
     rows of the old ``benches`` table and kept that table's ids as
     ``bench_candidate_id``, so they point at unrelated OSM candidates. The true
     location is ``benches.lat/lng`` (matched by provider_id parsed from the filename).
   - ``pano_gt_50m``: rows with panorama coordinates more than 50 m from the candidate.
   Their detections and detection_items go with them.
2. Deletes duplicate images (same candidate, image_source, panorama position and
   view name; the ``_api/_streetlevel/_streetview`` filename suffix is ignored).
   The row with the most detections is kept, ties broken by the highest id.
   Then deletes duplicate detections (same image, model_id, source,
   confidence_threshold), keeping the highest id.
3. Archives and clears ``processed_benches`` (it is rebuilt by the pipeline).
4. Archives and drops the legacy tables benches, detected_benches,
   clustered_benches, ultralytics_detections.
5. Verifies: no image >50 m from its candidate, no FK violations, rtree in sync.

Idempotent: a second run finds nothing to do. Row counts are logged.
"""

from __future__ import annotations

import argparse
import logging
import math
import re
import sqlite3
from pathlib import Path


logger = logging.getLogger(__name__)

MAX_DISTANCE_M = 50.0
LEGACY_TABLES = [
    "benches",
    "detected_benches",
    "clustered_benches",
    "ultralytics_detections",
]
COUNT_TABLES = [
    "bench_candidates",
    "images",
    "detections",
    "detection_items",
    "processed_benches",
    *LEGACY_TABLES,
]
_MAPI_RE = re.compile(r"^bench_(mapillary_\d+_\d+)_heading")
_SUFFIX_RE = re.compile(r"_(api|streetlevel|streetview)(\.\w+)?$")


def haversine_m(lat1, lng1, lat2, lng2):
    if None in (lat1, lng1, lat2, lng2):
        return None
    p = math.pi / 180
    a = (
        math.sin((lat2 - lat1) * p / 2) ** 2
        + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lng2 - lng1) * p / 2) ** 2
    )
    return 2 * 6371000 * math.asin(math.sqrt(a))


def _norm_filename(name):
    return _SUFFIX_RE.sub("", name or "")


def _mapi_provider(name):
    m = _MAPI_RE.match(name or "")
    return m.group(1) if m else None


def _has_table(conn, schema, name):
    return (
        conn.execute(
            f"SELECT 1 FROM {schema}.sqlite_master WHERE type='table' AND name=?",
            (name,),
        ).fetchone()
        is not None
    )


def _counts(conn):
    return {
        t: conn.execute(f"SELECT COUNT(*) FROM main.{t}").fetchone()[0]
        for t in COUNT_TABLES
        if _has_table(conn, "main", t)
    }


def _archive_rows(conn, table, where_sql):
    """Copy rows of main.<table> matching where_sql into arc.<table> (id-unique)."""
    conn.execute(
        f"CREATE TABLE IF NOT EXISTS arc.{table} AS SELECT * FROM main.{table} WHERE 0"
    )
    cur = conn.execute(
        f"INSERT INTO arc.{table} SELECT * FROM main.{table} WHERE ({where_sql}) "
        f"AND id NOT IN (SELECT id FROM arc.{table})"
    )
    return cur.rowcount


def quarantine(db_path: str, archive_path: str) -> dict:
    conn = sqlite3.connect(db_path, isolation_level=None)
    conn.create_function("haversine_m", 4, haversine_m)
    conn.execute("ATTACH DATABASE ? AS arc", (archive_path,))
    report: dict = {}
    try:
        report["before"] = _counts(conn)
        logger.info("Row counts before: %s", report["before"])
        conn.execute("BEGIN")
        conn.execute(
            "CREATE TEMP TABLE bad_images (image_id INTEGER PRIMARY KEY, reason TEXT, distance_m REAL)"
        )

        # 1a. legacy Mapillary images attached to the wrong candidate
        if _has_table(conn, "main", "benches"):
            legacy = conn.execute(
                "SELECT i.id, i.filename, bc.lat, bc.lng FROM images i "
                "JOIN bench_candidates bc ON bc.id = i.bench_candidate_id "
                "WHERE i.image_source IS NULL AND i.filename LIKE 'bench_mapillary_%'"
            ).fetchall()
            truth = {
                r[0]: (r[1], r[2])
                for r in conn.execute("SELECT provider_id, lat, lng FROM benches")
            }
            for image_id, filename, lat, lng in legacy:
                loc = truth.get(_mapi_provider(filename))
                dist = haversine_m(lat, lng, *loc) if loc else None
                if dist is None or dist > MAX_DISTANCE_M:
                    conn.execute(
                        "INSERT INTO bad_images VALUES (?, 'legacy_mapillary_mislinked', ?)",
                        (image_id, dist),
                    )
        # 1b. panoramas too far from their candidate
        conn.execute(
            "INSERT OR IGNORE INTO bad_images "
            "SELECT i.id, 'pano_gt_50m', haversine_m(i.panorama_lat, i.panorama_lng, bc.lat, bc.lng) "
            "FROM images i JOIN bench_candidates bc ON bc.id = i.bench_candidate_id "
            "WHERE haversine_m(i.panorama_lat, i.panorama_lng, bc.lat, bc.lng) > ?",
            (MAX_DISTANCE_M,),
        )
        report["quarantined_by_reason"] = dict(
            conn.execute(
                "SELECT reason, COUNT(*) FROM bad_images GROUP BY reason"
            ).fetchall()
        )

        conn.execute(
            "CREATE TABLE IF NOT EXISTS arc.image_quarantine "
            "(image_id INTEGER PRIMARY KEY, reason TEXT, distance_m REAL)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO arc.image_quarantine SELECT * FROM bad_images"
        )
        in_bad_img = "SELECT image_id FROM bad_images"
        in_bad_det = f"SELECT id FROM main.detections WHERE image_id IN ({in_bad_img})"
        _archive_rows(conn, "images", f"id IN ({in_bad_img})")
        _archive_rows(conn, "detections", f"id IN ({in_bad_det})")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS arc.detection_items AS SELECT * FROM main.detection_items WHERE 0"
        )
        conn.execute(
            f"INSERT INTO arc.detection_items SELECT * FROM main.detection_items WHERE detection_id IN ({in_bad_det}) "
            "AND id NOT IN (SELECT id FROM arc.detection_items)"
        )
        # processed_benches references images/detections: archive and clear it first.
        if _has_table(conn, "main", "processed_benches"):
            _archive_rows(conn, "processed_benches", "1=1")
            conn.execute("DELETE FROM main.processed_benches")
        conn.execute(
            f"DELETE FROM detection_items WHERE detection_id IN ({in_bad_det})"
        )
        conn.execute(f"DELETE FROM detections WHERE image_id IN ({in_bad_img})")
        conn.execute(f"DELETE FROM images WHERE id IN ({in_bad_img})")
        report["images_quarantined"] = conn.execute(
            "SELECT COUNT(*) FROM bad_images"
        ).fetchone()[0]

        # 2. duplicates
        rows = conn.execute(
            "SELECT i.id, i.bench_candidate_id, i.image_source, i.filename, i.panorama_lat, i.panorama_lng, "
            "(SELECT COUNT(*) FROM detections d WHERE d.image_id = i.id) FROM images i"
        ).fetchall()
        groups: dict = {}
        for iid, cand, src, fn, plat, plng, ndet in rows:
            groups.setdefault((cand, src, _norm_filename(fn), plat, plng), []).append(
                (ndet, iid)
            )
        dup_ids = []
        for members in groups.values():
            if len(members) > 1:
                members.sort()
                dup_ids.extend(i for _, i in members[:-1])
        conn.execute("CREATE TEMP TABLE dup_images (id INTEGER PRIMARY KEY)")
        conn.executemany("INSERT INTO dup_images VALUES (?)", [(i,) for i in dup_ids])
        conn.execute(
            "DELETE FROM detection_items WHERE detection_id IN (SELECT id FROM detections WHERE image_id IN (SELECT id FROM dup_images))"
        )
        conn.execute(
            "DELETE FROM detections WHERE image_id IN (SELECT id FROM dup_images)"
        )
        conn.execute("DELETE FROM images WHERE id IN (SELECT id FROM dup_images)")
        report["duplicate_images_deleted"] = len(dup_ids)

        dup_dets = "SELECT id FROM detections d WHERE id < (SELECT MAX(id) FROM detections x WHERE x.image_id = d.image_id AND x.model_id = d.model_id AND x.source = d.source AND x.confidence_threshold = d.confidence_threshold)"
        report["duplicate_detections_deleted"] = conn.execute(
            f"SELECT COUNT(*) FROM ({dup_dets})"
        ).fetchone()[0]
        conn.execute(f"DELETE FROM detection_items WHERE detection_id IN ({dup_dets})")
        conn.execute(f"DELETE FROM detections WHERE id IN ({dup_dets})")

        # 4. legacy tables
        for table in LEGACY_TABLES:
            if _has_table(conn, "main", table):
                conn.execute(
                    f"CREATE TABLE IF NOT EXISTS arc.{table} AS SELECT * FROM main.{table} WHERE 0"
                )
                conn.execute(f"DELETE FROM arc.{table}")
                conn.execute(f"INSERT INTO arc.{table} SELECT * FROM main.{table}")
                conn.execute(f"DROP TABLE main.{table}")

        # 5. verification
        report["after"] = _counts(conn)
        report["images_over_50m"] = conn.execute(
            "SELECT COUNT(*) FROM images i JOIN bench_candidates bc ON bc.id = i.bench_candidate_id "
            "WHERE haversine_m(i.panorama_lat, i.panorama_lng, bc.lat, bc.lng) > ?",
            (MAX_DISTANCE_M,),
        ).fetchone()[0]
        report["legacy_mapillary_left"] = conn.execute(
            "SELECT COUNT(*) FROM images WHERE image_source IS NULL AND filename LIKE 'bench_mapillary_%'"
        ).fetchone()[0]
        report["fk_violations"] = len(
            conn.execute("PRAGMA foreign_key_check").fetchall()
        )
        if _has_table(conn, "main", "rtree_bench_candidates"):
            report["rtree_rows"] = conn.execute(
                "SELECT COUNT(*) FROM rtree_bench_candidates"
            ).fetchone()[0]
            report["rtree_missing"] = conn.execute(
                "SELECT COUNT(*) FROM bench_candidates WHERE id NOT IN (SELECT id FROM rtree_bench_candidates)"
            ).fetchone()[0]
        if (
            report["images_over_50m"]
            or report["fk_violations"]
            or report.get("rtree_missing")
        ):
            raise RuntimeError(f"Verification failed: {report}")
        conn.execute("COMMIT")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    logger.info("Row counts after: %s", report["after"])
    logger.info(
        "Report: %s", {k: v for k, v in report.items() if k not in ("before", "after")}
    )
    return report


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/benches.db")
    parser.add_argument("--archive", default="data/archive.db")
    args = parser.parse_args()
    Path(args.archive).parent.mkdir(parents=True, exist_ok=True)
    quarantine(args.db, args.archive)


if __name__ == "__main__":
    main()
