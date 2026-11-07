#!/usr/bin/env python3
"""Export slim knowledge-point JSON for listen-desk「问这句」.

Reads existing data/knowledge/<id>/knowledge_points.jsonl only — does not run
knowledge-build or mutate pipeline state. Output is keyed by time window so the
frontend can pick overlapping / nearest claims for the current sentence.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KNOWLEDGE = ROOT / "data" / "knowledge"
DEFAULT_OUT = ROOT / "web" / "public" / "knowledge"
# Same 7 videos that already ship public transcripts.
DEFAULT_IDS = [
    "shl-001",
    "shl-002",
    "shl-003",
    "shl-004",
    "shl-005",
    "shl-006",
    "shl-007",
    "shl-008",
    "jgy-001",
    "jgy-002",
    "jgy-003",
    "jgy-004",
    "jgy-005",
    "jgy-006",
    "jgy-007",
    "jgy-008",
    "jgy-009",
    "jgy-010",
    "jgy-011",
    "jgy-012",
    "bc-001",
]

# Keep payload small: only fields the CheckSheet needs.
KEEP = (
    "kp_id",
    "video_id",
    "type",
    "statement",
    "evidence_quote",
    "start_s",
    "end_s",
    "confidence",
)


def export_one(vid: str, knowledge: Path, out_dir: Path) -> bool:
    src = knowledge / vid / "knowledge_points.jsonl"
    if not src.exists():
        print(f"SKIP {vid}: no knowledge_points.jsonl")
        return False
    points = []
    with src.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            statement = (row.get("statement") or "").strip()
            if not statement:
                continue
            try:
                start_s = float(row["start_s"])
                end_s = float(row["end_s"])
            except (KeyError, TypeError, ValueError):
                continue
            if end_s < start_s:
                start_s, end_s = end_s, start_s
            slim = {
                "kp_id": str(row.get("kp_id") or f"{vid}.kp{len(points):04d}"),
                "video_id": str(row.get("video_id") or vid),
                "type": str(row.get("type") or "claim"),
                "statement": statement,
                "evidence_quote": (row.get("evidence_quote") or "").strip(),
                "start_s": round(start_s, 3),
                "end_s": round(end_s, 3),
                "confidence": float(row.get("confidence") or 0),
            }
            # Drop unused keys if KEEP ever drifts — keep explicit.
            points.append({k: slim[k] for k in KEEP})
    points.sort(key=lambda p: (p["start_s"], p["end_s"], -p["confidence"]))
    dest = out_dir / f"{vid}.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"video_id": vid, "points": points}
    with dest.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK {vid}: {len(points)} kps -> {dest} ({dest.stat().st_size / 1024:.1f} KB)")
    return True


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--knowledge", type=Path, default=DEFAULT_KNOWLEDGE)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--ids", nargs="*", default=DEFAULT_IDS)
    args = p.parse_args()
    ok = 0
    for vid in args.ids:
        if export_one(vid, args.knowledge, args.out):
            ok += 1
    print(f"done: {ok}/{len(args.ids)}")


if __name__ == "__main__":
    main()
