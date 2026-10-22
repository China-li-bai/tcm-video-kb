#!/usr/bin/env bash
# Rolling pipeline: keep download alive, ASR-batch pending media, queue knowledge.
# Survives disconnects via nohup. Safe to restart (resumable).
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG=data/logs/roll_pipeline.log
PIDF=data/media/_roll_pipeline.pid
QUEUE=data/knowledge/_queue.txt
SERIES_ORDER=(zj nj jgy bc)   # shl already purged
BUDGET_GB=40
MIN_FREE_GB=15
ASR_THREADS=4
SLEEP_EMPTY=120
SLEEP_BETWEEN=30

mkdir -p data/logs data/knowledge data/media
echo $$ > "$PIDF"
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*" | tee -a "$LOG"; }

download_alive() {
  local p
  p=$(cat data/media/_orchestrator.pid 2>/dev/null || true)
  [[ -n "$p" ]] && kill -0 "$p" 2>/dev/null
}

ensure_download() {
  if download_alive; then return 0; fi
  # Check if all series already have playlist done (no pending downloads)
  local need=0
  for s in "${SERIES_ORDER[@]}"; do
    local pl="data/media/$s/_playlist.txt"
    [[ -f "$pl" ]] || { need=1; break; }
    local total have
    total=$(grep -c . "$pl" 2>/dev/null || echo 0)
    have=$(ls "data/media/$s" 2>/dev/null | grep -cE '\.(m4a|webm|mp3)$' || true)
    local purged=0
    if [[ -f "data/media/$s/_purged_ids.txt" ]]; then
      purged=$(grep -c . "data/media/$s/_purged_ids.txt" || true)
    fi
    # if have+purged < total, still need download
    if (( have + purged < total )); then need=1; break; fi
  done
  if (( need == 0 )); then
    log "download: all series complete (or playlists satisfied)"
    return 0
  fi
  log "download: restarting orchestrator for ${SERIES_ORDER[*]}"
  nohup bash scripts/download_youtube_renji.sh "${SERIES_ORDER[@]}" \
    >> data/media/_orchestrator.out 2>&1 &
  echo $! > data/media/_orchestrator.pid
  sleep 2
}

pending_m4a_count() {
  local s=$1
  ls "data/media/$s" 2>/dev/null | grep -cE '\.(m4a|webm|mp3)$' || true
}

free_gb() {
  df -BG --output=avail / | tail -1 | tr -dc '0-9'
}

queue_new_purged() {
  local s=$1
  local f="data/media/$s/_purged.json"
  [[ -f "$f" ]] || return 0
  mkdir -p data/knowledge
  touch "$QUEUE"
  python3 - <<PY
import json
from pathlib import Path
purged = json.load(open("$f")).get("items", {})
queue = Path("$QUEUE")
have = set()
if queue.exists():
    have = {ln.strip() for ln in queue.read_text().splitlines() if ln.strip()}
# also skip already-built knowledge
root = Path("data/knowledge")
built = {p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith("_")}
added = []
for vid in sorted(purged):
    if vid in have or vid in built or vid.endswith("-demo"):
        continue
    with queue.open("a") as fh:
        fh.write(vid + "\n")
    added.append(vid)
print("queued", ",".join(added) if added else "(none)")
PY
}

run_one_batch() {
  local s=$1
  local n
  n=$(pending_m4a_count "$s")
  if (( n == 0 )); then return 1; fi
  local fg
  fg=$(free_gb)
  if (( fg < MIN_FREE_GB )); then
    log "ASR skip $s: free ${fg}G < ${MIN_FREE_GB}G"
    return 1
  fi
  # Don't start ASR if another batch already running
  if pgrep -f "tcmkb_ingest batch" >/dev/null 2>&1; then
    log "ASR skip: another batch already running"
    return 1
  fi
  local rid="roll-${s}-$(date +%Y%m%d-%H%M%S)"
  log "ASR start series=$s pending=$n free=${fg}G run_id=$rid"
  uv run python -m tcmkb_ingest batch \
    --media "$s" \
    --budget-gb "$BUDGET_GB" \
    --min-free-gb "$MIN_FREE_GB" \
    --asr-threads "$ASR_THREADS" \
    --max-batches 1 \
    --run-id "$rid" \
    >> "data/logs/${rid}.log" 2>&1
  local rc=$?
  log "ASR end series=$s rc=$rc"
  queue_new_purged "$s"
  return 0
}

all_done() {
  # done when: no download needed, no pending m4a, no ASR running
  for s in shl "${SERIES_ORDER[@]}"; do
    local n
    n=$(pending_m4a_count "$s")
    (( n > 0 )) && return 1
  done
  download_alive && return 1
  pgrep -f "tcmkb_ingest batch" >/dev/null 2>&1 && return 1
  return 0
}

log "roll_pipeline start pid=$$"
# seed queue from already-purged shl
queue_new_purged shl

while true; do
  ensure_download
  did=0
  for s in "${SERIES_ORDER[@]}"; do
    if run_one_batch "$s"; then did=1; sleep "$SLEEP_BETWEEN"; fi
  done
  # also catch any leftover shl if re-fetched
  if run_one_batch shl; then did=1; fi
  queue_new_purged shl
  for s in "${SERIES_ORDER[@]}"; do queue_new_purged "$s"; done

  if all_done; then
    log "roll_pipeline: all media downloaded, transcribed, purged. Idle."
    # stay alive but sleep longer so restarts of download can be watched
    sleep 600
    if all_done; then
      log "roll_pipeline: still idle after 10m; exiting cleanly"
      rm -f "$PIDF"
      exit 0
    fi
  fi
  if (( did == 0 )); then
    log "idle cycle (waiting for downloads or disk); sleep ${SLEEP_EMPTY}s"
    sleep "$SLEEP_EMPTY"
  fi
done
