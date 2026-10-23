"""Rewrite segment/chapter cite.t_url to site /watch/{id}?t= without re-running ASR.

Also refreshes lecture.md timestamp links. Does not touch asr_raw.json or wav.
When ``data/knowledge/<id>/`` exists: rewrites chapters/kp/entities citation URLs
and re-renders ``outline.md`` via the same ``render_outline`` used by knowledge-build.
"""
from __future__ import annotations
import json, pathlib
from typing import Any

from tcmkb_core.config import load_pipeline_config
from tcmkb_core.logging_util import get_logger
from tcmkb_ingest import artifacts as art
from tcmkb_ingest.sources import cite
from tcmkb_ingest.state import StateDB

log = get_logger("tcmkb.backfill_cites")


def _rewrite_cite(obj: dict[str, Any] | None, source: dict[str, Any], video_id: str,
                  start_s: float, end_s: float) -> dict[str, Any] | None:
    base = dict(obj or {})
    # Prefer stored youtube_id / title from existing cite or video.meta.source
    src = {
        "video_id": video_id,
        "youtube_id": base.get("youtube_id") or source.get("youtube_id"),
        "url": base.get("url") or source.get("url"),
        "title": base.get("title") or source.get("title"),
        "series_id": base.get("series_id") or source.get("series_id"),
        "series_title": base.get("series_title") or source.get("series_title"),
        "episode": base.get("episode") if base.get("episode") is not None else source.get("episode"),
    }
    return cite(src, start_s, end_s, video_id=video_id)


def _active_step_dir(abase: pathlib.Path, video_id: str, step: str, vk: str | None) -> pathlib.Path | None:
    if vk and (abase / step / vk).is_dir():
        return abase / step / vk
    cands = sorted((abase / step).glob("*"), key=lambda p: p.stat().st_mtime if p.is_dir() else 0)
    return cands[-1] if cands else None


def backfill_video(root: pathlib.Path, video_id: str, *, dry_run: bool = False) -> dict[str, Any]:
    pipe = load_pipeline_config(root)
    abase = root / pipe.get("artifacts_dir", "data/artifacts") / video_id
    db = StateDB(root / pipe.get("state_db", "data/state.sqlite"))
    try:
        m = db.get_video(video_id)
    finally:
        db.close()
    source = ((m.meta or {}).get("source") if m else None) or {}
    if not source.get("video_id"):
        source = {**source, "video_id": video_id}

    av = (m.active_versions if m else None) or {}
    info: dict[str, Any] = {"video_id": video_id, "dry_run": dry_run, "updated": []}

    # --- segments ---
    s06 = _active_step_dir(abase, video_id, "s06_clean", av.get("s06_clean"))
    seg_paths: list[pathlib.Path] = []
    if s06 and (s06 / "segments.jsonl").is_file():
        seg_paths.append(s06 / "segments.jsonl")
    top_seg = abase / "segments.jsonl"
    if top_seg.is_file() and top_seg not in seg_paths:
        seg_paths.append(top_seg)

    n_seg = 0
    segs_for_lecture: list[dict] = []
    for sp in seg_paths:
        rows = [json.loads(x) for x in sp.read_text(encoding="utf-8").splitlines() if x.strip()]
        new_rows = []
        for s in rows:
            c = _rewrite_cite(s.get("cite"), source, video_id, s["start_s"], s["end_s"])
            s = {**s, "cite": c}
            new_rows.append(s)
            n_seg += 1
        if sp == seg_paths[0]:
            segs_for_lecture = new_rows
        if not dry_run:
            body = "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in new_rows)
            art.atomic_write_text(sp, body)
        info["updated"].append(str(sp.relative_to(root)) if sp.is_relative_to(root) else str(sp))

    # --- chapters + lecture.md ---
    s08 = _active_step_dir(abase, video_id, "s08_chapter", av.get("s08_chapter"))
    chap_paths: list[pathlib.Path] = []
    if s08 and (s08 / "chapters.json").is_file():
        chap_paths.append(s08 / "chapters.json")
    top_ch = abase / "chapters.json"
    if top_ch.is_file() and top_ch not in chap_paths:
        chap_paths.append(top_ch)

    chapters: list[dict] = []
    for cp in chap_paths:
        chaps = json.loads(cp.read_text(encoding="utf-8"))
        for ch in chaps:
            ch["cite"] = _rewrite_cite(ch.get("cite"), source, video_id, ch["start_s"], ch["end_s"])
        if cp == chap_paths[0]:
            chapters = chaps
        if not dry_run:
            art.atomic_write_json(cp, chaps)
        info["updated"].append(str(cp.relative_to(root)) if cp.is_relative_to(root) else str(cp))

    if chapters and segs_for_lecture:
        from tcmkb_ingest.steps.s08_chapter import render_lecture_md
        title = (m.title if m else None) or source.get("title") or video_id
        lecture = render_lecture_md(video_id, title, chapters, segs_for_lecture, source)
        for lp in ([s08 / "lecture.md"] if s08 else []) + [abase / "lecture.md"]:
            if lp.parent.exists() or lp == abase / "lecture.md":
                if not dry_run:
                    lp.parent.mkdir(parents=True, exist_ok=True)
                    art.atomic_write_text(lp, lecture)
                info["updated"].append(str(lp.relative_to(root)) if lp.is_relative_to(root) else str(lp))

    # --- knowledge layer (optional, no ASR) ---
    kdir = root / "data" / "knowledge" / video_id
    if (kdir / "chapters.json").is_file():
        try:
            from tcmkb_core.knowledge import (
                KChapter, KEntity, KnowledgePoint, t_url, youtube_t_url,
            )
            from tcmkb_ingest.knowledge.build import render_outline
            from tcmkb_ingest.knowledge.episode import Episode, load_episode

            def _rewrite_k_cite(cit_in: dict[str, Any] | None, start_s: float,
                                end_s: float | None = None) -> dict[str, Any]:
                """Align knowledge citation with ingest cite: url=YouTube page, t_url=site."""
                cit = dict(cit_in or {})
                y = cit.get("youtube_id") or source.get("youtube_id")
                cit["video_id"] = video_id
                cit["t_url"] = t_url(video_id, start_s)
                cit["start_s"] = float(cit.get("start_s", start_s))
                if end_s is not None and cit.get("end_s") is None:
                    cit["end_s"] = float(end_s)
                if y:
                    cit["youtube_id"] = y
                    cit["youtube_t_url"] = youtube_t_url(y, start_s)
                    cit["url"] = f"https://www.youtube.com/watch?v={y}"
                else:
                    # keep non-YouTube source url if present; drop stale site-style url
                    src_url = source.get("url")
                    if src_url:
                        cit["url"] = src_url
                    elif isinstance(cit.get("url"), str) and cit["url"].startswith("/watch/"):
                        cit["url"] = None
                return cit

            kch = json.loads((kdir / "chapters.json").read_text(encoding="utf-8"))
            yid = source.get("youtube_id") or (
                (kch[0].get("citation") or {}).get("youtube_id") if kch else None)
            for ch in kch:
                start_s = float((ch.get("citation") or {}).get("start_s", ch["start_s"]))
                ch["citation"] = _rewrite_k_cite(ch.get("citation"), start_s, ch.get("end_s"))
                # ensure series/episode/title for KCitation validation when re-rendering outline
                cit = ch["citation"]
                cit.setdefault("series", source.get("series_id") or video_id.split("-", 1)[0])
                cit.setdefault("episode", int(source.get("episode") or 0))
                cit.setdefault("title", source.get("title") or (m.title if m else None) or video_id)
            if not dry_run:
                art.atomic_write_json(kdir / "chapters.json", kch)
            info["updated"].append(f"data/knowledge/{video_id}/chapters.json")

            kp_rows: list[dict] = []
            kp_p = kdir / "knowledge_points.jsonl"
            if kp_p.is_file():
                kp_rows = [json.loads(x) for x in kp_p.read_text(encoding="utf-8").splitlines() if x.strip()]
                for k in kp_rows:
                    start_s = float((k.get("citation") or {}).get("start_s", k["start_s"]))
                    k["citation"] = _rewrite_k_cite(k.get("citation"), start_s, k.get("end_s"))
                    cit = k["citation"]
                    cit.setdefault("series", source.get("series_id") or video_id.split("-", 1)[0])
                    cit.setdefault("episode", int(source.get("episode") or 0))
                    cit.setdefault("title", source.get("title") or (m.title if m else None) or video_id)
                if not dry_run:
                    art.atomic_write_text(
                        kp_p, "".join(json.dumps(k, ensure_ascii=False) + "\n" for k in kp_rows))
                info["updated"].append(f"data/knowledge/{video_id}/knowledge_points.jsonl")

            ent_rows: list[dict] = []
            ent_p = kdir / "entities.jsonl"
            if ent_p.is_file():
                ent_rows = [json.loads(x) for x in ent_p.read_text(encoding="utf-8").splitlines() if x.strip()]
                for e in ent_rows:
                    if e.get("first_start_s") is not None:
                        e["first_url"] = t_url(video_id, e["first_start_s"])
                    for ment in e.get("mentions") or []:
                        ment["url"] = t_url(video_id, ment["start_s"])
                if not dry_run:
                    art.atomic_write_text(
                        ent_p, "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in ent_rows))
                info["updated"].append(f"data/knowledge/{video_id}/entities.jsonl")

            # Re-render outline.md with the same helper as knowledge-build
            try:
                chapters_m = [KChapter.model_validate(c) for c in kch]
                kps_m = [KnowledgePoint.model_validate(k) for k in kp_rows]
                ents_m = [KEntity.model_validate(e) for e in ent_rows]
                try:
                    ep = load_episode(root, video_id)
                except Exception:
                    cit0 = (kch[0].get("citation") or {}) if kch else {}
                    ep = Episode(
                        video_id=video_id,
                        series=cit0.get("series") or source.get("series_id")
                               or video_id.split("-", 1)[0],
                        episode=int(cit0.get("episode") or source.get("episode") or 0),
                        title=cit0.get("title") or source.get("title")
                              or (m.title if m else None) or video_id,
                        youtube_id=cit0.get("youtube_id") or yid,
                        duration_s=float(max((c.get("end_s") or 0) for c in kch) if kch else 0),
                        segments=[],
                    )
                outline = render_outline(ep, chapters_m, kps_m, ents_m)
                if not dry_run:
                    art.atomic_write_text(kdir / "outline.md", outline)
                info["updated"].append(f"data/knowledge/{video_id}/outline.md")
            except Exception as oe:
                info["outline_error"] = str(oe)
                log.warning("outline re-render %s: %s", video_id, oe)
        except Exception as e:
            info["knowledge_error"] = str(e)
            log.warning("knowledge backfill %s: %s", video_id, e)

    info["n_segments_rewritten"] = n_seg
    info["n_chapters"] = len(chapters)
    log.info("backfill cites %s segs=%d chapters=%d files=%d", video_id, n_seg, len(chapters),
             len(info["updated"]))
    return info


def backfill_many(root: pathlib.Path, video_ids: list[str] | None = None, *,
                  dry_run: bool = False) -> dict[str, Any]:
    pipe = load_pipeline_config(root)
    abase = root / pipe.get("artifacts_dir", "data/artifacts")
    if video_ids is None:
        found = []
        for p in abase.iterdir():
            if not p.is_dir():
                continue
            if (p / "segments.jsonl").is_file() or any(p.glob("s06_clean/*/segments.jsonl")):
                found.append(p.name)
        video_ids = sorted(found)
    results = [backfill_video(root, v, dry_run=dry_run) for v in video_ids]
    return {"n": len(results), "dry_run": dry_run, "items": results}
