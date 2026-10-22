#!/usr/bin/env bash
# Download one YouTube video as m4a. Short: single shot. Long: optional sections.
# Usage: download_one_audio.sh SERIES IDX VIDEO_ID [DURATION_HINT]
# Env: CHUNK_SEC=1500 (25min), MAX_ATTEMPTS=6, NO_COOKIES=1
set -uo pipefail
export PATH="$HOME/.deno/bin:$HOME/.local/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SERIES="${1:?}"; IDX="${2:?}"; VID="${3:?}"; DUR_HINT="${4:-0}"
MEDIA="$ROOT/data/media/$SERIES"
LOG="$ROOT/data/media/_download_log.txt"
FINAL="$MEDIA/${SERIES}-${IDX}.m4a"
CHUNK="${CHUNK_SEC:-1500}"
MAX="${MAX_ATTEMPTS:-6}"
mkdir -p "$MEDIA"
log(){ echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $*" | tee -a "$LOG"; }

if [[ -f "$FINAL" ]] && (( $(stat -c%s "$FINAL") > 100000 )); then
  d=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$FINAL" 2>/dev/null || echo 0)
  if python3 -c "import sys; sys.exit(0 if float('$d' or 0)>60 else 1)"; then
    log "$SERIES skip existing ${SERIES}-${IDX}.m4a size=$(stat -c%s "$FINAL") dur=$d"
    exit 0
  fi
  log "$SERIES removing bad existing ${SERIES}-${IDX}.m4a"
  rm -f "$FINAL"
fi

# Already transcribed and purged by `tcmkb_ingest batch --media` (disk budget): don't re-download
# unless explicitly asked (tcmkb_ingest refetch sets FORCE_REFETCH=1).
if [[ "${FORCE_REFETCH:-0}" != "1" && -f "$MEDIA/_purged_ids.txt" ]] && grep -qxF "$VID" "$MEDIA/_purged_ids.txt"; then
  log "$SERIES skip purged ${SERIES}-${IDX} id=$VID (FORCE_REFETCH=1 to re-download)"
  exit 0
fi

YT=(--js-runtimes deno -f 'bestaudio[ext=m4a]/bestaudio' --no-playlist
    --retries 10 --fragment-retries 15 --continue)

finalize() {
  local src="$1"
  local br
  br=$(ffprobe -v error -show_entries format=bit_rate -of default=nw=1:nk=1 "$src" 2>/dev/null || echo 0)
  if [[ "${src##*.}" != "m4a" ]] || { [[ -n "$br" ]] && [[ "$br" =~ ^[0-9]+$ ]] && (( br > 110000 )); }; then
    ffmpeg -y -i "$src" -c:a aac -b:a 96k "$FINAL" </dev/null >/dev/null 2>&1 || mv "$src" "$FINAL"
    [[ -f "$src" && "$src" != "$FINAL" ]] && rm -f "$src"
  else
    mv "$src" "$FINAL"
  fi
  local d size
  d=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$FINAL" 2>/dev/null || echo 0)
  size=$(stat -c%s "$FINAL")
  if ! python3 -c "import sys; sys.exit(0 if float('$d' or 0)>30 else 1)"; then
    rm -f "$FINAL"; return 1
  fi
  log "$SERIES OK ${SERIES}-${IDX}.m4a size=$size dur=$d"
  return 0
}

download_full() {
  local tmpdir="/tmp/yt-dl-${SERIES}-${IDX}"
  mkdir -p "$tmpdir"; rm -rf "$tmpdir"/* 2>/dev/null || true
  local attempt=1 delay=30
  while (( attempt <= MAX )); do
    log "$SERIES download ${SERIES}-${IDX} id=$VID attempt=$attempt/$MAX (full)"
    : > "$MEDIA/_yt-dlp-${IDX}.log"
    if yt-dlp "${YT[@]}" -o "$tmpdir/%(id)s.%(ext)s" \
        "https://www.youtube.com/watch?v=${VID}" 2>>"$MEDIA/_yt-dlp-${IDX}.log"; then
      local got
      got=$(ls "$tmpdir"/*.{m4a,webm,opus,mp4} 2>/dev/null | head -1 || true)
      if [[ -n "$got" ]] && finalize "$got"; then
        rm -rf "$tmpdir"; return 0
      fi
    fi
    local err; err=$(tail -2 "$MEDIA/_yt-dlp-${IDX}.log" 2>/dev/null | tr '\n' ' ')
    log "$SERIES FAIL ${SERIES}-${IDX} full attempt=$attempt; sleep ${delay}s; $err"
    sleep "$delay"
    delay=$(( delay < 300 ? delay * 2 : 300 ))
    attempt=$((attempt+1))
  done
  rm -rf "$tmpdir"
  return 1
}

download_sections() {
  local dur="$1"
  local secdir="$MEDIA/${SERIES}-${IDX}.sections"
  mkdir -p "$secdir"
  local start=0 part=0
  while (( start < dur )); do
    local end=$(( start + CHUNK ))
    (( end > dur )) && end=$dur
    local partf
    partf=$(printf "%s/part-%03d.m4a" "$secdir" "$part")
    if [[ -f "$partf" ]] && (( $(stat -c%s "$partf") > 50000 )); then
      local pd; pd=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$partf" 2>/dev/null || echo 0)
      if python3 -c "import sys; sys.exit(0 if float('$pd' or 0)>10 else 1)"; then
        log "$SERIES skip section $part $start-$end"
        start=$end; part=$((part+1)); continue
      fi
    fi
    local attempt=1 delay=30 ok=0
    while (( attempt <= 5 )); do
      log "$SERIES section $part $start-$end / $dur attempt=$attempt"
      rm -f "$partf" "${partf}.part" 2>/dev/null
      local tmpsec="/tmp/yt-sec-${SERIES}-${IDX}-${part}"
      mkdir -p "$tmpsec"; rm -rf "$tmpsec"/* 2>/dev/null || true
      if yt-dlp "${YT[@]}" --download-sections "*${start}-${end}" --force-keyframes-at-cuts \
          -o "$tmpsec/%(id)s.%(ext)s" \
          "https://www.youtube.com/watch?v=${VID}" 2>"$secdir/part-${part}.err"; then
        local got; got=$(ls "$tmpsec"/*.{m4a,webm,opus,mp4} 2>/dev/null | head -1 || true)
        if [[ -n "$got" ]]; then
          if [[ "${got##*.}" != "m4a" ]]; then
            ffmpeg -y -i "$got" -c:a aac -b:a 96k "$partf" </dev/null >/dev/null 2>&1
          else
            # copy/remux to stable m4a
            ffmpeg -y -i "$got" -c copy "$partf" </dev/null >/dev/null 2>&1 || mv "$got" "$partf"
          fi
          if [[ -f "$partf" ]] && (( $(stat -c%s "$partf") > 50000 )); then
            ok=1; rm -rf "$tmpsec"; break
          fi
        fi
      fi
      local err; err=$(tail -2 "$secdir/part-${part}.err" 2>/dev/null | tr '\n' ' ')
      log "$SERIES section $part FAIL attempt=$attempt; sleep ${delay}s; $err"
      sleep "$delay"
      delay=$(( delay < 300 ? delay * 2 : 300 ))
      attempt=$((attempt+1))
    done
    rm -rf "/tmp/yt-sec-${SERIES}-${IDX}-${part}" 2>/dev/null || true
    if (( ok == 0 )); then
      log "$SERIES GAVE UP section $part for ${SERIES}-${IDX}"
      echo "$VID" >> "$MEDIA/_failed_ids.txt"
      return 1
    fi
    start=$end; part=$((part+1)); sleep 2
  done
  local list="$secdir/concat.txt"
  : > "$list"
  for f in "$secdir"/part-*.m4a; do
    [[ -f "$f" ]] || continue
    printf "file '%s'\n" "$f" >> "$list"
  done
  ffmpeg -y -f concat -safe 0 -i "$list" -c copy "$FINAL" </dev/null 2>"$secdir/concat.err"
  if [[ -f "$FINAL" ]] && (( $(stat -c%s "$FINAL") > 100000 )); then
    local d size
    d=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$FINAL")
    size=$(stat -c%s "$FINAL")
    log "$SERIES OK ${SERIES}-${IDX}.m4a size=$size dur=$d (sectioned)"
    rm -rf "$secdir"
    return 0
  fi
  log "$SERIES concat FAIL ${SERIES}-${IDX}"
  return 1
}

DUR="$DUR_HINT"
if (( DUR <= 0 )); then
  DUR=$(yt-dlp --js-runtimes deno --print "%(duration)s" --simulate \
    "https://www.youtube.com/watch?v=${VID}" 2>/dev/null | tail -1 || echo 0)
fi
DUR=${DUR%.*}
DUR=${DUR:-0}

# Short/medium: full download. Long (>45min): try full once then sections.
if (( DUR > 0 && DUR <= 2700 )); then
  if download_full; then exit 0; fi
elif (( DUR > 2700 )); then
  # Try full with fewer attempts first; fall back to sections
  MAX=3 download_full && exit 0
  log "$SERIES falling back to sections dur=$DUR chunk=$CHUNK"
  if download_sections "$DUR"; then exit 0; fi
else
  if download_full; then exit 0; fi
fi

log "$SERIES GAVE UP ${SERIES}-${IDX} id=$VID"
echo "$VID" >> "$MEDIA/_failed_ids.txt"
exit 1
