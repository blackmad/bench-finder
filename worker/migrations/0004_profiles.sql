-- Public favourites pages (opt-in) and the order of a user's favourites.
-- A page is addressed by its random slug (/u/<slug>) or, once chosen, by the
-- user's handle (/u/<handle>); a handle may never equal any slug, and new
-- slugs never equal a handle, so one lookup by either is unambiguous.
CREATE TABLE profiles (
  user_id      TEXT    PRIMARY KEY,
  slug         TEXT    NOT NULL UNIQUE,
  handle       TEXT    UNIQUE,
  display_name TEXT    NOT NULL,
  public       INTEGER NOT NULL DEFAULT 0 CHECK (public IN (0, 1)),
  created_at   TEXT    NOT NULL,
  updated_at   TEXT    NOT NULL
);

-- fav_rank: the user's order (NULL = unranked, after the ranked ones, newest
-- first). favorited_at: when the bench became a favourite (the homepage feed).
ALTER TABLE user_status ADD COLUMN fav_rank INTEGER;
ALTER TABLE user_status ADD COLUMN favorited_at TEXT;
UPDATE user_status SET favorited_at = updated_at WHERE favorite = 1;
CREATE INDEX idx_user_status_favorited ON user_status (favorited_at) WHERE favorite = 1;
CREATE INDEX idx_ratings_updated ON ratings (updated_at);
CREATE INDEX idx_comments_created ON comments (created_at);
