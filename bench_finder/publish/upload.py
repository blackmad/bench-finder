"""Upload a publish directory to Cloudflare R2 (S3-compatible). Only new/changed objects."""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Any


IMMUTABLE = "public, max-age=31536000, immutable"
MANIFEST_CACHE = "public, max-age=60"
MUTABLE_CACHE = "public, max-age=300"
_TYPES = {
    ".avif": "image/avif",
    ".webp": "image/webp",
    ".geojson": "application/geo+json",
    ".json": "application/json",
}


def make_client() -> tuple[Any, str]:
    """Build a boto3 client for R2 from env. Raises KeyError naming a missing variable."""
    import boto3

    account = os.environ["R2_ACCOUNT_ID"]
    client = boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )
    return client, os.environ["R2_BUCKET"]


def cache_control(key: str) -> str:
    if key == "manifest.json":
        return MANIFEST_CACHE
    if key.startswith(("img/", "data/benches.")):
        return IMMUTABLE  # content-hashed names
    return MUTABLE_CACHE  # data/bench/<id>.json keeps its name


def _existing(client: Any, bucket: str) -> dict[str, str]:
    found: dict[str, str] = {}
    token = None
    while True:
        kw: dict[str, Any] = {"Bucket": bucket}
        if token:
            kw["ContinuationToken"] = token
        resp = client.list_objects_v2(**kw)
        for obj in resp.get("Contents", []):
            found[obj["Key"]] = obj.get("ETag", "").strip('"')
        if not resp.get("IsTruncated"):
            return found
        token = resp["NextContinuationToken"]


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()


_IMG_REF = re.compile(r"img/[0-9a-f]{16}-\d+\.(?:avif|webp|jpg)")


def live_keys(out_dir: Path) -> set[str]:
    """Every key the current publish uses: the manifest, its GeoJSON, the bench
    files, and the images those name. Anything else in ``out_dir`` or the bucket
    is a leftover from an earlier publish."""
    manifest = json.loads((out_dir / "manifest.json").read_text())
    data = manifest.get("data_base", "data")
    geo = f"{data}/{manifest['benches']}"
    keys = {"manifest.json", geo}
    texts = [(out_dir / geo).read_text()]
    for p in (out_dir / data / manifest.get("bench_dir", "bench")).glob("*.json"):
        keys.add(p.relative_to(out_dir).as_posix())
        texts.append(p.read_text())
    for t in texts:
        keys.update(_IMG_REF.findall(t))
    return keys


def prune_remote(client: Any, bucket: str, live: set[str], existing: set[str]) -> int:
    """Delete bucket objects the current publish no longer uses (approved by the
    owner 2026-11-16). Refuses when the live set looks broken."""
    stale = sorted(k for k in existing if k not in live)
    n_json = sum(k.endswith(".json") for k in live)
    if n_json < 100 or not any(k.endswith(".geojson") for k in live):
        raise RuntimeError("live set looks incomplete; not pruning")
    if len(stale) > 0.8 * len(existing):
        raise RuntimeError(f"would delete {len(stale)} of {len(existing)}; not pruning")
    for i in range(0, len(stale), 1000):
        client.delete_objects(
            Bucket=bucket,
            Delete={
                "Objects": [{"Key": k} for k in stale[i : i + 1000]],
                "Quiet": True,
            },
        )
    return len(stale)


def upload_dir(
    out_dir: Path, client: Any, bucket: str, *, prune: bool = True
) -> dict[str, int]:
    """Upload the files the current publish uses; skip hashed objects already
    present and mutable ones whose ETag equals the local md5. ``manifest.json``
    goes last so readers never see a manifest pointing at missing files. Then,
    with ``prune``, delete bucket objects no longer used.
    """
    existing = _existing(client, bucket)
    live = live_keys(out_dir)
    # Read now: a later publish may rewrite manifest.json while this runs.
    manifest_bytes = (out_dir / "manifest.json").read_bytes()
    files = sorted(out_dir / k for k in live if (out_dir / k).is_file())
    files.sort(key=lambda p: p.relative_to(out_dir).as_posix() == "manifest.json")
    uploaded = skipped = 0
    for path in files:
        key = path.relative_to(out_dir).as_posix()
        cc = cache_control(key)
        if key in existing and (cc == IMMUTABLE or existing[key] == _md5(path)):
            skipped += 1
            continue
        ctype = (
            _TYPES.get(path.suffix)
            or mimetypes.guess_type(key)[0]
            or "application/octet-stream"
        )
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=manifest_bytes if key == "manifest.json" else path.read_bytes(),
            ContentType=ctype,
            CacheControl=cc,
        )
        uploaded += 1
    pruned = prune_remote(client, bucket, live, set(existing)) if prune else 0
    return {"uploaded": uploaded, "skipped": skipped, "pruned": pruned}


LOCK = Path("data/upload.lock")


def wait_for_uploads() -> None:
    """Block until no background upload holds the lock (a publish calls this
    before rewriting the output directory)."""
    import fcntl

    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)


def start_background(out_dir: Path, log: Path = Path("data/upload.log")) -> int:
    """Upload ``out_dir`` in a detached process; returns its pid."""
    import subprocess
    import sys

    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as fh:
        p = subprocess.Popen(
            [sys.executable, "-m", "bench_finder.publish.upload", str(out_dir)],
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    return p.pid


def main() -> None:
    """``python -m bench_finder.publish.upload OUT_DIR``: one upload at a time."""
    import fcntl
    import sys
    import time

    import bench_finder.config  # noqa: F401 - loads .env (R2_* keys)

    out_dir = Path(sys.argv[1])
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        t0 = time.time()
        print(f"{time.strftime('%F %T')} upload {out_dir} started", flush=True)
        client, bucket = make_client()
        stats = upload_dir(out_dir, client, bucket)
        print(
            f"{time.strftime('%F %T')} done in {time.time() - t0:.0f}s: {stats}",
            flush=True,
        )


if __name__ == "__main__":
    main()
