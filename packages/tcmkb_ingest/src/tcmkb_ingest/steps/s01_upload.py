"""s01_upload: copy source into LocalStorage (R2 mirror) under source/{video_id}.{ext}."""
from __future__ import annotations
import pathlib, shutil
from tcmkb_ingest import artifacts as art
from tcmkb_ingest.steps.base import Ctx, log

def run(ctx: Ctx, **_kw) -> dict:
    step = "s01_upload"
    m = ctx.state.get_video(ctx.video_id)
    if not m:
        raise RuntimeError(f"{ctx.video_id} not registered")
    src = pathlib.Path(m.source_path)
    key = f"source/{ctx.video_id}.{m.ext or src.suffix.lstrip('.')}"
    cfg = {"key": key}
    up = (m.active_versions or {}).get("s00_register", "")
    vk = ctx.compute_vk(step, cfg, upstream_hash=up or m.source_sha256[:16])
    existing = ctx.state.find_done(ctx.video_id, step, vk)
    if existing and not ctx.force:
        log.info("skip %s %s", ctx.video_id, step)
        return {"skipped": True, "version_key": vk}

    ctx.state.ensure_step(ctx.video_id, step, vk)
    ctx.state.claim(ctx.video_id, step, vk, ctx.worker_id)
    uri = ctx.storage.put_file(key, src)
    outdir = ctx.outdir(step, vk)
    art.atomic_write_json(outdir / "upload.json", {"key": key, "uri": uri, "bytes": m.source_bytes})
    # Also keep a pointer copy under artifacts for convenience
    dest = outdir / f"source.{m.ext or 'bin'}"
    if not dest.exists():
        try:
            dest.symlink_to(ctx.storage._path(key))
        except OSError:
            shutil.copy2(src, dest)
    oh = art.hash_dir_files(outdir, ["upload.json"])
    art.write_success(outdir, {"key": key}, oh)
    m.r2_source_key = key
    m.active_versions[step] = vk
    ctx.state.upsert_video(m)
    ctx.state.mark_done(ctx.video_id, step, vk, str(outdir), oh, {"key": key})
    log.info("s01 uploaded %s -> %s", ctx.video_id, key)
    return {"version_key": vk, "key": key, "uri": uri}
