-- A missing-bench report can say where the bench shows in a street panorama:
-- the City of Amsterdam's panoramas (picked in the dialog) or a pasted Google
-- Street View link. heading is the compass bearing from the panorama to the bench.
ALTER TABLE missing_bench_reports ADD COLUMN pano_source  TEXT CHECK (pano_source IN ('amsterdam', 'google'));
ALTER TABLE missing_bench_reports ADD COLUMN pano_id      TEXT;
ALTER TABLE missing_bench_reports ADD COLUMN pano_heading REAL CHECK (pano_heading >= 0 AND pano_heading < 360);
ALTER TABLE missing_bench_reports ADD COLUMN pano_url     TEXT;
