#!/usr/bin/env bash
# Build Worker inputs: vendored packages, graph snapshot, Vite dist.
# Does not deploy and does not need a Cloudflare token.
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
if [[ ! -x .venv/bin/python ]]; then
  echo "missing .venv; from the repo root run: uv sync" >&2
  exit 1
fi

copy_pkg() {
  local src="$1" dest="$2"
  rm -rf "$dest"
  mkdir -p "$dest"
  cp -a "$src"/. "$dest"/
  find "$dest" -type d -name '__pycache__' -prune -exec rm -rf {} +
  find "$dest" -type d -name '*.egg-info' -prune -exec rm -rf {} +
  rm -rf "$dest/build"
}

copy_pkg packages/tcmkb_core services/worker/vendor/tcmkb_core
copy_pkg packages/tcmkb_graph services/worker/vendor/tcmkb_graph
copy_pkg services/api services/worker/vendor/tcmkb_api

.venv/bin/python -m tcmkb_graph snapshot \
  --out services/worker/src/graph_snapshot.json \
  --embed services/worker/src/graph_data.py

npm ci --prefix web
npm run build --prefix web
