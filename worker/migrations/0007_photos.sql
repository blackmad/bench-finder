-- Visitors' photos of a bench. Stored in R2 (photos/<uuid>.jpg); shown once a
-- moderator approves them.
CREATE TABLE bench_photos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bench_id INTEGER NOT NULL,
  user_id TEXT NOT NULL,
  display_name TEXT NOT NULL,
  photo_key TEXT NOT NULL UNIQUE,
  width INTEGER NOT NULL,
  height INTEGER NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'visible', 'hidden')),
  created_at TEXT NOT NULL,
  moderated_by TEXT,
  moderated_at TEXT,
  deleted_at TEXT
);
CREATE INDEX idx_bench_photos_bench ON bench_photos (bench_id, state);
CREATE INDEX idx_bench_photos_state ON bench_photos (state, created_at);
