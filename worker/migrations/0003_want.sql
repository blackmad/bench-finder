-- "Want to sit here": a per-user wishlist flag next to visited / favorite.
ALTER TABLE user_status ADD COLUMN want INTEGER NOT NULL DEFAULT 0 CHECK (want IN (0, 1));
