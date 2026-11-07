#!/usr/bin/env python3
"""Export artifact segments.jsonl into compact public/transcripts/<id>.json."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACTS = Path("/workspace/tcm-video-kb/data/artifacts")
DEFAULT_OUT = ROOT / "web" / "public" / "transcripts"
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


def export_one(vid: str, artifacts: Path, out_dir: Path) -> bool:
    src = artifacts / vid / "segments.jsonl"
    if not src.exists():
        print(f"SKIP {vid}: no segments.jsonl")
        return False
    segments = []
    with src.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            text = (row.get("text") or "").strip()
            if not text:
                continue
            segments.append(
                {
                    "seq": int(row.get("seq", len(segments))),
                    "start_s": float(row["start_s"]),
                    "end_s": float(row["end_s"]),
                    "text": text,
                }
            )
    dest = out_dir / f"{vid}.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as f:
        json.dump({"video_id": vid, "segments": segments}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK {vid}: {len(segments)} segs -> {dest} ({dest.stat().st_size / 1024:.1f} KB)")
    return True


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--ids", nargs="*", default=DEFAULT_IDS)
    args = p.parse_args()
    ok = 0
    for vid in args.ids:
        if export_one(vid, args.artifacts, args.out):
            ok += 1
    print(f"done: {ok}/{len(args.ids)}")


if __name__ == "__main__":
    main()
