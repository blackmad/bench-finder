#!/usr/bin/env bash
# Build the committed frontend (HEAD), upload its source maps to Sentry
# (whizziwig/bench-finder-web), strip them from the public files, deploy.
# Needs an authenticated sentry-cli and wrangler.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
git -C "$repo" archive HEAD frontend | tar -x -C "$work"
cd "$work/frontend"
ln -s "$repo/frontend/node_modules" node_modules
cp "$repo"/frontend/.env* . 2>/dev/null || true
rm -rf public/data
release=$(git -C "$repo" rev-parse --short HEAD)
VITE_SENTRY_RELEASE="$release" \
VITE_DATA_BASE_URL=https://bench-data.blackmad.com \
VITE_API_BASE_URL=https://bench-finder-api.bench-finder-worker.workers.dev \
  npx vite build
sentry-cli sourcemaps inject dist
sentry-cli sourcemaps upload --org whizziwig --project bench-finder-web \
  --release "$release" dist
find dist -name '*.map' -delete
npx wrangler deploy
