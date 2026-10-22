"""Media catalog: local file <-> YouTube source (id / URL / title / series / episode).

Inputs (all already on disk, nothing fetched):
- data/media/{series}/_playlist.txt  (yt-dlp flat playlist: idx \t id \t duration \t title)
- data/media/{series}/_manifest.json (scripts/build_media_manifest.py: size / ffprobe duration)
- configs/sources/youtube_renji.yaml (series title, playlist URL, channel)
- configs/series.yaml                (series title fallback)

Local files are named `{series}-{idx}.m4a`, so video_id = `{series}-{idx}` and the
playlist row with the same idx gives the YouTube id. The resulting `source` dict is
stored in video.meta["source"] at s00 and copied into every transcript segment /
chapter as a citation (`cite()`), so the knowledge layer links to
https://www.youtube.com/watch?v=<id>&t=<sec>s instead of local files.
"""
from __future__ import annotations
import json, math, pathlib, time
from dataclasses import dataclass, field, asdict
from typing import Any

import yaml

from tcmkb_core.config import load_series_config

AUDIO_EXTS = (".m4a", ".webm", ".opus", ".mp3", ".aac", ".wav", ".flac", ".mp4")
YT_WATCH = "https://www.youtube.com/watch?v="


def youtube_url(youtube_id: str, t: float | None = None) -> str:
    u = f"{YT_WATCH}{youtube_id}"
    if t is not None:
        u += f"&t={max(int(math.floor(float(t))), 0)}s"
    return u


@dataclass
class MediaEntry:
    video_id: str
    series_id: str
    episode: int
    idx: str
    youtube_id: str | None = None
    url: str | None = None
    title: str = ""
    series_title: str = ""
    playlist_url: str | None = None
    channel: str | None = None
    duration_s: float = 0.0          # playlist (or ffprobe manifest) duration
    file: str | None = None          # local media path if present
    size_bytes: int = 0
    mtime: float = 0.0
    extra: dict[str, Any] = field(default_factory=dict)

    def source(self) -> dict[str, Any]:
        """Citation block stored in video.meta['source'] and copied into outputs."""
        return {
            "platform": "youtube" if self.youtube_id else "local",
            "youtube_id": self.youtube_id,
            "url": self.url,
            "title": self.title,
            "series_id": self.series_id,
            "series_title": self.series_title,
            "episode": self.episode,
            "playlist_url": self.playlist_url,
            "channel": self.channel,
            "duration_s": self.duration_s or None,
        }

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def cite(source: dict[str, Any] | None, start_s: float, end_s: float) -> dict[str, Any] | None:
    """Per-segment / per-chapter citation. None when the video has no source metadata."""
    if not source:
        return None
    yid = source.get("youtube_id")
    return {
        "youtube_id": yid,
        "url": source.get("url") or (youtube_url(yid) if yid else None),
        "t_url": youtube_url(yid, start_s) if yid else None,
        "title": source.get("title"),
        "series_id": source.get("series_id"),
        "series_title": source.get("series_title"),
        "episode": source.get("episode"),
        "start_s": round(float(start_s), 3),
        "end_s": round(float(end_s), 3),
    }


def parse_playlist(text: str) -> list[dict[str, Any]]:
    rows = []
    for ln in text.splitlines():
        if not ln.strip():
            continue
        parts = ln.split("\t")
        if len(parts) < 2:
            continue
        idx, yid = parts[0].strip(), parts[1].strip()
        dur = parts[2].strip() if len(parts) > 2 else ""
        try:
            d = float(dur)
        except ValueError:
            d = 0.0
        rows.append({"idx": idx, "youtube_id": yid, "duration_s": d,
                     "title": "\t".join(parts[3:]).strip() if len(parts) > 3 else ""})
    return rows


def _series_meta(root: pathlib.Path, series_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {"series_title": "", "playlist_url": None, "channel": None}
    for s in (load_series_config(root).get("series") or []):
        if s.get("series_id") == series_id:
            out["series_title"] = s.get("title") or ""
    p = root / "configs" / "sources" / "youtube_renji.yaml"
    if p.exists():
        try:
            y = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            y = {}
        s = (y.get("series") or {}).get(series_id) or {}
        best = s.get("best") or {}
        out["series_title"] = out["series_title"] or s.get("title") or ""
        out["playlist_url"] = best.get("url")
        out["channel"] = best.get("channel")
    return out


def media_dir(root: pathlib.Path, series_id: str) -> pathlib.Path:
    return root / "data" / "media" / series_id


def load_catalog(root: pathlib.Path, series_id: str) -> list[MediaEntry]:
    """Every playlist row of a series (downloaded or not), joined with local files."""
    d = media_dir(root, series_id)
    meta = _series_meta(root, series_id)
    pl = d / "_playlist.txt"
    rows = parse_playlist(pl.read_text(encoding="utf-8")) if pl.exists() else []
    man: dict[str, dict[str, Any]] = {}
    mp = d / "_manifest.json"
    if mp.exists():
        try:
            for f in json.loads(mp.read_text(encoding="utf-8")).get("files") or []:
                man[pathlib.Path(f["file"]).stem] = f
        except Exception:
            pass
    by_idx = {r["idx"]: r for r in rows}
    # local files not in the playlist still get an entry (no URL)
    local: dict[str, pathlib.Path] = {}
    if d.is_dir():
        for p in sorted(d.iterdir()):
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS and p.stem.startswith(f"{series_id}-"):
                idx = p.stem[len(series_id) + 1:]
                if idx not in local or p.suffix.lower() == ".m4a":
                    local[idx] = p
    out: list[MediaEntry] = []
    for idx in sorted(set(by_idx) | set(local), key=lambda s: (len(s), s)):
        r = by_idx.get(idx, {})
        yid = r.get("youtube_id")
        try:
            ep = int(idx)
        except ValueError:
            ep = 0
        e = MediaEntry(
            video_id=f"{series_id}-{idx}", series_id=series_id, episode=ep, idx=idx,
            youtube_id=yid, url=youtube_url(yid) if yid else None,
            title=r.get("title") or "", series_title=meta["series_title"],
            playlist_url=meta["playlist_url"], channel=meta["channel"],
            duration_s=float(r.get("duration_s") or 0.0),
        )
        p = local.get(idx)
        if p is not None:
            st = p.stat()
            e.file, e.size_bytes, e.mtime = str(p.resolve()), st.st_size, st.st_mtime
            mf = man.get(p.stem)
            if mf and mf.get("duration_sec"):
                e.extra["probed_duration_s"] = float(mf["duration_sec"])
                if not e.duration_s:
                    e.duration_s = float(mf["duration_sec"])
        out.append(e)
    return out


def is_stable(e: MediaEntry, *, min_age_s: float = 120.0, now: float | None = None) -> bool:
    """A local file is safe to ingest: not being written by the downloader."""
    if not e.file:
        return False
    p = pathlib.Path(e.file)
    if (p.parent / f"{p.stem}.sections").exists():   # sectioned download still in progress
        return False
    now = time.time() if now is None else now
    return (now - e.mtime) >= min_age_s and e.size_bytes > 4096
