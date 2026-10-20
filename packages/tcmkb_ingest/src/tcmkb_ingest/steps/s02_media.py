"""s02_media: playback copies. For local wav demo, copy/link as play audio; skip heavy transcode."""
from __future__ import annotations
import pathlib, shutil, subprocess
from tcmkb_ingest import artifacts as art
from tcmkb_ingest.steps.base import Ctx, log

def run(ctx: Ctx, **_kw) -> dict:
    step = "s02_media"
    cfg = ctx.step_cfg(step)
    if cfg.get("enabled") is False:
        vk = ctx.compute_vk(step, {"enabled": False})
        ctx.state.ensure_step(ctx.video_id, step, vk)
        ctx.state.mark_skipped(ctx.video_id, step, vk, "disabled")
        return {"skipped": True, "version_key": vk}

    m = ctx.state.get_video(ctx.video_id)
    if not m:
        raise RuntimeError(f"{ctx.video_id} not registered")
    src = pathlib.Path(m.source_path)
    up = (m.active_versions or {}).get("s01_upload", "")
    vk = ctx.compute_vk(step, {"mode": "local-lite"}, upstream_hash=up)
    existing = ctx.state.find_done(ctx.video_id, step, vk)
    if existing and not ctx.force:
        log.info("skip %s %s", ctx.video_id, step)
        return {"skipped": True, "version_key": vk}

    ctx.state.ensure_step(ctx.video_id, step, vk)
    ctx.state.claim(ctx.video_id, step, vk, ctx.worker_id)
    outdir = ctx.outdir(step, vk)
    play_key = f"play/{ctx.video_id}.m4a"
    audio_key = play_key

    # If source is already wav/m4a/mp3, store as play audio; optionally remux to m4a
    ext = (m.ext or src.suffix.lstrip(".")).lower()
    if ext in ("wav", "flac", "mp3", "m4a", "aac"):
        # Prefer remux/copy to m4a when ffmpeg available; else copy original
        dest_local = outdir / f"{ctx.video_id}.m4a"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(src), "-vn", "-c:a", "aac", "-b:a", "64k", str(dest_local)],
                capture_output=True, check=True, timeout=600,
            )
        except Exception:
            dest_local = outdir / src.name
            shutil.copy2(src, dest_local)
        uri = ctx.storage.put_file(play_key, dest_local)
    else:
        # Video: remux faststart mp4 (no re-encode) + extract m4a
        mp4 = outdir / f"{ctx.video_id}.mp4"
        m4a = outdir / f"{ctx.video_id}.m4a"
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(src), "-c", "copy", "-movflags", "+faststart", str(mp4)],
                capture_output=True, check=True, timeout=1800,
            )
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(src), "-vn", "-c:a", "aac", "-b:a", "64k", str(m4a)],
                capture_output=True, check=True, timeout=1800,
            )
            ctx.storage.put_file(f"play/{ctx.video_id}.mp4", mp4)
            uri = ctx.storage.put_file(play_key, m4a)
            m.r2_play_key = f"play/{ctx.video_id}.mp4"
        except Exception as e:
            log.warning("s02 ffmpeg failed, copying source: %s", e)
            shutil.copy2(src, outdir / src.name)
            uri = ctx.storage.put_file(f"play/{ctx.video_id}.{ext}", src)
            play_key = f"play/{ctx.video_id}.{ext}"

    m.r2_audio_key = audio_key
    if not m.r2_play_key:
        m.r2_play_key = play_key
    art.atomic_write_json(outdir / "media.json", {"play_key": m.r2_play_key, "audio_key": audio_key, "uri": uri})
    oh = art.hash_dir_files(outdir, ["media.json"])
    art.write_success(outdir, {"play_key": m.r2_play_key}, oh)
    m.active_versions[step] = vk
    ctx.state.upsert_video(m)
    ctx.state.mark_done(ctx.video_id, step, vk, str(outdir), oh, {"play_key": m.r2_play_key})
    log.info("s02 media %s play=%s", ctx.video_id, m.r2_play_key)
    return {"version_key": vk, "play_key": m.r2_play_key}
