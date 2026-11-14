import sqlite3

from bench_finder.migrate import list_migrations, migrate


def test_fresh_db_is_created_from_models_and_marks_migrations_applied(tmp_path):
    db = str(tmp_path / "fresh.db")
    assert migrate(db) == []
    conn = sqlite3.connect(db)
    versions = {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}
    assert versions == {v for v, _ in list_migrations()}
    cols = {r[1] for r in conn.execute("PRAGMA table_info(images)")}
    assert {"pano_id", "kind", "camera_bearing_deg"} <= cols
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
    assert {"image_annotations", "bench_attributes"} <= tables
    assert migrate(db) == []


def test_pending_migrations_apply_once(tmp_path):
    mdir = tmp_path / "m"
    mdir.mkdir()
    (mdir / "001_a.sql").write_text("SELECT 1;")
    (mdir / "002_b.sql").write_text("CREATE TABLE t (x INTEGER);")
    db = str(tmp_path / "old.db")
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE bench_candidates (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    assert migrate(db, mdir) == ["001_a", "002_b"]
    assert migrate(db, mdir) == []
