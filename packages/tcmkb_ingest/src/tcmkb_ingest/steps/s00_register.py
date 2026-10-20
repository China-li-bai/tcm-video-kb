"""s00_register: sha256, ffprobe duration, write meta.json, upsert video row."""
from __future__ import annotations
import json, pathlib, subprocess
from tcmkb_core.models import VideoManifest
from tcmkb_core.ids import sha256_file, content_hash
from tcmkb_ingest import artifacts as art
from tcmkb_ingest.steps.base import Ctx, log

def _ffprobe_duration(path: pathlib.Path) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True, timeout=60,
        )
        return float(r.stdout.strip() or 0)
    except Exception as e:
        log.warning("ffprobe failed for %s: %s", path, e)
        return 0.0

def run(ctx: Ctx, *, source_path: str | None = None, series_id: str | None = None,
        episode: int = 0, title: str = "", **_kw) -> dict:
    step = "s00_register"
    m = ctx.state.get_video(ctx.video_id)
    if m is None:
        if not source_path:
            raise FileNotFoundError(f"{ctx.video_id} not registered; pass --file")
        src = pathlib.Path(source_path).resolve()
    else:
        src = pathlib.Path(source_path).resolve() if source_path else pathlib.Path(m.source_path)

    if not src.is_file():
        raise FileNotFoundError(src)

    digest = sha256_file(src)
    size = src.stat().st_size
    dur = _ffprobe_duration(src)
    series_id = series_id or (m.series_id if m else ctx.video_id.split("-")[0])
    episode = episode if episode else (m.episode if m else 0)
    title = title or (m.title if m else src.stem)
    ext = src.suffix.lstrip(".")

    cfg = {"ext": ext}
    vk = ctx.compute_vk(step, cfg, upstream_hash=digest[:16])
    existing = ctx.state.find_done(ctx.video_id, step, vk)
    if existing and not ctx.force:
        log.info("skip %s %s (done)", ctx.video_id, step)
        return {"skipped": True, "version_key": vk, "outdir": existing.output_uri}

    ctx.state.ensure_step(ctx.video_id, step, vk)
    if not ctx.state.claim(ctx.video_id, step, vk, worker_id="local"):
        # already running; still allow force overwrite of done
        pass

    outdir = ctx.outdir(step, vk)
    meta = {
        "video_id": ctx.video_id,
        "series_id": series_id,
        "episode": episode,
        "title": title,
        "source_path": str(src),
        "source_sha256": digest,
        "source_bytes": size,
        "duration_s": dur,
        "ext": ext,
    }
    art.atomic_write_json(outdir / "meta.json", meta)
    oh = art.hash_dir_files(outdir, ["meta.json"])
    art.write_success(outdir, {"duration_s": dur, "bytes": size}, oh)

    manifest = VideoManifest(
        video_id=ctx.video_id, series_id=series_id, episode=episode, title=title,
        source_path=str(src), source_sha256=digest, source_bytes=size,
        duration_s=dur, ext=ext, active_versions={step: vk},
    )
    if m and m.active_versions:
        av = dict(m.active_versions)
        av[step] = vk
        manifest.active_versions = av
        manifest.r2_source_key = m.r2_source_key
        manifest.r2_play_key = m.r2_play_key
        manifest.r2_audio_key = m.r2_audio_key
    ctx.state.upsert_video(manifest)
    ctx.state.mark_done(ctx.video_id, step, vk, str(outdir), oh, {"duration_s": dur, "bytes": size})
    log.info("s00 registered %s sha=%s… dur=%.1fs", ctx.video_id, digest[:12], dur)
    return {"version_key": vk, "outdir": str(outdir), "meta": meta}
