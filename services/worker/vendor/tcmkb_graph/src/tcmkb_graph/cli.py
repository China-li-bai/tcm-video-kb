"""``python -m tcmkb_graph`` — draft JSONL, or the Worker graph snapshot."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tcmkb_core.config import repo_root

from tcmkb_graph.draft import materialize, write_jsonl
from tcmkb_graph.snapshot import write_embedded_module, write_snapshot


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tcmkb_graph")
    sub = parser.add_subparsers(dest="cmd", required=True)
    draft = sub.add_parser("draft", help="scan knowledge points into candidate edges")
    draft.add_argument("--root", default=None, help="repo root (default: auto)")
    draft.add_argument("--video", action="append", default=None, help="limit to video_id (repeatable)")
    draft.add_argument("--out", default=None, help="candidate JSONL (default: data/graph/candidates.jsonl)")
    draft.add_argument("--held", default=None, help="rejected-KP JSONL (default: data/graph/held.jsonl)")
    snap = sub.add_parser("snapshot", help="write the Worker graph snapshot JSON")
    snap.add_argument("--root", default=None, help="repo root (default: auto)")
    snap.add_argument("--out", required=True, help="snapshot JSON path")
    snap.add_argument("--embed", default=None, help="also write a Python module the Worker imports")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve() if args.root else repo_root()
    if args.cmd == "snapshot":
        embed = Path(args.embed) if args.embed else None
        return _snapshot(root, Path(args.out), embed)
    return _draft(root, args)


def _draft(root: Path, args: argparse.Namespace) -> int:
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


def _snapshot(root: Path, out: Path, embed: Path | None) -> int:
    path = out if out.is_absolute() else root / out
    payload = write_snapshot(path, root)
    embedded = None
    if embed is not None:
        embedded_path = embed if embed.is_absolute() else root / embed
        write_embedded_module(path, embedded_path)
        embedded = str(embedded_path)
    print(json.dumps({
        "version": payload["version"],
        "n_candidates": len(payload["edges"]),
        "n_held": len(payload["held"]),
        "n_index": len(payload["index"]),
        "n_mentions": len(payload["mentions"]),
        "out": str(path),
        "embed": embedded,
    }, ensure_ascii=False))
    return 0


def _path(root: Path, given: str | None, default: str) -> Path:
    if not given:
        return root / default
    path = Path(given)
    return path if path.is_absolute() else root / path
