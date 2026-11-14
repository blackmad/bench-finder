"""Tiny numbered-SQL-migration runner for the SQLite database.

Usage:
    uv run python -m bench_finder.migrate [--db PATH] [--dir migrations]

The database path defaults to $DATABASE_PATH (or data/benches.db). Each
``migrations/NNN_name.sql`` file is applied once, in order, inside a
transaction, and recorded in ``schema_migrations``. Re-running applies nothing.

A database with no ``bench_candidates`` table (brand new) is created from the
SQLModel metadata and every migration is recorded as applied, since the models
already describe the latest schema.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sqlite3
from pathlib import Path


logger = logging.getLogger(__name__)

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "migrations"
_NAME_RE = re.compile(r"^(\d+)_.+\.sql$")


def list_migrations(directory: Path = DEFAULT_DIR) -> list[tuple[str, Path]]:
    """Return ``(version, path)`` sorted by version, where version is the filename stem."""
    return [
        (path.stem, path)
        for path in sorted(directory.glob("*.sql"))
        if _NAME_RE.match(path.name)
    ]


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )


def _is_fresh(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='bench_candidates'"
    ).fetchone()
    return row is None


def migrate(db_path: str, directory: Path = DEFAULT_DIR) -> list[str]:
    """Apply pending migrations; return the versions applied."""
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        _ensure_table(conn)
        migrations = list_migrations(directory)

        if _is_fresh(conn):
            from sqlmodel import SQLModel, create_engine

            import bench_finder.models.unified_models  # noqa: F401

            engine = create_engine(f"sqlite:///{db_path}")
            SQLModel.metadata.create_all(engine)
            engine.dispose()
            for version, _ in migrations:
                conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
                    (version,),
                )
            logger.info(
                "Fresh database created from models; recorded %d migrations",
                len(migrations),
            )
            return []

        done = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
        applied: list[str] = []
        for version, path in migrations:
            if version in done:
                continue
            sql = path.read_text()
            logger.info("Applying %s", version)
            try:
                conn.executescript(
                    "BEGIN;\n"
                    + sql
                    + f"\nINSERT INTO schema_migrations (version) VALUES ('{version}');\nCOMMIT;"
                )
            except Exception:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
            applied.append(version)
        if not applied:
            logger.info("Database up to date; nothing to apply")
        return applied
    finally:
        conn.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.getenv("DATABASE_PATH", "data/benches.db"))
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()
    applied = migrate(args.db, args.dir)
    print(f"Applied {len(applied)} migration(s): {', '.join(applied) or '-'}")


if __name__ == "__main__":
    main()
