#!/usr/bin/env bash
# Utrecht, entirely local and free: no LLM (Claude, Gemini), no paid API (no
# Google geocoding or Static API). Run it from a fresh clone on a machine that
# has NOT got the Amsterdam database in data/: ids, caches and images are keyed
# by bench id, so the two cities must not share a data/ directory.
#
#   scripts/utrecht_local.sh                 # the whole city (resumes where it stopped)
#   scripts/utrecht_local.sh --limit 30      # a trial on the 30 benches nearest the centre
#   scripts/utrecht_local.sh --fresh         # forget which steps finished, run them all again
#
# Free sources only: OSM (Overpass), PDOK Locatieserver (addresses), Google and
# Apple panoramas via the `streetlevel` library (the same unofficial, unbilled
# endpoints the Amsterdam run used), YOLO + SAM 3 on this machine, and an
# optional local Ollama model for the occlusion check.
#
# Needs: uv, ~10 GB disk per 1,000 benches, models/sam3.pt (gated on Hugging Face:
# request access at https://huggingface.co/facebook/sam3, download sam3.pt into
# models/). Output: data/benches.db, images/, and the publishable site data in
# dist-data-utrecht/ (not uploaded: an upload would replace Amsterdam's live data).
#
# Each step leaves data/utrecht_steps/<step>.done; a re-run skips finished steps.
# Log: data/utrecht.log.
set -euo pipefail
cd "$(dirname "$0")/.."

LIMIT=""
FRESH=0
while [ $# -gt 0 ]; do
  case "$1" in
    --limit) LIMIT="$2"; shift 2 ;;
    --fresh) FRESH=1; shift ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done

export BENCH_CITY=utrecht
export DATABASE_PATH=data/benches.db
export IMAGES_DIR=images
# No API keys: anything that would call a paid API fails instead of spending.
unset GOOGLE_MAPS_API_KEY ANTHROPIC_API_KEY OPENROUTER_API_KEY GEMINI_API_KEY GOOGLE_API_KEY ROBOFLOW_API_KEY
export GOOGLE_MAPS_API_KEY=""

STEPS=data/utrecht_steps
LOG=data/utrecht.log
OUT=dist-data-utrecht
mkdir -p data models "$STEPS"
[ "$FRESH" = 1 ] && rm -f "$STEPS"/*.done
exec > >(tee -a "$LOG") 2>&1

quiet() { grep -v -i "warn\|term.image\|readthedocs\|terminal\|ghostty" || true; }
step() {  # step NAME COMMAND...: run once, mark done
  local name="$1"; shift
  if [ -f "$STEPS/$name.done" ]; then echo "== $name: done earlier, skipped"; return; fi
  echo "== $name $(date '+%F %T')"
  "$@" 2>&1 | quiet | tail -n 8
  touch "$STEPS/$name.done"
}

echo "==== Utrecht local run $(date '+%F %T') limit=${LIMIT:-none}"

# --- setup -------------------------------------------------------------------
uv sync --group detect-extra 2>&1 | tail -n 1
if [ ! -f models/yolo11x-seg.pt ]; then
  echo "== downloading yolo11x-seg.pt"
  curl -fL -o models/yolo11x-seg.pt \
    https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11x-seg.pt
fi
if [ ! -f models/sam3.pt ]; then
  echo "models/sam3.pt is missing. Request access at https://huggingface.co/facebook/sam3," >&2
  echo "then download sam3.pt into models/ (e.g. 'uv run hf download facebook/sam3 sam3.pt --local-dir models')." >&2
  exit 1
fi
if [ -z "${TORCH_DEVICE:-}" ]; then
  TORCH_DEVICE=$(uv run python -c "import torch; print('mps' if torch.backends.mps.is_available() else 'cuda' if torch.cuda.is_available() else 'cpu')" 2>/dev/null | tail -n 1)
fi
export TORCH_DEVICE
echo "torch device: $TORCH_DEVICE"

# Refuse to mix cities in one database (see the top of this file).
if [ -f "$DATABASE_PATH" ]; then
  other=$(uv run python - <<'EOF' 2>/dev/null | tail -n 1
import sqlite3
c = sqlite3.connect("data/benches.db")
try:
    print(c.execute("SELECT count(*) FROM searches WHERE query <> 'utrecht'").fetchone()[0])
except sqlite3.OperationalError:
    print(0)
EOF
)
  if [ "${other:-0}" != 0 ]; then
    echo "data/benches.db holds other searches (Amsterdam?). Run this in a separate clone." >&2
    exit 1
  fi
fi

# --- candidates ------------------------------------------------------------------
step migrate      uv run python -m bench_finder.migrate
step import_osm   uv run python -m bench_finder.import_osm ${LIMIT:+--limit "$LIMIT"}

# --- photos and detection ------------------------------------------------------------
step fetch_images uv run bench-finder fetch-images
step yolo         uv run python -m bench_finder.detect_aimed --bbox utrecht
step sam3         uv run --group detect-extra python -m bench_finder.detect_aimed --bbox utrecht --model sam3
step sam3_verify  uv run --group detect-extra python -m bench_finder.detect_aimed --bbox utrecht --verify-only

# --- positions and facings (geometry only) --------------------------------------------
step triangulate  uv run python -m bench_finder.triangulate apply
step water_fetch  uv run python -m bench_finder.water_facing fetch
step water_apply  uv run python -m bench_finder.water_facing apply
step water_unfaced uv run python -m bench_finder.water_facing unfaced

# --- second capture from better panoramas (Google/Apple), then detect those ----------
step vantage      uv run python -m bench_finder.vantage run
step yolo2        uv run python -m bench_finder.detect_aimed --bbox utrecht
step sam3_2       uv run --group detect-extra python -m bench_finder.detect_aimed --bbox utrecht --model sam3
step sam3_verify2 uv run --group detect-extra python -m bench_finder.detect_aimed --bbox utrecht --verify-only

# --- heroes ----------------------------------------------------------------------
step recentre     uv run python -m bench_finder.recentre run
step recut        uv run python -m bench_finder.recut --heroes --bbox utrecht --include-unclassified
if command -v ollama >/dev/null && ollama list 2>/dev/null | grep -q "qwen3.5:9b"; then
  step occlusion  uv run python -m bench_finder.local_occlusion
else
  echo "== occlusion: skipped (needs Ollama with qwen3.5:9b: 'ollama pull qwen3.5:9b')"
fi
step hero_masks   uv run --group detect-extra python -m bench_finder.hero_fade masks
step hero_fade    uv run python -m bench_finder.hero_fade fade

# --- names and exclusions -----------------------------------------------------------
step addresses    uv run python -m bench_finder.addresses fetch
step stops        uv run python -m bench_finder.publish.exclude fetch
step platforms    uv run python -m bench_finder.publish.exclude fetch-platforms
step mark_stops   uv run python -m bench_finder.publish.exclude mark-stops

# --- publish locally (never uploads) -------------------------------------------------
rm -f "$STEPS/publish.done"  # always rebuild the site data from the current db
step publish      uv run bench-finder publish --bbox utrecht --include-unclassified --out "$OUT"

uv run python - <<'EOF'
import json
m = json.load(open("dist-data-utrecht/manifest.json"))
print("published:", m.get("counts"))
EOF
echo "==== done $(date '+%F %T'). Bring back: data/benches.db, images/, $OUT/"
