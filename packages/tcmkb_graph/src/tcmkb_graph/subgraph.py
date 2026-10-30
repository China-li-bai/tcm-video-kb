"""Assemble a focus subgraph and equal-weight pattern tracks.

``composed_of`` is copied from the lexicon (source=lexicon). Lecture edges are the
candidate rows from :func:`tcmkb_graph.draft.materialize`. Tracks are ordered by
id, not by confidence, so the UI cannot present a winning 证型.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tcmkb_core.play import site_watch_url, youtube_t_url

from tcmkb_graph.draft import Materialization
from tcmkb_graph.lexicon_index import Ent

DISCLAIMER = (
    "学习倪师讲授，非诊疗建议。candidate 边不进入检索。"
    "多证分轨、同权并列，不标唯一证型、不按置信度排行。"
)


def build_subgraph(focus: str, mat: Materialization) -> dict:
    if focus not in mat.index:
        raise KeyError(focus)
    ent = mat.index[focus]
    edges: list[dict] = []
    node_ids: list[str] = [focus]

    if ent.category == "formula":
        for pred, obj in ent.relations:
            if pred != "composed_of" or obj not in mat.index:
                continue
            edges.append(_lexicon_edge(focus, obj))
            if obj not in node_ids:
                node_ids.append(obj)

    lecture = _lecture_touching(focus, ent, mat)
    seen = {e["id"] for e in edges}
    for raw in lecture:
        pub = _with_id(raw)
        if pub["id"] in seen:
            continue
        seen.add(pub["id"])
        edges.append(pub)
        for end in (pub["subj_id"], pub["obj_id"]):
            if end not in node_ids:
                node_ids.append(end)

    mentions = mentions_for(mat, set(node_ids))
    nodes = [_node(nid, mat.index, mentions, edges) for nid in node_ids]
    held = _held_for(focus, mat)
    return {
        "focus": focus,
        "disclaimer": DISCLAIMER,
        "nodes": nodes,
        "edges": edges,
        "held": held,
    }


def build_paths(focus: str, mat: Materialization) -> dict:
    """One track per 证, cards inside a track sorted by id (equal weight, no rank)."""
    if focus not in mat.index:
        raise KeyError(focus)
    ent = mat.index[focus]
    tracks: list[dict] = []
    if ent.category == "formula":
        syndrome_ids = sorted({
            e["obj_id"] for e in mat.edges
            if e["pred"] == "treats" and e["subj_id"] == focus
        })
        tracks = [_track(sid, mat, formula_id=focus) for sid in syndrome_ids]
    elif ent.category == "syndrome":
        linked = any(
            e["obj_id"] == focus and e["pred"] in ("indicates", "treats")
            for e in mat.edges
        )
        if linked:
            tracks = [_track(focus, mat, formula_id=None)]
    return {
        "focus": focus,
        "disclaimer": DISCLAIMER,
        "equal_weight": True,
        "tracks": tracks,
        "held": _held_for(focus, mat),
    }


def mentions_for(mat: Materialization, ids: set[str]) -> dict[str, dict]:
    """Mentions for ``ids``. A snapshot dict is used as-is; otherwise scan JSONL."""
    if mat.mentions is not None:
        return {i: mat.mentions[i] for i in ids if i in mat.mentions}
    return load_mentions(mat.knowledge_root, ids)


def index_mentions(knowledge_root: Path) -> dict[str, dict]:
    """First lecture mention for every entity id. Same order as :func:`load_mentions`."""
    found: dict[str, dict] = {}
    for video_dir in _entity_dirs(knowledge_root):
        for line in (video_dir / "entities.jsonl").read_text(encoding="utf-8").splitlines():
            if '"entity_id"' not in line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            eid = str(row.get("entity_id") or "")
            if not eid or eid in found:
                continue
            cite = _mention_cite(row)
            if cite:
                found[eid] = cite
    return found


def _entity_dirs(knowledge_root: Path) -> list[Path]:
    if not knowledge_root.is_dir():
        return []
    dirs = [
        p for p in knowledge_root.iterdir()
        if p.is_dir() and (p / "entities.jsonl").is_file()
    ]
    dirs.sort(key=lambda p: (p.name != "shl-001", p.name))
    return dirs


def load_mentions(knowledge_root: Path, ids: set[str]) -> dict[str, dict]:
    """First lecture mention per entity. Prefer shl-001, then other episodes."""
    if not ids or not knowledge_root.is_dir():
        return {}
    need = set(ids)
    found: dict[str, dict] = {}
    dirs = _entity_dirs(knowledge_root)
    for video_dir in dirs:
        if not need:
            break
        for line in (video_dir / "entities.jsonl").read_text(encoding="utf-8").splitlines():
            hit = next((i for i in need if f'"entity_id": "{i}"' in line), None)
            if hit is None:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            eid = str(row.get("entity_id") or "")
            if eid not in need:
                continue
            cite = _mention_cite(row)
            if cite:
                found[eid] = cite
                need.discard(eid)
            if not need:
                break
    return found


def _lecture_touching(focus: str, ent: Ent, mat: Materialization) -> list[dict]:
    direct = [
        e for e in mat.edges
        if e["subj_id"] == focus or e["obj_id"] == focus
    ]
    if ent.category != "formula":
        return direct
    syndromes = {
        e["obj_id"] for e in direct
        if e["pred"] == "treats" and e["subj_id"] == focus
    }
    extra = [
        e for e in mat.edges
        if e["pred"] == "indicates" and e["obj_id"] in syndromes
    ]
    return direct + extra


def _held_for(focus: str, mat: Materialization) -> list[dict]:
    return [
        h for h in mat.held
        if focus in h.get("subj_ids", []) or focus in h.get("obj_ids", [])
    ]


def _lexicon_edge(subj: str, obj: str) -> dict:
    return {
        "id": f"composed_of:{subj}:{obj}:lexicon",
        "subj_id": subj,
        "pred": "composed_of",
        "obj_id": obj,
        "source": "lexicon",
        "kp_id": None,
        "citation": None,
        "confidence": None,
        "review_status": "lexicon",
        "evidence_quote": None,
        "statement": None,
        "video_id": None,
    }


def _with_id(edge: dict) -> dict:
    out = dict(edge)
    out["id"] = f"{edge['pred']}:{edge['subj_id']}:{edge['obj_id']}:{edge.get('kp_id') or 'lexicon'}"
    return out


def _node(nid: str, index: dict[str, Ent], mentions: dict[str, dict], edges: list[dict]) -> dict:
    ent = index[nid]
    citations: list[dict] = []
    if nid in mentions:
        citations.append(mentions[nid])
    seen: set[tuple] = set()
    for edge in edges:
        if edge.get("source") != "lecture":
            continue
        if nid not in (edge.get("subj_id"), edge.get("obj_id")):
            continue
        cit = edge.get("citation") or {}
        key = ("lecture", edge.get("kp_id"), cit.get("start_s"))
        if key in seen:
            continue
        seen.add(key)
        citations.append({
            "kind": "lecture",
            "kp_id": edge.get("kp_id"),
            "video_id": edge.get("video_id"),
            "start_s": cit.get("start_s"),
            "end_s": cit.get("end_s"),
            "quote": edge.get("evidence_quote") or cit.get("quote"),
            "title": cit.get("title"),
            "statement": edge.get("statement"),
            "t_url": cit.get("t_url"),
            "youtube_t_url": cit.get("youtube_t_url"),
        })
    return {
        "id": nid,
        "label": ent.term,
        "category": ent.category,
        "citations": citations,
    }


def _track(syndrome_id: str, mat: Materialization, *, formula_id: str | None) -> dict:
    treats = [
        e for e in mat.edges
        if e["pred"] == "treats" and e["obj_id"] == syndrome_id
        and (formula_id is None or e["subj_id"] == formula_id)
    ]
    treats.sort(key=lambda e: (e["kp_id"], e["subj_id"]))
    cards = [
        e for e in mat.edges
        if e["pred"] == "indicates" and e["obj_id"] == syndrome_id
    ]
    cards.sort(key=lambda e: (e["subj_id"], e["kp_id"]))
    ent = mat.index.get(syndrome_id)
    return {
        "syndrome_id": syndrome_id,
        "label": ent.term if ent else syndrome_id,
        "treats": [_card(e, mat.index) for e in treats],
        "cards": [_card(e, mat.index) for e in cards],
    }


def _card(edge: dict, index: dict[str, Ent]) -> dict:
    """Equal-weight card. Confidence is intentionally omitted so it cannot be a rank."""
    sub = edge["subj_id"]
    ent = index.get(sub)
    cit = edge.get("citation") or {}
    return {
        "subj_id": sub,
        "obj_id": edge["obj_id"],
        "label": ent.term if ent else sub,
        "category": ent.category if ent else "",
        "pred": edge["pred"],
        "kp_id": edge["kp_id"],
        "review_status": "candidate",
        "evidence_quote": edge.get("evidence_quote"),
        "statement": edge.get("statement") or "",
        "video_id": edge.get("video_id"),
        "start_s": cit.get("start_s"),
        "t_url": cit.get("t_url"),
        "youtube_t_url": cit.get("youtube_t_url"),
        "title": cit.get("title"),
    }


def _mention_cite(row: dict) -> dict | None:
    video_id = row.get("video_id")
    try:
        start = float(row["first_start_s"])
    except (KeyError, TypeError, ValueError):
        return None
    url = str(row.get("first_url") or "")
    yt = _youtube_id(url)
    return {
        "kind": "mention",
        "kp_id": None,
        "video_id": video_id,
        "start_s": start,
        "end_s": None,
        "quote": None,
        "title": None,
        "statement": None,
        "t_url": site_watch_url(str(video_id), start) if video_id else None,
        "youtube_t_url": youtube_t_url(yt, start) if yt else (url or None),
    }


def _youtube_id(url: str) -> str | None:
    if "youtube" not in url and "youtu.be" not in url:
        return None
    vs = parse_qs(urlparse(url).query).get("v")
    return vs[0] if vs else None
