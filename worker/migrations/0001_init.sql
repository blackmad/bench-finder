-- Bench Finder user-generated data. Bench ids are the integer bench_candidates.id
-- from the local pipeline database; benches themselves are NOT stored in D1.
-- user_id is the Firebase uid (JWT `sub`). Timestamps are ISO-8601 UTC strings.

CREATE TABLE ratings (
  bench_id   INTEGER NOT NULL,
  user_id    TEXT    NOT NULL,
  rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  created_at TEXT    NOT NULL,
  updated_at TEXT    NOT NULL,
  PRIMARY KEY (bench_id, user_id)
);
CREATE INDEX idx_ratings_user ON ratings (user_id);

CREATE TABLE user_status (
  bench_id   INTEGER NOT NULL,
  user_id    TEXT    NOT NULL,
  visited    INTEGER NOT NULL DEFAULT 0 CHECK (visited IN (0, 1)),
  favorite   INTEGER NOT NULL DEFAULT 0 CHECK (favorite IN (0, 1)),
  created_at TEXT    NOT NULL,
  updated_at TEXT    NOT NULL,
  PRIMARY KEY (bench_id, user_id)
);
CREATE INDEX idx_user_status_user ON user_status (user_id);

-- Comments are public. state: visible (published), flagged (published but queued
-- for moderation after a user flag), hidden (removed by a moderator).
-- deleted_at is the author's soft delete.
CREATE TABLE comments (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  bench_id     INTEGER NOT NULL,
  user_id      TEXT    NOT NULL,
  display_name TEXT    NOT NULL DEFAULT 'Anonymous',
  body         TEXT    NOT NULL,
  state        TEXT    NOT NULL DEFAULT 'visible' CHECK (state IN ('visible', 'flagged', 'hidden')),
  created_at   TEXT    NOT NULL,
  deleted_at   TEXT,
  moderated_by TEXT,
  moderated_at TEXT
);
CREATE INDEX idx_comments_bench ON comments (bench_id, created_at);
CREATE INDEX idx_comments_state ON comments (state);
CREATE INDEX idx_comments_user ON comments (user_id);

-- Reports of a bad detection on an existing bench. user_id is NULL for anonymous
-- reports. No IP address is stored.
CREATE TABLE bench_reports (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  bench_id    INTEGER NOT NULL,
  reason      TEXT    NOT NULL CHECK (reason IN ('not_a_bench', 'wrong_location', 'wrong_facing', 'bad_image', 'other')),
  note        TEXT,
  photo_key   TEXT,
  user_id     TEXT,
  status      TEXT    NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'resolved', 'dismissed')),
  admin_notes TEXT,
  created_at  TEXT    NOT NULL,
  resolved_at TEXT,
  resolved_by TEXT
);
CREATE INDEX idx_bench_reports_status ON bench_reports (status, created_at);
CREATE INDEX idx_bench_reports_bench ON bench_reports (bench_id);

-- Reports of a bench that is not on the map.
CREATE TABLE missing_bench_reports (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  lat             REAL    NOT NULL CHECK (lat BETWEEN -90 AND 90),
  lng             REAL    NOT NULL CHECK (lng BETWEEN -180 AND 180),
  note            TEXT,
  photo_key       TEXT,
  accuracy_meters REAL,
  user_id         TEXT,
  status          TEXT    NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'resolved', 'dismissed')),
  admin_notes     TEXT,
  created_at      TEXT    NOT NULL,
  resolved_at     TEXT,
  resolved_by     TEXT
);
CREATE INDEX idx_missing_reports_status ON missing_bench_reports (status, created_at);

-- Fixed-window rate limiting counters (see src/rate-limit.ts). Purged opportunistically.
CREATE TABLE rate_limits (
  key          TEXT PRIMARY KEY,
  window_start INTEGER NOT NULL,
  count        INTEGER NOT NULL
);
CREATE INDEX idx_rate_limits_window ON rate_limits (window_start);
