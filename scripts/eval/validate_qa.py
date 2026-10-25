#!/usr/bin/env python3
"""Validate eval/retrieval/qa.jsonl against knowledge layer.

Checks required fields, unique ids, gold_video_id exists under data/knowledge/,
and (when gold_kp_id set) timestamps match knowledge_points.csv.

Usage (repo root):
  uv run python scripts/eval/validate_qa.py
  uv run python scripts/eval/validate_qa.py --path eval/retrieval/qa.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REQUIRED = (
    "id",
    "question",
    "series",
    "gold_video_id",
    "gold_start_s",
    "gold_end_s",
    "tolerance_s",
)


def load_qa(path: Path) -> list[dict]:
    rows: list[dict] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        try:
            rows.append(json.loads(s))
        except json.JSONDecodeError as e:
            raise SystemExit(f"{path}:{i}: JSON error: {e}") from e
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--path",
        type=Path,
        default=REPO / "eval/retrieval/qa.jsonl",
    )
    ap.add_argument("--strict-kp", action="store_true", help="require gold_kp_id on every row")
    args = ap.parse_args()
    path = args.path if args.path.is_absolute() else REPO / args.path
    if not path.is_file():
        print(f"MISSING {path}", file=sys.stderr)
        return 2

    qa = load_qa(path)
    kp_path = REPO / "data/knowledge/_index/knowledge_points.csv"
    kp_by_id: dict[str, dict] = {}
    if kp_path.is_file():
        with kp_path.open(encoding="utf-8") as f:
            kp_by_id = {r["kp_id"]: r for r in csv.DictReader(f)}

    errors: list[str] = []
    seen_ids: set[str] = set()
    for i, row in enumerate(qa, 1):
        rid = row.get("id", f"row#{i}")
        for k in REQUIRED:
            if k not in row or row[k] in ("", None):
                errors.append(f"{rid}: missing {k}")
        if rid in seen_ids:
            errors.append(f"{rid}: duplicate id")
        seen_ids.add(rid)

        vid = row.get("gold_video_id") or ""
        kdir = REPO / "data" / "knowledge" / vid
        if not kdir.is_dir():
            errors.append(f"{rid}: gold_video_id {vid!r} not under data/knowledge/")

        try:
            start = float(row["gold_start_s"])
            end = float(row["gold_end_s"])
            tol = float(row["tolerance_s"])
        except (KeyError, TypeError, ValueError) as e:
            errors.append(f"{rid}: bad numeric fields ({e})")
            continue
        if end < start:
            errors.append(f"{rid}: end_s < start_s")
        if tol < 0:
            errors.append(f"{rid}: tolerance_s < 0")

        kid = row.get("gold_kp_id")
        if args.strict_kp and not kid:
            errors.append(f"{rid}: missing gold_kp_id (--strict-kp)")
        if kid:
            if kid not in kp_by_id:
                errors.append(f"{rid}: gold_kp_id {kid!r} not in knowledge_points.csv")
            else:
                kr = kp_by_id[kid]
                if kr["video_id"] != vid:
                    errors.append(
                        f"{rid}: kp video {kr['video_id']} != gold_video_id {vid}"
                    )
                try:
                    ks, ke = float(kr["start_s"]), float(kr["end_s"])
                except (TypeError, ValueError):
                    errors.append(f"{rid}: kp has bad timestamps")
                else:
                    if abs(ks - start) > 0.05 or abs(ke - end) > 0.05:
                        errors.append(
                            f"{rid}: timestamps diverge from KP "
                            f"(qa {start}-{end} vs kp {ks}-{ke})"
                        )

        if not (row.get("question") or "").strip():
            errors.append(f"{rid}: empty question")

    if errors:
        print(f"FAIL {path.relative_to(REPO)}: {len(qa)} items, {len(errors)} error(s)")
        for e in errors[:50]:
            print(" ", e)
        if len(errors) > 50:
            print(f"  ... +{len(errors) - 50} more")
        return 1

    from collections import Counter

    series = Counter(r.get("series") for r in qa)
    print(f"OK {path.relative_to(REPO)}: {len(qa)} items  series={dict(series)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
