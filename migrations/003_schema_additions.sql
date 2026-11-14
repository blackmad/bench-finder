-- 1.4: aimed-view metadata on images/detection_items, plus image_annotations and bench_attributes.
ALTER TABLE images ADD COLUMN pano_id TEXT;
ALTER TABLE images ADD COLUMN pano_date TEXT;
ALTER TABLE images ADD COLUMN camera_bearing_deg REAL;
ALTER TABLE images ADD COLUMN camera_distance_m REAL;
ALTER TABLE images ADD COLUMN fov_deg REAL;
ALTER TABLE images ADD COLUMN pitch_deg REAL;
ALTER TABLE images ADD COLUMN kind TEXT NOT NULL DEFAULT 'legacy';
UPDATE images SET kind = 'legacy';

-- Legacy rows have NULL pano_id; NULLs are distinct in a unique index, so they never collide.
CREATE UNIQUE INDEX uq_images_candidate_pano_kind ON images (bench_candidate_id, pano_id, kind);

ALTER TABLE detection_items ADD COLUMN is_target BOOLEAN;
ALTER TABLE detection_items ADD COLUMN center_offset_deg REAL;

CREATE TABLE image_annotations (
    id INTEGER NOT NULL PRIMARY KEY,
    image_id INTEGER NOT NULL REFERENCES images (id),
    annotator VARCHAR NOT NULL,
    label_type VARCHAR NOT NULL,
    value JSON,
    confidence FLOAT,
    created_at DATETIME NOT NULL
);
CREATE INDEX ix_image_annotations_image_id ON image_annotations (image_id);

CREATE TABLE bench_attributes (
    id INTEGER NOT NULL PRIMARY KEY,
    bench_candidate_id INTEGER NOT NULL UNIQUE REFERENCES bench_candidates (id),
    facing_deg FLOAT,
    facing_confidence FLOAT,
    facing_method VARCHAR,
    axis_only BOOLEAN NOT NULL DEFAULT 0,
    bench_type VARCHAR,
    backrest BOOLEAN,
    faces_category VARCHAR,
    faces_text VARCHAR,
    hero_image_id INTEGER REFERENCES images (id),
    hero_reason VARCHAR,
    embed_pano_id VARCHAR,
    embed_heading_deg FLOAT,
    updated_at DATETIME NOT NULL
);
CREATE INDEX ix_bench_attributes_hero_image_id ON bench_attributes (hero_image_id);
