-- 1.3: one candidate per provider_id, and indexes on FK columns that lacked one.
-- (bench_candidates.provider_id has no duplicates after 1.2; NULLs stay allowed.)
DROP INDEX IF EXISTS idx_bench_candidates_provider_id;
CREATE UNIQUE INDEX IF NOT EXISTS ix_bench_candidates_provider_id ON bench_candidates (provider_id);

CREATE INDEX IF NOT EXISTS ix_detection_items_detection_id ON detection_items (detection_id);
CREATE INDEX IF NOT EXISTS ix_processed_benches_best_image_id ON processed_benches (best_image_id);
CREATE INDEX IF NOT EXISTS ix_processed_benches_best_detection_id ON processed_benches (best_detection_id);
CREATE INDEX IF NOT EXISTS ix_bench_ratings_bench_candidate_id ON bench_ratings (bench_candidate_id);
CREATE INDEX IF NOT EXISTS ix_bench_comments_bench_candidate_id ON bench_comments (bench_candidate_id);
CREATE INDEX IF NOT EXISTS ix_bench_user_status_bench_candidate_id ON bench_user_status (bench_candidate_id);
CREATE INDEX IF NOT EXISTS ix_bench_reports_bench_candidate_id ON bench_reports (bench_candidate_id);
CREATE INDEX IF NOT EXISTS ix_bench_reports_image_id ON bench_reports (image_id);
