"""s03_audio: extract 16 kHz mono wav parts (≤ max_part_s). Local wav demo = single part."""
from __future__ import annotations
import pathlib, shutil, subprocess
from tcmkb_ingest import artifacts as art
from tcmkb_ingest.steps.base import Ctx, log

def run(ctx: Ctx, **_kw) -> dict:
    step = "s03_audio"
    cfg = ctx.step_cfg(step)
    sr = int(cfg.get("sample_rate", 16000))
    ch = int(cfg.get("channels", 1))
    max_part = float(cfg.get("max_part_s", 1200))
    m = ctx.state.get_video(ctx.video_id)
    if not m:
        raise RuntimeError(f"{ctx.video_id} not registered")
    src = pathlib.Path(m.source_path)
    up = (m.active_versions or {}).get("s02_media", "") or (m.active_versions or {}).get("s01_upload", "")
    frag = {"sr": sr, "ch": ch, "max_part_s": max_part}
    vk = ctx.compute_vk(step, frag, upstream_hash=up or m.source_sha256[:16])
    existing = ctx.state.find_done(ctx.video_id, step, vk)
    if existing and not ctx.force:
        log.info("skip %s %s", ctx.video_id, step)
        return {"skipped": True, "version_key": vk}

    ctx.state.ensure_step(ctx.video_id, step, vk)
    ctx.state.claim(ctx.video_id, step, vk, "local")
    outdir = ctx.outdir(step, vk)
    wav_dir = outdir / "audio"
    wav_dir.mkdir(parents=True, exist_ok=True)
    target = wav_dir / "part_000.wav"

    ext = (m.ext or src.suffix.lstrip(".")).lower()
    # If already 16k mono wav and short enough, copy; else ffmpeg
    need_convert = True
    if ext == "wav" and (m.duration_s or 0) <= max_part:
        # Probe channels/rate quickly
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "a:0",
                 "-show_entries", "stream=sample_rate,channels",
                 "-of", "csv=p=0", str(src)],
                capture_output=True, text=True, check=True, timeout=30,
            )
            parts = r.stdout.strip().split(",")
            if len(parts) >= 2 and int(parts[0]) == sr and int(parts[1]) == ch:
                shutil.copy2(src, target)
                need_convert = False
        except Exception:
            pass

    if need_convert:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-vn", "-ac", str(ch), "-ar", str(sr),
             "-c:a", "pcm_s16le", str(target)],
            capture_output=True, check=True, timeout=1800,
        )

    duration = m.duration_s or 0.0
    if duration <= 0:
        try:
            r = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(target)],
                capture_output=True, text=True, check=True, timeout=30,
            )
            duration = float(r.stdout.strip() or 0)
        except Exception:
            duration = 0.0

    # For MVP: single part (splitting by silence deferred). If longer than max_part, still one part with note.
    parts = [{"part": 0, "offset_s": 0.0, "duration_s": duration, "path": "audio/part_000.wav"}]
    if duration > max_part:
        log.warning("s03 %s duration %.0fs > max_part_s %.0fs; keeping single part for MVP",
                    ctx.video_id, duration, max_part)

    art.atomic_write_json(outdir / "parts.json", {"parts": parts, "sample_rate": sr, "channels": ch})
    # Mirror key for R2 artifacts
    r2_key = f"artifacts/{ctx.video_id}/audio/part_000.wav"
    ctx.storage.put_file(r2_key, target)
    oh = art.hash_dir_files(outdir, ["parts.json", "audio/part_000.wav"])
    art.write_success(outdir, {"n_parts": 1, "duration_s": duration}, oh)
    m.active_versions[step] = vk
    ctx.state.upsert_video(m)
    ctx.state.mark_done(ctx.video_id, step, vk, str(outdir), oh, {"n_parts": 1, "duration_s": duration})
    log.info("s03 audio %s parts=1 dur=%.1fs", ctx.video_id, duration)
    return {"version_key": vk, "outdir": str(outdir), "parts": parts}
