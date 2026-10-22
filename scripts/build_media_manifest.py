#!/usr/bin/env python3
"""Build _manifest.json for a media/{series}/ folder via ffprobe.

Each file is mapped to its YouTube source from _playlist.txt (idx, id, duration,
title) and configs/sources/youtube_renji.yaml (series title / playlist / channel):
youtube_id, url, title, series, series_title, episode, playlist_duration_sec.
Purged items (data/media/{series}/_purged.json) are listed under "purged" so the
manifest still maps every processed episode to its URL after the audio is gone.
Runs with plain python3 (PyYAML optional).
"""
from __future__ import annotations
import json, os, subprocess, sys, glob
from pathlib import Path
from datetime import datetime, timezone, timedelta

SH = timezone(timedelta(hours=8))

def ffprobe(path: str) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration,size,bit_rate,format_name",
        "-of", "json", path,
    ]
    out = subprocess.check_output(cmd, text=True)
    return json.loads(out).get("format", {})

ROOT = Path(__file__).resolve().parents[1]


def load_playlist(d: Path) -> dict:
    out = {}
    p = d / "_playlist.txt"
    if not p.exists():
        return out
    for ln in p.read_text(encoding="utf-8").splitlines():
        parts = ln.split("\t")
        if len(parts) < 2 or not parts[0].strip():
            continue
        try:
            dur = float(parts[2]) if len(parts) > 2 and parts[2].strip() else None
        except ValueError:
            dur = None
        out[parts[0].strip()] = {"youtube_id": parts[1].strip(), "duration": dur,
                                 "title": "\t".join(parts[3:]).strip() if len(parts) > 3 else ""}
    return out


def series_meta(series: str) -> dict:
    meta = {"series_title": None, "playlist_url": None, "channel": None}
    try:
        import yaml  # optional
        y = yaml.safe_load((ROOT / "configs/sources/youtube_renji.yaml").read_text(encoding="utf-8")) or {}
        s = (y.get("series") or {}).get(series) or {}
        best = s.get("best") or {}
        meta.update(series_title=s.get("title"), playlist_url=best.get("url"), channel=best.get("channel"))
    except Exception:
        # minimal fallback: "  <series>:\n    title: X" from the yaml text
        try:
            lines = (ROOT / "configs/sources/youtube_renji.yaml").read_text(encoding="utf-8").splitlines()
            for i, ln in enumerate(lines):
                if ln.strip() == f"{series}:" and i + 1 < len(lines) and "title:" in lines[i + 1]:
                    meta["series_title"] = lines[i + 1].split("title:", 1)[1].strip()
                    for ln2 in lines[i + 2:]:
                        st = ln2.strip()
                        if ln2.startswith("  ") and not ln2.startswith("   ") and st.endswith(":"):
                            break  # next series
                        if st.startswith("url:") and not meta["playlist_url"]:
                            meta["playlist_url"] = st.split(":", 1)[1].split("#")[0].strip().strip('"')
                        if st.startswith("channel:") and not meta["channel"]:
                            meta["channel"] = st.split(":", 1)[1].strip()
                        if meta["playlist_url"] and meta["channel"]:
                            break
                    break
        except Exception:
            pass
    return meta


def main(series_dir: str, expected: int | None = None) -> None:
    d = Path(series_dir)
    series = d.name
    plist = load_playlist(d)
    smeta = series_meta(series)
    files = sorted(d.glob(f"{series}-*.m4a")) + sorted(d.glob(f"{series}-*.webm")) + sorted(d.glob(f"{series}-*.opus"))
    # de-dup by stem preferring m4a
    by_stem = {}
    for f in files:
        by_stem.setdefault(f.stem, f)
        if f.suffix == ".m4a":
            by_stem[f.stem] = f
    files = [by_stem[k] for k in sorted(by_stem)]
    items = []
    total_dur = 0.0
    total_size = 0
    for f in files:
        meta = ffprobe(str(f))
        dur = float(meta.get("duration") or 0)
        size = int(meta.get("size") or f.stat().st_size)
        total_dur += dur
        total_size += size
        idx = f.stem[len(series) + 1:] if f.stem.startswith(series + "-") else ""
        pl = plist.get(idx) or {}
        yid = pl.get("youtube_id")
        items.append({
            "video_id": f.stem,
            "series": series,
            "series_title": smeta["series_title"],
            "episode": int(idx) if idx.isdigit() else None,
            "youtube_id": yid,
            "url": f"https://www.youtube.com/watch?v={yid}" if yid else None,
            "title": pl.get("title"),
            "playlist_duration_sec": pl.get("duration"),
            "file": f.name,
            "path": str(f),
            "size_bytes": size,
            "duration_sec": round(dur, 2),
            "duration_hms": _hms(dur),
            "bit_rate": meta.get("bit_rate"),
            "format": meta.get("format_name"),
        })
    manifest = {
        "series": series,
        "generated_at": datetime.now(SH).isoformat(),
        "file_count": len(items),
        "expected_count": expected,
        "total_duration_sec": round(total_dur, 2),
        "total_duration_hours": round(total_dur / 3600, 3),
        "total_size_bytes": total_size,
        "total_size_gb": round(total_size / (1024**3), 3),
        "playlist_url": smeta["playlist_url"],
        "channel": smeta["channel"],
        "files": items,
        "purged": _purged(d),
    }
    out = d / "_manifest.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: manifest[k] for k in ("series","file_count","expected_count","total_duration_hours","total_size_gb")}, ensure_ascii=False))

def _purged(d: Path) -> list:
    p = d / "_purged.json"
    if not p.exists():
        return []
    try:
        items = (json.loads(p.read_text(encoding="utf-8")).get("items") or {}).values()
    except ValueError:
        return []
    return [{k: it.get(k) for k in ("video_id", "episode", "youtube_id", "source_url", "title",
                                    "duration_s", "purged_at")} for it in items]


def _hms(sec: float) -> str:
    s = int(round(sec))
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

if __name__ == "__main__":
    exp = int(sys.argv[2]) if len(sys.argv) > 2 else None
    main(sys.argv[1], exp)
