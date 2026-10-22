"""Write reading packets for an annotator: data/knowledge/<id>/_work/windows/wNN.txt."""
from __future__ import annotations
import json, pathlib
from typing import Any

from tcmkb_ingest.knowledge.chunk import hms, make_windows, render
from tcmkb_ingest.knowledge.episode import load_episode
from tcmkb_ingest.knowledge.lexmatch import Lexicon, match_clauses, window_candidates


def knowledge_dir(root: pathlib.Path, video_id: str) -> pathlib.Path:
    return root / "data" / "knowledge" / video_id


def prepare(root: pathlib.Path, video_id: str, window_s: float = 720.0) -> dict[str, Any]:
    ep = load_episode(root, video_id)
    lx = Lexicon(root)
    wins = make_windows(ep.segments, window_s=window_s)
    kd = knowledge_dir(root, video_id)
    wd = kd / "_work" / "windows"
    wd.mkdir(parents=True, exist_ok=True)
    index = []
    for w in wins:
        segs = [s for s in ep.segments if w.seg_from <= s["seq"] <= w.seg_to]
        cands = window_candidates(lx, segs)
        clauses = match_clauses(lx, segs)
        heur = [c for c in ep.s08_chapters if c["end_s"] > w.start_s and c["start_s"] < w.end_s]
        head = [f"# {video_id} {w.window} seq {w.seg_from}-{w.seg_to} "
                f"[{hms(w.start_s)}-{hms(w.end_s)}] {ep.title}",
                "# lexicon candidates (id term xN @first_seq): " + "; ".join(
                    f"{eid} {t}x{n}@{fs}" for eid, t, n, fs in cands[:80]),
                "# clause matches (no@seq ratio): " + "; ".join(
                    f"{c['no']}@{c['seq']} {c['ratio']}" for c in clauses),
                "# s08 heuristic chapter starts: " + ", ".join(str(c.get("seg_from")) for c in heur)]
        (wd / f"{w.window}.txt").write_text("\n".join(head) + "\n" + render(segs) + "\n", encoding="utf-8")
        index.append({**w.__dict__, "n_segments": len(segs), "n_chars": sum(len(s["text"]) for s in segs),
                      "clauses": clauses})
    (kd / "_work" / "windows.json").write_text(json.dumps(
        {"video_id": video_id, "window_s": window_s, "windows": index}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return {"video_id": video_id, "windows": len(wins), "dir": str(wd)}
