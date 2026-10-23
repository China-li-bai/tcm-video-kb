"""Aggregate per-episode knowledge outputs into data/knowledge/_index/*.csv.

Pure file work: reads data/knowledge/<video_id>/{entities,knowledge_points}.jsonl and
chapters.json, writes flat CSVs that a spreadsheet, SQLite import or a search UI can load.
"""
from __future__ import annotations
import csv, io, json, pathlib
from typing import Any

from tcmkb_ingest import artifacts as art

ENTITY_COLS = ["entity_id", "type", "canonical", "in_lexicon", "n_videos", "n_mentions", "videos",
               "surfaces", "dosages", "first_url", "asr_uncertain", "note"]
KP_COLS = ["kp_id", "video_id", "series", "episode", "type", "statement", "entity_ids", "chapter_id",
           "chapter_title", "evidence_quote", "start_s", "end_s", "url", "confidence", "asr_note", "title"]
CHAPTER_COLS = ["chapter_id", "video_id", "level", "parent_id", "title", "summary", "start_s", "end_s",
                "clause_refs", "six_channel", "url"]


def _jsonl(p: pathlib.Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()] if p.exists() else []


def episode_dirs(kroot: pathlib.Path) -> list[pathlib.Path]:
    return sorted(d for d in kroot.iterdir()
                  if d.is_dir() and not d.name.startswith("_") and (d / "knowledge_points.jsonl").exists())


def _csv(rows: list[dict[str, Any]], cols: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


def build_index(root: pathlib.Path) -> dict[str, Any]:
    kroot = root / "data" / "knowledge"
    out = kroot / "_index"
    ents: dict[str, dict[str, Any]] = {}
    kps: list[dict[str, Any]] = []
    chaps: list[dict[str, Any]] = []
    vids = []
    for d in episode_dirs(kroot):
        vids.append(d.name)
        chapters = json.loads((d / "chapters.json").read_text(encoding="utf-8")) \
            if (d / "chapters.json").exists() else []
        ctitle = {c["chapter_id"]: c["title"] for c in chapters}
        for c in chapters:
            chaps.append({**c, "clause_refs": " ".join(c.get("clause_refs") or []),
                          "url": (c["citation"].get("t_url") or c["citation"].get("url"))})
        for e in _jsonl(d / "entities.jsonl"):
            g = ents.setdefault(e["entity_id"], {
                "entity_id": e["entity_id"], "type": e["type"], "canonical": e["canonical"],
                "in_lexicon": e["in_lexicon"], "n_mentions": 0, "videos": [], "surfaces": [], "dosages": [],
                "first_url": e.get("first_url") or "", "asr_uncertain": e.get("asr_uncertain", False),
                "note": e.get("note", "")})
            g["n_mentions"] += e["n_mentions"]
            g["videos"].append(d.name)
            g["surfaces"] += [s for s in e.get("surfaces", []) if s not in g["surfaces"]]
            g["dosages"] += [s for s in e.get("dosages", []) if s not in g["dosages"]]
            g["asr_uncertain"] = g["asr_uncertain"] and e.get("asr_uncertain", False)
            g["note"] = g["note"] or e.get("note", "")
        for k in _jsonl(d / "knowledge_points.jsonl"):
            c = k["citation"]
            kps.append({**k, "entity_ids": " ".join(k["entity_ids"]), "series": c["series"],
                        "episode": c["episode"], "url": (c.get("t_url") or c.get("url")), "title": c["title"],
                        "chapter_title": ctitle.get(k.get("chapter_id") or "", "")})
    erows = []
    for g in sorted(ents.values(), key=lambda g: (g["type"], -g["n_mentions"], g["entity_id"])):
        erows.append({**g, "n_videos": len(g["videos"]), "videos": " ".join(g["videos"]),
                      "surfaces": "|".join(g["surfaces"][:20]), "dosages": "|".join(g["dosages"])})
    art.atomic_write_text(out / "entities.csv", _csv(erows, ENTITY_COLS))
    art.atomic_write_text(out / "knowledge_points.csv", _csv(kps, KP_COLS))
    art.atomic_write_text(out / "chapters.csv", _csv(chaps, CHAPTER_COLS))
    rep = {"videos": vids, "n_entities": len(erows), "n_knowledge_points": len(kps), "n_chapters": len(chaps)}
    art.atomic_write_json(out / "index_report.json", rep)
    return rep
