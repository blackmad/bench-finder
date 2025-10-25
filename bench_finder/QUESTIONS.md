- what to do about duplicated images in DB?

- why is this bench being returned for no_bench mode?

➜  bench_finder git:(main) ✗ cd ~/bench_finder; uv run python tools/fastapi_cli.py random --show-images --show-annotations  --mode no_bench
('iterm2', '3.6.5') to WHOLE
🎲 Getting random bench (min_confidence=0.8, mode=no_bench)...

============================================================
🪑 Bench ID: 245
📍 Location: 52.377811, 4.929819
📊 Source: OSM
🎯 Detection Type: ROBOFLOW
✅ Bench Found: True
🎯 Best Confidence: 0.950
   Roboflow: 0.950
📏 Distance: 0m (0.00km)
🖼️  Images: 8
   Image files:
     • bench_4600552064_node_heading_0.jpg
     • bench_4600552064_node_heading_90.jpg
     • bench_4600552064_node_heading_180.jpg
     • bench_4600552064_node_heading_270.jpg
     • bench_4600552064_node_heading_0.jpg
     ... and 3 more
