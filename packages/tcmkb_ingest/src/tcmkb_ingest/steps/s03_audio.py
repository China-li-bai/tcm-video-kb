"""s03_audio: extract 16 kHz mono wav and split into parts <= max_part_s at silences.

Long lectures (1-2 h) are cut into ~20 min parts so s04 never holds more than one
part's audio/features in memory; cut points are chosen at the longest silence
(ffmpeg silencedetect) within `split_search_s` before each max_part_s boundary,
falling back to a hard cut. Each part records offset_s; s04 adds it back.
"""
from __future__ import annotations
import pathlib, re, shutil, subprocess, wave
from tcmkb_ingest import artifacts as art
from tcmkb_ingest.steps.base import Ctx, log

_SIL_START = re.compile(r"silence_start:\s*([0-9.]+)")
_SIL_END = re.compile(r"silence_end:\s*([0-9.]+)")


def wav_duration(path: pathlib.Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate() or 1)


def parse_silencedetect(stderr: str) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    start = None
    for line in stderr.splitlines():
        m = _SIL_START.search(line)
        if m:
            start = float(m.group(1))
            continue
        m = _SIL_END.search(line)
        if m and start is not None:
            out.append((start, float(m.group(1))))
            start = None
    return out


def plan_cuts(duration: float, silences: list[tuple[float, float]], max_part_s: float,
              search_s: float = 120.0) -> list[float]:
    """Return cut times (seconds) so every part is <= max_part_s.

    For each boundary, pick the longest silence whose midpoint lies in
    (target - search_s, target]; cut at its midpoint. Else hard-cut at target.
    """
    cuts: list[float] = []
    last = 0.0
    while duration - last > max_part_s:
        target = last + max_part_s
        lo = max(last + 1.0, target - search_s)
        cands = [(e - s, (s + e) / 2) for s, e in silences if lo < (s + e) / 2 <= target]
        cut = max(cands)[1] if cands else target
        cuts.append(round(cut, 3))
        last = cut
    return cuts


def _silences(path: pathlib.Path, noise_db: float, min_sil_s: float) -> list[tuple[float, float]]:
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
         f"silencedetect=noise={noise_db}dB:d={min_sil_s}", "-f", "null", "-"],
        capture_output=True, text=True, timeout=3600,
    )
    return parse_silencedetect(r.stderr)


def run(ctx: Ctx, **_kw) -> dict:
    step = "s03_audio"
    cfg = ctx.step_cfg(step)
    sr = int(cfg.get("sample_rate", 16000))
    ch = int(cfg.get("channels", 1))
    max_part = float(cfg.get("max_part_s", 1200))
    search_s = float(cfg.get("split_search_s", 120))
    noise_db = float(cfg.get("silence_noise_db", -35))
    min_sil = float(cfg.get("silence_min_s", 0.4))
    m = ctx.state.get_video(ctx.video_id)
    if not m:
        raise RuntimeError(f"{ctx.video_id} not registered")
    src = pathlib.Path(m.source_path)
    up = (m.active_versions or {}).get("s02_media", "") or (m.active_versions or {}).get("s01_upload", "")
    frag = {"sr": sr, "ch": ch, "max_part_s": max_part, "split_search_s": search_s,
            "silence_noise_db": noise_db, "silence_min_s": min_sil}
    vk = ctx.compute_vk(step, frag, upstream_hash=up or m.source_sha256[:16])
    existing = ctx.state.find_done(ctx.video_id, step, vk)
    if existing and not ctx.force:
        log.info("skip %s %s", ctx.video_id, step)
        return {"skipped": True, "version_key": vk}

    ctx.state.ensure_step(ctx.video_id, step, vk)
    ctx.state.claim(ctx.video_id, step, vk, ctx.worker_id)
    outdir = ctx.outdir(step, vk)
    wav_dir = outdir / "audio"
    if wav_dir.exists():
        shutil.rmtree(wav_dir)
    wav_dir.mkdir(parents=True, exist_ok=True)
    full = wav_dir / "full.wav"

    ext = (m.ext or src.suffix.lstrip(".")).lower()
    copied = False
    if ext == "wav":
        try:
            with wave.open(str(src), "rb") as w:
                if w.getframerate() == sr and w.getnchannels() == ch and w.getsampwidth() == 2:
                    shutil.copy2(src, full)
                    copied = True
        except Exception:
            copied = False
    if not copied:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vn", "-ac", str(ch),
             "-ar", str(sr), "-c:a", "pcm_s16le", str(full)],
            capture_output=True, check=True, timeout=3 * 3600,
        )
    duration = wav_duration(full)

    cuts: list[float] = []
    if duration > max_part:
        cuts = plan_cuts(duration, _silences(full, noise_db, min_sil), max_part, search_s)
    bounds = [0.0, *cuts, duration]
    parts = []
    if not cuts:
        target = wav_dir / "part_000.wav"
        full.rename(target)
        parts.append({"part": 0, "offset_s": 0.0, "duration_s": round(duration, 3),
                      "path": "audio/part_000.wav"})
    else:
        for i, (a, b) in enumerate(zip(bounds[:-1], bounds[1:])):
            target = wav_dir / f"part_{i:03d}.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(full), "-ss", f"{a:.3f}",
                 "-t", f"{b - a:.3f}", "-c:a", "pcm_s16le", str(target)],
                capture_output=True, check=True, timeout=3600,
            )
            parts.append({"part": i, "offset_s": round(a, 3),
                          "duration_s": round(wav_duration(target), 3),
                          "path": f"audio/part_{i:03d}.wav"})
        full.unlink()

    art.atomic_write_json(outdir / "parts.json",
                          {"parts": parts, "sample_rate": sr, "channels": ch,
                           "duration_s": round(duration, 3), "cuts_s": cuts})
    for p in parts:
        # R2 stub: LocalStorage mirror only (no cloud upload)
        ctx.storage.put_file(f"artifacts/{ctx.video_id}/{p['path']}", outdir / p["path"])
    oh = art.hash_dir_files(outdir, ["parts.json", *[p["path"] for p in parts]])
    metrics = {"n_parts": len(parts), "duration_s": round(duration, 3), "cuts_s": cuts}
    art.write_success(outdir, metrics, oh)
    m.active_versions[step] = vk
    ctx.state.upsert_video(m)
    ctx.state.mark_done(ctx.video_id, step, vk, str(outdir), oh, metrics)
    log.info("s03 audio %s parts=%d dur=%.1fs cuts=%s", ctx.video_id, len(parts), duration, cuts)
    return {"version_key": vk, "outdir": str(outdir), "parts": parts}
