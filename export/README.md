# Bench Finder data

CSV exports of the data behind [bench.blackmad.com](https://bench.blackmad.com).
Regenerate with `make export-csv` after `bench-finder publish`.

## `benches.csv`

One row per bench shown on the site (Amsterdam).

| column | meaning |
| --- | --- |
| `id` | Bench id; the page is `page_url` |
| `lat`, `lng` | Position (WGS84). Some are moved from the mapped spot onto where street-level panoramas place the bench |
| `address` | Nearest street address |
| `source` | `OSM` (OpenStreetMap) or `BGT` (the city's large-scale base map) |
| `osm_id`, `osm_url` | The OpenStreetMap node, for OSM benches |
| `facing_deg` | Compass bearing the sitter faces (0 = north, 90 = east); blank if unknown |
| `facing_confidence` | 0 to 1, for estimated facings |
| `facing_method` | How the facing was found: `osm_tag`, `water_edge` (turned toward the nearest water edge), `vlm` (a vision model reading the photos) |
| `axis_only` | True for backless benches: the facing is an axis, either way round |
| `bench_type`, `backrest`, `material`, `seats`, `lit` | From OSM tags or detection |
| `faces_category` | What it looks at: water, street, park, square, wall, playground, other |
| `faces_text` | A few words on the view |
| `place_id` | Benches within a few metres of each other share a place (one card on the map) |
| `photo_url`, `photo_date` | Street-level photo of the bench and its capture month |
| `osm_tags` | The OSM tags, as JSON |

## `tables/`

The pipeline's SQLite tables (`data/benches.db`), one CSV each; the larger ones
are gzipped. See `DATABASE_MODEL.md` for the schema. Left out: tables written by
site visitors (ratings, notes, reports), and `detection_items` (one row per
detected box with its polygon, about 100 MB compressed).

Bench data from OpenStreetMap is © OpenStreetMap contributors, ODbL. BGT data is
from the Basisregistratie Grootschalige Topografie (CC0).
