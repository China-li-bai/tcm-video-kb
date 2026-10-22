"""s08_chapter: heuristic chapterer + lecture.md; optional LLM if API key present."""
from __future__ import annotations
import json, os, pathlib, re
from typing import Any
from tcmkb_ingest import artifacts as art
from tcmkb_ingest.steps.base import Ctx, log

def _fmt_ts(s: float) -> str:
    s = max(0, int(s))
    return f"{s // 60:02d}:{s % 60:02d}"

def _load_segments(ctx: Ctx) -> list[dict[str, Any]]:
    # Prefer s07, fall back to s06
    for step in ("s07_flag", "s06_clean"):
        d = ctx.active_outdir(step)
        if d and (d / "segments.jsonl").exists():
            return [json.loads(l) for l in (d / "segments.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    raise RuntimeError("no segments from s06/s07")

def heuristic_chapters(segs: list[dict[str, Any]], *, silence_gap_s: float = 3.0,
                       min_chapter_s: float = 60.0, max_chapter_s: float = 1500.0,
                       target_chapter_s: float = 300.0) -> list[dict[str, Any]]:
    if not segs:
        return []
    # Candidate boundaries: large gaps between sentences, or every ~target_chapter_s
    boundaries = [0]  # segment indices where a new chapter starts
    last_start_s = float(segs[0]["start_s"])
    for i in range(1, len(segs)):
        gap = float(segs[i]["start_s"]) - float(segs[i - 1]["end_s"])
        dur_so_far = float(segs[i]["start_s"]) - last_start_s
        if gap >= silence_gap_s and dur_so_far >= min_chapter_s:
            boundaries.append(i)
            last_start_s = float(segs[i]["start_s"])
        elif dur_so_far >= max_chapter_s:
            boundaries.append(i)
            last_start_s = float(segs[i]["start_s"])
        elif dur_so_far >= target_chapter_s and gap >= 0.8:
            boundaries.append(i)
            last_start_s = float(segs[i]["start_s"])
    boundaries.append(len(segs))

    # Merge too-short final/middle chapters
    chapters = []
    for bi, (a, b) in enumerate(zip(boundaries[:-1], boundaries[1:])):
        if a >= b:
            continue
        chunk = segs[a:b]
        start_s = float(chunk[0]["start_s"])
        end_s = float(chunk[-1]["end_s"])
        text = "".join(s["text"] for s in chunk)
        title = _guess_title(text, seq=len(chapters) + 1)
        summary = text[:120] + ("…" if len(text) > 120 else "")
        chapters.append({
            "seq": len(chapters) + 1,
            "title": title,
            "start_s": round(start_s, 3),
            "end_s": round(end_s, 3),
            "summary": summary,
            "key_points": _key_points(text),
            "clause_refs": [],
            "node_id": None,
            "review_status": "auto",
            "seg_from": a,
            "seg_to": b - 1,
        })

    # Merge chapters shorter than min_chapter_s into previous
    merged: list[dict[str, Any]] = []
    for ch in chapters:
        if merged and (ch["end_s"] - ch["start_s"]) < min_chapter_s:
            prev = merged[-1]
            prev["end_s"] = ch["end_s"]
            prev["seg_to"] = ch["seg_to"]
            prev["summary"] = (prev["summary"] + ch["summary"])[:200]
            continue
        merged.append(ch)
    for i, ch in enumerate(merged):
        ch["seq"] = i + 1
    return merged

_ACU = re.compile(r"(足三里|合谷|内关|三阴交|上巨虚|下巨虚|阑尾穴|梁丘|伏兔|髀关|补泻|胃气|经络|穴位)")
_FORMULA = re.compile(r"(桂枝汤|麻黄汤|小柴胡汤|白虎汤|承气汤|乌梅丸|经方|伤寒论|黄帝内经)")

def _guess_title(text: str, seq: int) -> str:
    for rx in (_ACU, _FORMULA):
        m = rx.search(text[:400])
        if m:
            return f"{m.group(1)}（第{seq}节）"
    kp = _key_points(text, n=1)
    if kp:
        return f"{kp[0]}（第{seq}节）"
    clean = re.sub(r"[，。！？、\s]+", "", text)[:12]
    return clean or f"第{seq}节"

def _key_points(text: str, n: int = 3) -> list[str]:
    hits = []
    for rx in (_ACU, _FORMULA):
        for m in rx.finditer(text):
            if m.group(1) not in hits:
                hits.append(m.group(1))
            if len(hits) >= n:
                return hits
    return hits

def render_lecture_md(video_id: str, title: str, chapters: list[dict], segs: list[dict],
                      source: dict | None = None) -> str:
    lines = [f"# {title or video_id}", "", f"video_id: `{video_id}`", ""]
    if source and source.get("url"):
        lines += [f"source: [{source.get('title') or source['url']}]({source['url']})"
                  f" — {source.get('series_title') or source.get('series_id')}"
                  f" 第{source.get('episode')}集", ""]
    for ch in chapters:
        link = (ch.get("cite") or {}).get("t_url")
        ts = f"[{_fmt_ts(ch['start_s'])}–{_fmt_ts(ch['end_s'])}]"
        lines.append(f"## {ch['seq']}. {ch['title']}  " + (f"[{ts}]({link})" if link else ts))
        lines.append("")
        if ch.get("summary"):
            lines.append(f"> {ch['summary']}")
            lines.append("")
        if ch.get("key_points"):
            lines.append("要点：" + "、".join(ch["key_points"]))
            lines.append("")
        a, b = ch.get("seg_from", 0), ch.get("seg_to", 0)
        for s in segs[a: b + 1]:
            lines.append(f"- [{_fmt_ts(s['start_s'])}] {s['text']}")
        lines.append("")
    return "\n".join(lines)

def _try_llm_chapters(ctx: Ctx, segs: list[dict]) -> list[dict] | None:
    """Optional LLM chaptering when OPENAI_API_KEY (or TCMKB_LLM_API_KEY) is set."""
    key = os.environ.get("TCMKB_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    base = os.environ.get("TCMKB_LLM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
    model = os.environ.get("TCMKB_LLM_MODEL", "gpt-4o-mini")
    prompt_path = ctx.root / "configs" / "prompts" / "chaptering.v1.md"
    system = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "Divide into chapters as JSON."
    body_lines = [f"[{_fmt_ts(s['start_s'])}] {s['text']}" for s in segs]
    # Cap input for safety
    user = "\n".join(body_lines[:400])
    try:
        import urllib.request
        req = urllib.request.Request(
            f"{base.rstrip('/')}/chat/completions",
            data=json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
            }).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        # Extract JSON array
        m = re.search(r"\[.*\]", content, re.S)
        if not m:
            return None
        arr = json.loads(m.group(0))
        out = []
        for i, ch in enumerate(arr):
            out.append({
                "seq": i + 1,
                "title": ch.get("title") or f"第{i+1}节",
                "start_s": float(ch["start_s"]),
                "end_s": float(ch["end_s"]),
                "summary": ch.get("summary") or "",
                "key_points": ch.get("key_points") or [],
                "clause_refs": ch.get("clause_refs") or [],
                "node_id": ch.get("node_id"),
                "review_status": "auto",
            })
        return out
    except Exception as e:
        log.warning("LLM chaptering failed, falling back to heuristic: %s", e)
        return None

def run(ctx: Ctx, **_kw) -> dict:
    step = "s08_chapter"
    m = ctx.state.get_video(ctx.video_id)
    if not m:
        raise RuntimeError(f"{ctx.video_id} not registered")
    cfg = ctx.step_cfg(step)
    mode = cfg.get("mode", "heuristic")
    source = (m.meta or {}).get("source")
    frag = {
        "cite": (source or {}).get("youtube_id") or (source or {}).get("url"),
        "mode": mode,
        "silence_gap_s": cfg.get("silence_gap_s", 3.0),
        "min_chapter_s": cfg.get("min_chapter_s", 60.0),
        "max_chapter_s": cfg.get("max_chapter_s", 1500.0),
        "target_chapter_s": cfg.get("target_chapter_s", 300.0),
    }
    up = (m.active_versions or {}).get("s07_flag") or (m.active_versions or {}).get("s06_clean", "")
    vk = ctx.compute_vk(step, frag, upstream_hash=up)
    existing = ctx.state.find_done(ctx.video_id, step, vk)
    if existing and not ctx.force:
        log.info("skip %s %s", ctx.video_id, step)
        return {"skipped": True, "version_key": vk}

    segs = _load_segments(ctx)
    ctx.state.ensure_step(ctx.video_id, step, vk)
    ctx.state.claim(ctx.video_id, step, vk, ctx.worker_id)
    outdir = ctx.outdir(step, vk)

    chapters = None
    used_mode = "heuristic"
    if mode == "llm" or (mode == "heuristic" and (os.environ.get("TCMKB_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"))):
        chapters = _try_llm_chapters(ctx, segs)
        if chapters:
            used_mode = "llm"
    if not chapters:
        chapters = heuristic_chapters(
            segs,
            silence_gap_s=float(frag["silence_gap_s"]),
            min_chapter_s=float(frag["min_chapter_s"]),
            max_chapter_s=float(frag["max_chapter_s"]),
            target_chapter_s=float(frag["target_chapter_s"]),
        )

    # Snap boundaries to sentence starts; ensure coverage
    if chapters and segs:
        chapters[0]["start_s"] = float(segs[0]["start_s"])
        chapters[-1]["end_s"] = float(segs[-1]["end_s"])

    from tcmkb_ingest.sources import cite
    for ch in chapters:
        ch["cite"] = cite(source, ch["start_s"], ch["end_s"])
    art.atomic_write_json(outdir / "chapters.json", chapters)
    lecture = render_lecture_md(ctx.video_id, m.title, chapters, segs, source)
    art.atomic_write_text(outdir / "lecture.md", lecture)
    # Demo pointers
    art.atomic_write_json(ctx.artifacts_base / ctx.video_id / "chapters.json", chapters)
    art.atomic_write_text(ctx.artifacts_base / ctx.video_id / "lecture.md", lecture)

    metrics = {"n_chapters": len(chapters), "mode": used_mode,
               "duration_s": chapters[-1]["end_s"] if chapters else 0.0}
    oh = art.hash_dir_files(outdir, ["chapters.json", "lecture.md"])
    art.write_success(outdir, metrics, oh)
    m.active_versions[step] = vk
    ctx.state.upsert_video(m)
    ctx.state.mark_done(ctx.video_id, step, vk, str(outdir), oh, metrics)
    log.info("s08 chapter %s n=%d mode=%s", ctx.video_id, len(chapters), used_mode)
    return {"version_key": vk, "outdir": str(outdir), "metrics": metrics}
