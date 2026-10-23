"""s02_media: 64 kbps AAC/m4a play copy → LocalStorage (data/r2-mirror) or R2.

Domestic playback: audio on R2 + site /watch/{id}?t= jump. YouTube URL kept as
source backup only. When play_copy is false, YouTube-backed items skip the
transcode (legacy disk-budget mode).
"""
from __future__ import annotations
import pathlib, shutil, subprocess
from tcmkb_core.play import construct_play_url, play_audio_key
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
    source = (m.meta or {}).get("source") or {}
    play_copy = bool(cfg.get("play_copy", True))
    bitrate = str(cfg.get("audio_bitrate", "64k"))

    # Legacy: YouTube-backed + play_copy false → record YouTube URL only (no local play file)
    if source.get("url") and not play_copy:
        vk = ctx.compute_vk(step, {"mode": "youtube-ref"}, upstream_hash=up)
        if ctx.state.find_done(ctx.video_id, step, vk) and not ctx.force:
            log.info("skip %s %s", ctx.video_id, step)
            return {"skipped": True, "version_key": vk}
        ctx.state.ensure_step(ctx.video_id, step, vk)
        ctx.state.claim(ctx.video_id, step, vk, ctx.worker_id)
        outdir = ctx.outdir(step, vk)
        art.atomic_write_json(outdir / "media.json", {"play_url": source["url"],
                                                      "youtube_id": source.get("youtube_id"),
                                                      "mode": "youtube-ref"})
        oh = art.hash_dir_files(outdir, ["media.json"])
        art.write_success(outdir, {"play_url": source["url"]}, oh)
        m.r2_play_key = None
        m.r2_audio_key = None
        m.active_versions[step] = vk
        ctx.state.upsert_video(m)
        ctx.state.mark_done(ctx.video_id, step, vk, str(outdir), oh, {"play_url": source["url"]})
        log.info("s02 media %s play=%s (youtube-ref, no local copy)", ctx.video_id, source["url"])
        return {"version_key": vk, "play_url": source["url"]}

    frag = {"mode": "play-m4a", "bitrate": bitrate}
    vk = ctx.compute_vk(step, frag, upstream_hash=up)
    existing = ctx.state.find_done(ctx.video_id, step, vk)
    if existing and not ctx.force:
        log.info("skip %s %s", ctx.video_id, step)
        return {"skipped": True, "version_key": vk}

    ctx.state.ensure_step(ctx.video_id, step, vk)
    ctx.state.claim(ctx.video_id, step, vk, ctx.worker_id)
    outdir = ctx.outdir(step, vk)
    audio_key = play_audio_key(ctx.video_id)
    play_key = audio_key
    dest_local = outdir / f"{ctx.video_id}.m4a"
    uri = None
    ext = (m.ext or src.suffix.lstrip(".")).lower()

    try:
        if not src.is_file():
            raise FileNotFoundError(str(src))
        # Always produce 64 kbps AAC/m4a for site playback (audio-only is enough for domestic)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-vn", "-c:a", "aac", "-b:a", bitrate, str(dest_local)],
            capture_output=True, check=True, timeout=1800,
        )
        uri = ctx.storage.put_file(audio_key, dest_local)
        # Optional faststart mp4 remux when source is video (kept for future; not required for cites)
        if ext in ("mp4", "mkv", "webm", "mov") and cfg.get("also_mp4"):
            mp4 = outdir / f"{ctx.video_id}.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(src), "-c", "copy", "-movflags", "+faststart", str(mp4)],
                capture_output=True, check=True, timeout=1800,
            )
            ctx.storage.put_file(f"play/{ctx.video_id}.mp4", mp4)
            play_key = f"play/{ctx.video_id}.mp4"
    except Exception as e:
        log.warning("s02 ffmpeg failed, copying source as play fallback: %s", e)
        if src.is_file():
            fallback = outdir / src.name
            shutil.copy2(src, fallback)
            play_key = f"play/{ctx.video_id}.{ext or 'bin'}"
            uri = ctx.storage.put_file(play_key, fallback)
            audio_key = play_key
        else:
            raise RuntimeError(f"s02_media: source missing and ffmpeg failed: {e}") from e

    m.r2_audio_key = audio_key
    m.r2_play_key = play_key
    play_meta = construct_play_url(ctx.video_id, root=ctx.root)
    media = {
        "play_key": play_key,
        "audio_key": audio_key,
        "audio_bitrate": bitrate,
        "uri": uri,
        "play_url": play_meta.get("url"),
        "play_mode": play_meta.get("mode"),
        "youtube_id": source.get("youtube_id"),
        "youtube_url": source.get("url"),
        "mode": "play-m4a",
    }
    art.atomic_write_json(outdir / "media.json", media)
    oh = art.hash_dir_files(outdir, ["media.json"])
    art.write_success(outdir, {"play_key": play_key, "audio_key": audio_key}, oh)
    m.active_versions[step] = vk
    # Keep play keys in meta for API / backfill
    meta = dict(m.meta or {})
    meta["play"] = {"audio_key": audio_key, "play_key": play_key, "play_url": play_meta.get("url"),
                    "play_mode": play_meta.get("mode"), "bitrate": bitrate}
    m.meta = meta
    ctx.state.upsert_video(m)
    ctx.state.mark_done(ctx.video_id, step, vk, str(outdir), oh,
                       {"play_key": play_key, "audio_key": audio_key, "play_url": play_meta.get("url")})
    log.info("s02 media %s audio=%s play_url=%s", ctx.video_id, audio_key, play_meta.get("url"))
    return {"version_key": vk, "play_key": play_key, "audio_key": audio_key, "play_url": play_meta.get("url")}
