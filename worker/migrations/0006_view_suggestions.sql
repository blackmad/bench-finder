-- "Find a better view": a Street View camera someone framed on the site. A
-- moderator's offline run (bench_finder.view_suggestions) renders it into a
-- photo, which then appears in the bench's gallery to be picked.
CREATE TABLE view_suggestions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bench_id INTEGER NOT NULL,
  pano_id TEXT NOT NULL,
  heading REAL NOT NULL,
  pitch REAL NOT NULL,
  fov REAL NOT NULL,
  user_id TEXT NOT NULL,
  display_name TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'rendered', 'failed', 'dismissed')),
  image_id INTEGER,
  error TEXT,
  created_at TEXT NOT NULL,
  resolved_at TEXT
);
CREATE INDEX idx_view_suggestions_state ON view_suggestions (state, created_at);
