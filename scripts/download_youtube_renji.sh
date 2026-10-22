#!/usr/bin/env bash
# Download all 倪海厦 人纪 YouTube series as audio-only into data/media/{series}/
# Proven approach (2026-10-21): yt-dlp --js-runtimes deno, NO cookies, NO aria2.
# Long (>45min) videos: full download first; on failure use --download-sections.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/data/media/_download_log.txt"
export PATH="$HOME/.deno/bin:$HOME/.local/bin:$PATH"
mkdir -p "$ROOT/data/media"

SERIES_ORDER=(shl zj nj jgy bc)
[[ $# -gt 0 ]] && SERIES_ORDER=("$@")

for s in "${SERIES_ORDER[@]}"; do
  case "$s" in
    shl) e=8; r=0;; zj) e=90; r=0;; nj) e=10; r=0;; jgy) e=40; r=0;; bc) e=8; r=1;;
    *) echo "unknown series $s"; continue;;
  esac
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] ORCH start $s" | tee -a "$LOG"
  "$ROOT/scripts/download_series_videos.sh" "$s" "$e" "$r"
  echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] ORCH end $s" | tee -a "$LOG"
done
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] ORCH all done" | tee -a "$LOG"
