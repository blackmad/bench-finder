where are these benches in our DB? https://overpass-turbo.eu/s/2eHq

okay they seem to be missing from candidates
(bench-finder) ➜  bench_finder git:(main) ✗ find . | grep 11176424310
./images/bench_11176424310_node_heading_180.jpg
./images/bench_11176424310_node_heading_0.jpg
./images/bench_node_11176424310_heading_180.jpg
./images/bench_node_11176424310_heading_0.jpg
./images/bench_node_11176424310_heading_90.jpg
./images/bench_11176424310_node_heading_270.jpg
./images/bench_11176424310_node_heading_90.jpg
./images/bench_node_11176424310_heading_270.jpg
./bench_images/ultralytics/11176424310_node_heading_270_bench_11176424310_node_heading_270.jpg
(bench-finder) ➜  bench_finder git:(main) ✗ litecli data/benches.db
LiteCli: 1.15.0 (SQLite: 3.50.4)
GitHub: https://github.com/dbcli/litecli
data/benches.db> select * FROM bench_candidates WHERE provider_id='11176424310_node';
0 rows in set
Time: 0.001s
data/benches.db>
