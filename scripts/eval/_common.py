"""Shared helpers for quality spot-check samplers (ASR windows / KP review)."""
from __future__ import annotations

import csv
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parents[2]
ARTIFACTS = REPO / "data" / "artifacts"
KNOWLEDGE = REPO / "data" / "knowledge"
LEXICON_ENTRIES = REPO / "lexicon" / "entries"
STATE_DB = REPO / "data" / "state.sqlite"
KP_INDEX = KNOWLEDGE / "_index" / "knowledge_points.csv"

# zj short 目录 clips under data/media/zj/_incomplete — leave alone for eval.
INCOMPLETE_ZJ = frozenset(
    {
        "zj-001",
        "zj-009",
        "zj-018",
        "zj-027",
        "zj-035",
        "zj-044",
        "zj-053",
        "zj-061",
        "zj-070",
        "zj-079",
        "zj-085",
        # also known short/orphan catalog clips
        "zj-060",
        "zj-078",
    }
)

SERIES_ORDER = ("shl", "zj", "nj", "jgy", "bc")

_TERM_RE = re.compile(r"^\s+term:\s*[\"']?([^\s\"'#]+)", re.M)
_ALIAS_RE = re.compile(r"^\s+aliases:\s*\[([^\]]*)\]", re.M)
_ALIAS_ITEM_RE = re.compile(r"[\"']([^\"']+)[\"']|([\u4e00-\u9fff]{2,12})")


def load_lexicon_terms(min_len: int = 2, max_len: int = 8) -> list[str]:
    """Parse term/alias surfaces from lexicon/entries/*.yaml without requiring PyYAML."""
    terms: set[str] = set()
    if not LEXICON_ENTRIES.is_dir():
        return []
    for path in sorted(LEXICON_ENTRIES.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        for m in _TERM_RE.finditer(text):
            t = m.group(1).strip()
            if min_len <= len(t) <= max_len:
                terms.add(t)
        for m in _ALIAS_RE.finditer(text):
            for am in _ALIAS_ITEM_RE.finditer(m.group(1)):
                t = (am.group(1) or am.group(2) or "").strip()
                if min_len <= len(t) <= max_len:
                    terms.add(t)
    # longest first for greedy density count
    return sorted(terms, key=len, reverse=True)


def term_density(text: str, terms: list[str]) -> tuple[float, list[str]]:
    """Return (hits_per_100_chars, matched surfaces) for ranking ASR windows.

    Counts non-overlapping leftmost-longest hits via str.find on a working copy.
    """
    if not text or not terms:
        return 0.0, []
    work = text
    matched: list[str] = []
    for t in terms:
        if len(t) < 2:
            continue
        start = 0
        while True:
            i = work.find(t, start)
            if i < 0:
                break
            matched.append(t)
            work = work[:i] + (" " * len(t)) + work[i + len(t) :]
            start = i + len(t)
    dens = 100.0 * len(matched) / max(len(text), 1)
    return dens, matched



def knowledge_video_ids(series: str | None = None) -> list[str]:
    vids = sorted(
        p.name
        for p in KNOWLEDGE.iterdir()
        if p.is_dir() and not p.name.startswith("_") and "-" in p.name
    )
    if series:
        vids = [v for v in vids if v.startswith(series + "-")]
    return vids


def skip_video(video_id: str) -> bool:
    if video_id in INCOMPLETE_ZJ:
        return True
    if video_id.endswith("-demo"):
        return True
    return False


def load_segments(video_id: str) -> list[dict[str, Any]]:
    path = ARTIFACTS / video_id / "segments.jsonl"
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def video_duration_s(video_id: str, segments: list[dict[str, Any]] | None = None) -> float:
    if STATE_DB.is_file():
        try:
            con = sqlite3.connect(STATE_DB)
            row = con.execute(
                "SELECT duration_s FROM video WHERE video_id=?", (video_id,)
            ).fetchone()
            con.close()
            if row and row[0]:
                return float(row[0])
        except sqlite3.Error:
            pass
    segs = segments if segments is not None else load_segments(video_id)
    if segs:
        return float(segs[-1].get("end_s") or 0)
    return 0.0


def youtube_from_segments(segments: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    for seg in segments:
        cite = seg.get("cite") or {}
        yid = cite.get("youtube_id")
        url = cite.get("url")
        if yid or url:
            return yid, url
    return None, None


def youtube_t_url(youtube_id: str | None, url: str | None, t_s: float) -> str:
    t = int(max(0, t_s))
    if youtube_id:
        return f"https://www.youtube.com/watch?v={youtube_id}&t={t}s"
    if url:
        base = url.split("&t=")[0].split("?t=")[0]
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}t={t}s"
    return ""


def lecture_md_path(video_id: str) -> str:
    p = ARTIFACTS / video_id / "lecture.md"
    return str(p.relative_to(REPO)) if p.is_file() else ""


def segments_path(video_id: str) -> str:
    p = ARTIFACTS / video_id / "segments.jsonl"
    return str(p.relative_to(REPO)) if p.is_file() else ""


def outline_path(video_id: str) -> str:
    p = KNOWLEDGE / video_id / "outline.md"
    return str(p.relative_to(REPO)) if p.is_file() else ""


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})
    return len(rows)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def load_kp_index() -> list[dict[str, str]]:
    with KP_INDEX.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def group_by(rows: list[dict[str, Any]], key: str) -> dict[Any, list[dict[str, Any]]]:
    g: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        g[r.get(key)].append(r)
    return g
