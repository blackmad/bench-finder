-- Moderators choose a bench's lead photo on the site; anyone signed in can suggest one.
-- `photo` is the published gallery entry (urls, urls_webp, width, height) as JSON,
-- so the site can show the pick before the next publish bakes it in.
CREATE TABLE hero_picks (
  bench_id INTEGER PRIMARY KEY,
  image_id INTEGER NOT NULL,
  image_key TEXT NOT NULL,
  photo TEXT NOT NULL,
  picked_by TEXT NOT NULL,
  picked_at TEXT NOT NULL
);

CREATE TABLE hero_suggestions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  bench_id INTEGER NOT NULL,
  image_id INTEGER NOT NULL,
  image_key TEXT NOT NULL,
  photo TEXT NOT NULL,
  user_id TEXT NOT NULL,
  display_name TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'accepted', 'dismissed')),
  created_at TEXT NOT NULL,
  resolved_at TEXT,
  resolved_by TEXT,
  UNIQUE (bench_id, image_id, user_id)
);
CREATE INDEX idx_hero_suggestions_state ON hero_suggestions (state, created_at);

-- Stars given with a note show beside it (and the feed shows them as one line).
ALTER TABLE comments ADD COLUMN rating INTEGER CHECK (rating BETWEEN 1 AND 5);
