"""``python -m tcmkb_graph draft`` — write candidate / held JSONL."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tcmkb_core.config import repo_root

from tcmkb_graph.draft import materialize, write_jsonl


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tcmkb_graph")
    sub = parser.add_subparsers(dest="cmd", required=True)
    draft = sub.add_parser("draft", help="scan knowledge points into candidate edges")
    draft.add_argument("--root", default=None, help="repo root (default: auto)")
    draft.add_argument("--video", action="append", default=None, help="limit to video_id (repeatable)")
    draft.add_argument("--out", default=None, help="candidate JSONL (default: data/graph/candidates.jsonl)")
    draft.add_argument("--held", default=None, help="rejected-KP JSONL (default: data/graph/held.jsonl)")
    args = parser.parse_args(argv)
    if args.cmd != "draft":
        parser.error(args.cmd)
        return 2

    root = Path(args.root).resolve() if args.root else repo_root()
    try:
        result = materialize(root, videos=args.video)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    out = _path(root, args.out, "data/graph/candidates.jsonl")
    held = _path(root, args.held, "data/graph/held.jsonl")
    write_jsonl(out, result.edges)
    write_jsonl(held, result.held)
    print(json.dumps({
        "n_candidates": len(result.edges),
        "n_held": len(result.held),
        "out": str(out),
        "held": str(held),
        "videos": args.video or "all",
    }, ensure_ascii=False))
    return 0


def _path(root: Path, given: str | None, default: str) -> Path:
    if not given:
        return root / default
    path = Path(given)
    return path if path.is_absolute() else root / path
