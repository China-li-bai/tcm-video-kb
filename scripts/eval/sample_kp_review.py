#!/usr/bin/env python3
"""Stratified sample of knowledge points for human accuracy review.

Stratify by series + type; flag short evidence_quote; emit review CSV with blank verdict.

Usage (from repo root):
  uv run python scripts/eval/sample_kp_review.py
  uv run python scripts/eval/sample_kp_review.py --per-cell 1 --seed 42 \\
      --out-csv eval/kp/batch001_kp_review.csv
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    REPO,
    SERIES_ORDER,
    load_kp_index,
    skip_video,
    write_csv,
    write_jsonl,
)

SHORT_EVIDENCE_CHARS = 8  # flag if evidence_quote shorter than this


def stratified_sample(
    rows: list[dict],
    per_cell: int,
    max_total: int | None,
    seed: int,
    short_chars: int,
) -> list[dict]:
    rng = random.Random(seed)
    # filter incomplete zj / demos
    rows = [r for r in rows if not skip_video(r.get("video_id") or "")]
    cells: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        series = r.get("series") or (r.get("video_id") or "").split("-")[0]
        typ = r.get("type") or "unknown"
        cells[(series, typ)].append(r)

    picked: list[dict] = []
    for (series, typ), items in sorted(cells.items(), key=lambda x: (SERIES_ORDER.index(x[0][0]) if x[0][0] in SERIES_ORDER else 99, x[0][1])):
        k = min(per_cell, len(items))
        # prefer items with short evidence (need review) then random
        def sort_key(r: dict) -> tuple:
            eq = r.get("evidence_quote") or ""
            short = 0 if len(eq) < short_chars else 1
            return (short, rng.random())

        ranked = sorted(items, key=sort_key)
        # take half from short-flagged pool if available, rest random among top
        shorts = [r for r in ranked if len(r.get("evidence_quote") or "") < short_chars]
        chosen: list[dict] = []
        if shorts and k >= 1:
            chosen.extend(rng.sample(shorts, min(len(shorts), max(1, k // 2))))
        remain = [r for r in items if r not in chosen]
        need = k - len(chosen)
        if need > 0 and remain:
            chosen.extend(rng.sample(remain, min(need, len(remain))))
        for r in chosen:
            eq = r.get("evidence_quote") or ""
            url = r.get("url") or ""
            # prefer youtube-style if present in statement sources — CSV url is often site /watch
            citation_url = url
            picked.append(
                {
                    "kp_id": r.get("kp_id", ""),
                    "video_id": r.get("video_id", ""),
                    "series": series,
                    "episode": r.get("episode", ""),
                    "type": typ,
                    "statement": r.get("statement", ""),
                    "evidence_quote": eq,
                    "evidence_chars": len(eq),
                    "short_evidence": "1" if len(eq) < short_chars else "0",
                    "start_s": r.get("start_s", ""),
                    "end_s": r.get("end_s", ""),
                    "citation_url": citation_url,
                    "chapter_title": r.get("chapter_title", ""),
                    "confidence": r.get("confidence", ""),
                    "asr_note": r.get("asr_note", ""),
                    "entity_ids": r.get("entity_ids", ""),
                    "verdict": "",  # 对 / 部分对 / 错
                    "notes": "",
                    "reviewer": "",
                    "reviewed_at": "",
                }
            )

    rng.shuffle(picked)
    # re-sort for readability: series then type
    picked.sort(
        key=lambda r: (
            SERIES_ORDER.index(r["series"]) if r["series"] in SERIES_ORDER else 99,
            r["type"],
            r["kp_id"],
        )
    )
    if max_total is not None and len(picked) > max_total:
        # keep stratified: take first max_total after shuffle within cells already done
        # trim evenly by dropping from largest cells
        while len(picked) > max_total:
            cnt = Counter((r["series"], r["type"]) for r in picked)
            cell = cnt.most_common(1)[0][0]
            for i in range(len(picked) - 1, -1, -1):
                if (picked[i]["series"], picked[i]["type"]) == cell:
                    picked.pop(i)
                    break
    return picked


CSV_FIELDS = [
    "kp_id",
    "video_id",
    "series",
    "episode",
    "type",
    "statement",
    "evidence_quote",
    "evidence_chars",
    "short_evidence",
    "start_s",
    "end_s",
    "citation_url",
    "chapter_title",
    "confidence",
    "asr_note",
    "entity_ids",
    "verdict",
    "notes",
    "reviewer",
    "reviewed_at",
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=20261025)
    ap.add_argument("--per-cell", type=int, default=1, help="samples per (series, type) cell")
    ap.add_argument("--max-total", type=int, default=80, help="cap total rows (None=no cap via 0)")
    ap.add_argument("--short-chars", type=int, default=SHORT_EVIDENCE_CHARS)
    ap.add_argument(
        "--out-csv",
        type=Path,
        default=REPO / "eval/kp/batch001_kp_review.csv",
    )
    ap.add_argument(
        "--out-jsonl",
        type=Path,
        default=REPO / "eval/kp/batch001_kp_review.jsonl",
    )
    args = ap.parse_args()
    max_total = None if args.max_total == 0 else args.max_total
    all_rows = load_kp_index()
    picked = stratified_sample(
        all_rows, args.per_cell, max_total, args.seed, args.short_chars
    )
    n1 = write_csv(args.out_csv, picked, CSV_FIELDS)
    n2 = write_jsonl(args.out_jsonl, picked)
    by_series = Counter(r["series"] for r in picked)
    by_type = Counter(r["type"] for r in picked)
    n_short = sum(1 for r in picked if r["short_evidence"] == "1")
    print(f"pool KPs: {len(all_rows)}; sampled: {n1}")
    print(f"wrote → {args.out_csv.relative_to(REPO)}")
    print(f"wrote → {args.out_jsonl.relative_to(REPO)}")
    print("per series:", dict(by_series))
    print("per type:", dict(by_type.most_common()))
    print(f"short_evidence flagged: {n_short}/{n1}")


if __name__ == "__main__":
    main()
