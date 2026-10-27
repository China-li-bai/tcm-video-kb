#!/usr/bin/env python3
"""Sample ~1×2min ASR check windows per ~10 lectures per series.

Prefer high TCM-term-density spans (lexicon match); else mid-video.
Skips zj short 目录 clips listed in _common.INCOMPLETE_ZJ.

Usage (from repo root):
  uv run python scripts/eval/sample_asr_windows.py
  uv run python scripts/eval/sample_asr_windows.py --seed 42 --window-s 120 --per-n 10 \\
      --out-csv eval/asr/windows/batch001_windows.csv \\
      --out-jsonl eval/asr/windows/batch001_windows.jsonl
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    REPO,
    SERIES_ORDER,
    knowledge_video_ids,
    lecture_md_path,
    load_lexicon_terms,
    load_segments,
    outline_path,
    segments_path,
    skip_video,
    term_density,
    video_duration_s,
    write_csv,
    write_jsonl,
    youtube_from_segments,
    youtube_t_url,
)


def pick_videos(series: str, per_n: int, rng: random.Random) -> list[str]:
    vids = [v for v in knowledge_video_ids(series) if not skip_video(v)]
    if not vids:
        return []
    n = max(1, math.ceil(len(vids) / per_n))
    # stratified by episode order: split into n buckets, pick one from each
    vids_sorted = sorted(vids)
    if len(vids_sorted) <= n:
        return vids_sorted
    buckets: list[list[str]] = [[] for _ in range(n)]
    for i, v in enumerate(vids_sorted):
        buckets[i * n // len(vids_sorted)].append(v)
    chosen: list[str] = []
    for b in buckets:
        if b:
            chosen.append(rng.choice(b))
    return chosen


def best_window(
    segments: list[dict],
    duration_s: float,
    window_s: float,
    terms: list[str],
    rng: random.Random,
    step_s: float = 60.0,
) -> dict:
    """Slide a window; score by term density of concatenated segment text."""
    if not segments or duration_s <= 0:
        mid = max(0.0, duration_s / 2 - window_s / 2)
        return {
            "start_s": round(mid, 2),
            "end_s": round(mid + window_s, 2),
            "term_density": 0.0,
            "matched_terms": [],
            "asr_text": "",
            "method": "mid_fallback_empty",
        }

    # Restrict lexicon to terms that appear at least once in this lecture (big speedup).
    if terms:
        full = "".join((seg.get("text") or "") for seg in segments)
        terms = [t for t in terms if t in full][:800]

    max_start = max(0.0, duration_s - window_s)
    # avoid very start/end intros/outros: keep 5% margin when long enough
    margin = min(60.0, duration_s * 0.05) if duration_s > window_s * 2 else 0.0
    lo, hi = margin, max(margin, max_start - margin)
    if hi <= lo:
        lo, hi = 0.0, max_start

    candidates: list[dict] = []
    t = lo
    while t <= hi + 1e-6:
        end = t + window_s
        texts: list[str] = []
        for seg in segments:
            ss = float(seg.get("start_s") or 0)
            ee = float(seg.get("end_s") or 0)
            if ee <= t or ss >= end:
                continue
            texts.append(seg.get("text") or "")
        blob = "".join(texts)
        dens, matched = term_density(blob, terms) if terms else (0.0, [])
        candidates.append(
            {
                "start_s": round(t, 2),
                "end_s": round(min(end, duration_s), 2),
                "term_density": round(dens, 4),
                "matched_terms": matched[:40],
                "asr_text": blob[:500],
                "method": "term_density",
            }
        )
        t += step_s

    if not candidates:
        mid = max(0.0, duration_s / 2 - window_s / 2)
        return {
            "start_s": round(mid, 2),
            "end_s": round(mid + window_s, 2),
            "term_density": 0.0,
            "matched_terms": [],
            "asr_text": "",
            "method": "mid_fallback",
        }

    # pick among top-3 density to avoid always same hotspot
    candidates.sort(key=lambda c: c["term_density"], reverse=True)
    top = candidates[:3]
    if top[0]["term_density"] <= 0:
        mid = max(0.0, duration_s / 2 - window_s / 2)
        # find candidate closest to mid
        best = min(candidates, key=lambda c: abs(c["start_s"] - mid))
        best = dict(best)
        best["method"] = "mid_video"
        return best
    chosen = rng.choice(top)
    return chosen


def sample(
    seed: int,
    window_s: float,
    per_n: int,
    series_filter: list[str] | None,
) -> list[dict]:
    rng = random.Random(seed)
    terms = load_lexicon_terms()
    series_list = series_filter or list(SERIES_ORDER)
    rows: list[dict] = []
    for series in series_list:
        for vid in pick_videos(series, per_n, rng):
            segs = load_segments(vid)
            if not segs:
                continue
            dur = video_duration_s(vid, segs)
            if dur < window_s * 0.5:
                continue  # too short to be a useful 2min check
            win = best_window(segs, dur, window_s, terms, rng)
            yid, yurl = youtube_from_segments(segs)
            t_url = youtube_t_url(yid, yurl, win["start_s"])
            rows.append(
                {
                    "window_id": f"{vid}.w{int(win['start_s']):05d}",
                    "series": series,
                    "video_id": vid,
                    "youtube_id": yid or "",
                    "youtube_url_t": t_url,
                    "start_s": win["start_s"],
                    "end_s": win["end_s"],
                    "window_s": round(win["end_s"] - win["start_s"], 2),
                    "duration_s": round(dur, 2),
                    "term_density": win["term_density"],
                    "matched_terms": ",".join(win["matched_terms"][:20]),
                    "method": win["method"],
                    "lecture_md": lecture_md_path(vid),
                    "segments_jsonl": segments_path(vid),
                    "outline_md": outline_path(vid),
                    "asr_excerpt": win["asr_text"][:240],
                    # scoring blanks
                    "cer": "",
                    "term_recall": "",
                    "notes": "",
                    "scorer": "",
                    "scored_at": "",
                }
            )
    return rows


CSV_FIELDS = [
    "window_id",
    "series",
    "video_id",
    "youtube_id",
    "youtube_url_t",
    "start_s",
    "end_s",
    "window_s",
    "duration_s",
    "term_density",
    "matched_terms",
    "method",
    "lecture_md",
    "segments_jsonl",
    "outline_md",
    "asr_excerpt",
    "cer",
    "term_recall",
    "notes",
    "scorer",
    "scored_at",
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--window-s", type=float, default=120.0)
    ap.add_argument("--per-n", type=int, default=10, help="1 window per ~N lectures")
    ap.add_argument("--series", nargs="*", default=None, help="subset e.g. shl zj")
    ap.add_argument(
        "--out-csv",
        type=Path,
        default=REPO / "eval/asr/windows/batch001_windows.csv",
    )
    ap.add_argument(
        "--out-jsonl",
        type=Path,
        default=REPO / "eval/asr/windows/batch001_windows.jsonl",
    )
    args = ap.parse_args()
    rows = sample(args.seed, args.window_s, args.per_n, args.series)
    n1 = write_csv(args.out_csv, rows, CSV_FIELDS)
    # jsonl keeps matched_terms as list
    jl = []
    for r in rows:
        j = dict(r)
        j["matched_terms"] = [t for t in (r.get("matched_terms") or "").split(",") if t]
        jl.append(j)
    n2 = write_jsonl(args.out_jsonl, jl)
    from collections import Counter

    c = Counter(r["series"] for r in rows)
    print(f"wrote {n1} windows → {args.out_csv.relative_to(REPO)}")
    print(f"wrote {n2} windows → {args.out_jsonl.relative_to(REPO)}")
    print("per series:", dict(c))
    print(f"lexicon terms loaded: {len(load_lexicon_terms())}")


if __name__ == "__main__":
    main()
