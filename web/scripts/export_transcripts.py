#!/usr/bin/env python3
"""Export artifact segments.jsonl into compact public/transcripts/<id>.json."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from export_common import export_batch
from publish_manifest import public_ids, require, validate_window

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACTS = ROOT / "data" / "artifacts"
DEFAULT_OUT = ROOT / "web" / "public" / "transcripts"


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
            require(isinstance(row, dict) and row.get("video_id") == vid, f"{vid}: segment source video_id missing/mismatched")
            text = (row.get("text") or "").strip()
            require(bool(text), "empty transcript text")
            validate_window(row)
            require(type(row.get("seq")) is int, "segment requires integer seq")
            segments.append(
                {
                    "seq": row["seq"],
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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--ids", nargs="*", default=None)
    args = p.parse_args()
    ids = args.ids if args.ids is not None else public_ids("transcript")
    return export_batch(ids, args.artifacts, args.out, "transcript", export_one)


if __name__ == "__main__":
    sys.exit(main())
