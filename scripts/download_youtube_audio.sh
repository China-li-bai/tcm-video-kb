#!/usr/bin/env bash
# Download one YouTube video as m4a. For long videos, uses time-sectioned
# downloads to survive mid-transfer 403s, then concatenates.
# Usage: download_youtube_audio.sh OUT_PATH_WITHOUT_EXT VIDEO_ID [DURATION_SEC]
set -uo pipefail
export PATH="$HOME/.local/bin:$HOME/.deno/bin:$PATH"
OUT="${1:?out path without ext}"  # e.g. .../shl-001
VID="${2:?video id}"
DUR_HINT="${3:-0}"
IMP="Chrome-133:Macos-15"
CHUNK=1200  # 20 minutes
URL="https://www.youtube.com/watch?v=${VID}"
TMPDIR="${OUT}.sections"
FINAL="${OUT}.m4a"

if [[ -f "$FINAL" ]] && (( $(stat -c%s "$FINAL") > 100000 )); then
  echo "exists $FINAL"; exit 0
fi

YT_COMMON=(--js-runtimes deno --impersonate "$IMP"
  -f "bestaudio[ext=m4a]/bestaudio/best"
  --retries 10 --fragment-retries 10 --extractor-retries 5
  --retry-sleep 5 --sleep-requests 1)

# Probe duration if needed
DUR="$DUR_HINT"
if (( DUR <= 0 )); then
  DUR=$(yt-dlp "${YT_COMMON[@]}" --print "%(duration)s" --simulate "$URL" 2>/dev/null | tail -1)
fi
DUR=${DUR%.*}
if [[ -z "$DUR" || "$DUR" -lt 1 ]]; then
  echo "cannot get duration for $VID"; exit 1
fi

# Short videos: single shot
if (( DUR <= CHUNK + 60 )); then
  yt-dlp "${YT_COMMON[@]}" -x --audio-format m4a --audio-quality 96K \
    --continue --no-overwrites \
    -o "${OUT}.%(ext)s" "$URL"
  [[ -f "$FINAL" ]] && exit 0
  # webm fallback convert
  if [[ -f "${OUT}.webm" ]]; then
    ffmpeg -y -i "${OUT}.webm" -c:a aac -b:a 96k "$FINAL" && rm -f "${OUT}.webm"
  fi
  [[ -f "$FINAL" ]] && exit 0 || exit 1
fi

mkdir -p "$TMPDIR"
START=0
PART=0
while (( START < DUR )); do
  END=$(( START + CHUNK ))
  (( END > DUR )) && END=$DUR
  PART_FILE=$(printf "%s/part-%03d.m4a" "$TMPDIR" "$PART")
  if [[ -f "$PART_FILE" ]] && (( $(stat -c%s "$PART_FILE") > 50000 )); then
    echo "skip section $PART $START-$END"
  else
    echo "section $PART $START-$END / $DUR"
    attempt=1
    ok=0
    while (( attempt <= 6 )); do
      rm -f "${PART_FILE}.part" 2>/dev/null
      if yt-dlp "${YT_COMMON[@]}" \
          --download-sections "*${START}-${END}" --force-keyframes-at-cuts \
          -x --audio-format m4a --audio-quality 96K \
          -o "$PART_FILE" "$URL" 2>"$TMPDIR/part-${PART}.err"; then
        # yt-dlp may write .m4a directly
        if [[ -f "$PART_FILE" ]] && (( $(stat -c%s "$PART_FILE") > 50000 )); then
          ok=1; break
        fi
        # sometimes adds extra extension
        found=$(ls "$TMPDIR"/part-$(printf '%03d' $PART)*.m4a 2>/dev/null | head -1)
        if [[ -n "$found" && "$found" != "$PART_FILE" ]]; then
          mv "$found" "$PART_FILE"; ok=1; break
        fi
      fi
      echo "section $PART attempt $attempt failed; sleep $((attempt*8))"
      sleep $((attempt * 8))
      attempt=$((attempt+1))
    done
    if (( ok == 0 )); then
      echo "GAVE UP section $PART ($START-$END) for $VID"
      exit 1
    fi
  fi
  START=$END
  PART=$((PART+1))
  sleep 2
done

# Concat
LIST="$TMPDIR/concat.txt"
: > "$LIST"
for f in "$TMPDIR"/part-*.m4a; do
  [[ -f "$f" ]] || continue
  # escape for concat demuxer
  printf "file '%s'\n" "$f" >> "$LIST"
done
ffmpeg -y -f concat -safe 0 -i "$LIST" -c copy "$FINAL" </dev/null 2>"$TMPDIR/concat.err"
if [[ -f "$FINAL" ]] && (( $(stat -c%s "$FINAL") > 100000 )); then
  rm -rf "$TMPDIR"
  echo "OK $FINAL size=$(stat -c%s "$FINAL")"
  exit 0
fi
echo "concat failed"; exit 1
