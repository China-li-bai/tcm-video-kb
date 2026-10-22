"""Load one episode's transcript segments, heuristic chapters and citation source."""
from __future__ import annotations
import json, pathlib
from dataclasses import dataclass, field
from typing import Any

from tcmkb_core.config import load_pipeline_config


@dataclass
class Episode:
    video_id: str
    series: str
    episode: int
    title: str
    youtube_id: str | None
    duration_s: float
    segments: list[dict[str, Any]]
    s08_chapters: list[dict[str, Any]] = field(default_factory=list)

    @property
    def by_seq(self) -> dict[int, dict[str, Any]]:
        return {s["seq"]: s for s in self.segments}


def _active_file(root: pathlib.Path, video_id: str, step: str, name: str) -> pathlib.Path | None:
    pipe = load_pipeline_config(root)
    abase = root / pipe.get("artifacts_dir", "data/artifacts") / video_id
    dbp = root / pipe.get("state_db", "data/state.sqlite")
    if dbp.exists():
        try:
            from tcmkb_ingest.state import StateDB
            db = StateDB(dbp)
            try:
                m = db.get_video(video_id)
            finally:
                db.close()
            vk = (m.active_versions or {}).get(step) if m else None
            if vk and (abase / step / vk / name).is_file():
                return abase / step / vk / name
        except Exception:  # pragma: no cover - db busy/corrupt: fall back to copies
            pass
    cands = sorted((abase / step).glob(f"*/{name}"), key=lambda p: p.stat().st_mtime)
    if cands:
        return cands[-1]
    top = abase / name
    return top if top.is_file() else None


def load_episode(root: pathlib.Path, video_id: str) -> Episode:
    sp = _active_file(root, video_id, "s07_flag", "segments.jsonl") \
        or _active_file(root, video_id, "s06_clean", "segments.jsonl")
    if not sp:
        raise FileNotFoundError(f"{video_id}: no segments.jsonl (run s06/s07 first)")
    segs = [json.loads(x) for x in sp.read_text(encoding="utf-8").splitlines() if x.strip()]
    if not segs:
        raise ValueError(f"{video_id}: empty segments")
    cp = _active_file(root, video_id, "s08_chapter", "chapters.json")
    chaps = json.loads(cp.read_text(encoding="utf-8")) if cp else []
    c = segs[0].get("cite") or {}
    series = c.get("series_id") or video_id.split("-", 1)[0]
    purged = root / "data" / "media" / series / "_purged.json"
    rec: dict[str, Any] = {}
    if purged.exists():
        rec = (json.loads(purged.read_text(encoding="utf-8")).get("items") or {}).get(video_id) or {}
    return Episode(
        video_id=video_id, series=series,
        episode=int(c.get("episode") or rec.get("episode") or 0),
        title=c.get("title") or rec.get("title") or video_id,
        youtube_id=c.get("youtube_id") or rec.get("youtube_id"),
        duration_s=float(rec.get("duration_s") or segs[-1]["end_s"]),
        segments=segs, s08_chapters=chaps,
    )
