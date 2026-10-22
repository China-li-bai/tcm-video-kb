#!/usr/bin/env bash
# Download one 人纪 series as m4a via proven yt-dlp (no cookies, no aria2).
# Usage: download_series_videos.sh SERIES EXPECTED [REVERSE=0]
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERIES="${1:?series}"; EXPECTED="${2:?expected}"; REVERSE="${3:-0}"
MEDIA="$ROOT/data/media/$SERIES"
LOG="$ROOT/data/media/_download_log.txt"
export PATH="$HOME/.deno/bin:$HOME/.local/bin:$PATH"
mkdir -p "$MEDIA"; PLIST="$MEDIA/_playlist.txt"; : > "$MEDIA/_failed_ids.txt"
declare -A URLS=(
  [shl]="https://www.youtube.com/playlist?list=PLWYut62NoAtzoHlM87Q3bCkuPq4TPbX81"
  [zj]="https://www.youtube.com/playlist?list=PLUOqnoW96eEY"
  [nj]="https://www.youtube.com/playlist?list=PLBOS9mCbmy5JSx4dtlOE7fScH-5EDF0ep"
  [jgy]="https://www.youtube.com/playlist?list=PLWYut62NoAtyHMBl-e3MFT69hwrr78VZ0"
  [bc]="https://www.youtube.com/playlist?list=PLUxSDTWtSyU8"
)
log(){ echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*"|tee -a "$LOG"; }

if [[ ! -s "$PLIST" ]]; then
  EXTRA=(); [[ "$REVERSE" == "1" ]] && EXTRA+=(--playlist-reverse)
  yt-dlp --flat-playlist --print $'%(playlist_index)03d\t%(id)s\t%(duration)s\t%(title)s' \
    "${EXTRA[@]}" "${URLS[$SERIES]}" > "$PLIST"
fi
mapfile -t LINES < "$PLIST"
log "$SERIES start count=${#LINES[@]} expected=$EXPECTED reverse=$REVERSE yt-dlp-simple"

FAILED=0; OK=0; N=0
for line in "${LINES[@]}"; do
  [[ -z "${line// }" ]] && continue
  N=$((N+1))
  if [[ "$REVERSE" == "1" ]]; then
    # bc playlist file already has reverse indices (008..001); use field 1
    idx=$(printf '%s\n' "$line" | cut -f1)
  else
    idx=$(printf '%s\n' "$line" | cut -f1)
  fi
  vid=$(printf '%s\n' "$line" | cut -f2)
  dur=$(printf '%s\n' "$line" | cut -f3)
  if "$ROOT/scripts/download_one_audio.sh" "$SERIES" "$idx" "$vid" "$dur"; then
    OK=$((OK+1))
  else
    FAILED=$((FAILED+1))
  fi
  sleep 2
done
python3 "$ROOT/scripts/build_media_manifest.py" "$MEDIA" "$EXPECTED" | tee -a "$LOG" || true
log "$SERIES done ok=$OK failed=$FAILED"
