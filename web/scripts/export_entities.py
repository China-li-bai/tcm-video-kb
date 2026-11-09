#!/usr/bin/env python3
"""Export slim high-confidence entity mentions for listen-desk chips (P3).

Reads existing data/knowledge/<id>/entities.jsonl only — does not run
knowledge-build. Keeps lexicon-held, non-uncertain mentions of learner-facing
types (方/药/症/证/…). Output is a flat time-sorted mention list for overlap
lookup near the active sentence.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from export_common import export_batch
from publish_manifest import public_ids, require, validate_window

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KNOWLEDGE = ROOT / "data" / "knowledge"
DEFAULT_OUT = ROOT / "web" / "public" / "entities"

# Entity.type values we surface as chips. Others (person/book/method/concept/…)
# stay out — quiet beats noisy.
KEEP_TYPES = frozenset(
    {
        "formula",
        "herb",
        "symptom",
        "pattern",
        "six_channel",
        "disease",
        "zangfu",
        "pulse",
        "tongue",
        "clause",
        "meridian",
        "acupoint",
    }
)


def export_one(vid: str, knowledge: Path, out_dir: Path) -> bool:
    src = knowledge / vid / "entities.jsonl"
    if not src.exists():
        print(f"SKIP {vid}: no entities.jsonl")
        return False

    mentions: list[dict] = []
    with src.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not row.get("in_lexicon"):
                continue
            if row.get("asr_uncertain"):
                continue
            etype = str(row.get("type") or "")
            if etype not in KEEP_TYPES:
                continue
            entity_id = str(row.get("entity_id") or "").strip()
            label = str(row.get("canonical") or "").strip()
            require(bool(entity_id) and bool(label), "eligible entity missing identity/label")
            # Skip draft / non-lexicon ids even if flagged oddly.
            if entity_id.startswith("new."):
                continue

            for m in row.get("mentions") or []:
                if (m.get("source") or "") != "lexicon":
                    continue
                if m.get("asr_uncertain"):
                    continue
                validate_window(m)
                start_s = m["start_s"]
                end_s = m["end_s"]
                mentions.append(
                    {
                        "entity_id": entity_id,
                        "label": label,
                        "type": etype,
                        "start_s": round(start_s, 3),
                        "end_s": round(end_s, 3),
                        "seq": int(m["seq"]) if m.get("seq") is not None else None,
                    }
                )

    mentions.sort(key=lambda x: (x["start_s"], x["end_s"], x["entity_id"]))
    # Drop exact dupes (same entity + start) to shrink payload.
    deduped: list[dict] = []
    seen: set[tuple] = set()
    for m in mentions:
        key = (m["entity_id"], m["start_s"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(m)

    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{vid}.json"
    payload = {"video_id": vid, "mentions": deduped}
    with dest.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK {vid}: {len(deduped)} mentions -> {dest} ({dest.stat().st_size / 1024:.1f} KB)")
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--knowledge", type=Path, default=DEFAULT_KNOWLEDGE)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p.add_argument("--ids", nargs="*", default=None)
    args = p.parse_args()
    ids = args.ids if args.ids is not None else public_ids("entities")
    return export_batch(ids, args.knowledge, args.out, "entities", export_one)


if __name__ == "__main__":
    sys.exit(main())
