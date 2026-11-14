"""Upload a publish directory to Cloudflare R2 (S3-compatible). Only new/changed objects."""

from __future__ import annotations

import hashlib
import mimetypes
import os
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from pathlib import Path


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


def upload_dir(out_dir: Path, client: Any, bucket: str) -> dict[str, int]:
    """Upload files under ``out_dir``; skip hashed objects already present and mutable
    ones whose ETag equals the local md5. ``manifest.json`` goes last so readers never
    see a manifest pointing at missing files.
    """
    existing = _existing(client, bucket)
    files = sorted(
        p for p in out_dir.rglob("*") if p.is_file() and not p.name.endswith(".tmp")
    )
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
            Body=path.read_bytes(),
            ContentType=ctype,
            CacheControl=cc,
        )
        uploaded += 1
    return {"uploaded": uploaded, "skipped": skipped}
