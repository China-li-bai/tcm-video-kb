"""s05_asr_alt: optional SenseVoiceSmall second pass. Default skipped (--skip-alt)."""
from __future__ import annotations
import json
from tcmkb_ingest import artifacts as art
from tcmkb_ingest.steps.base import Ctx, log

def run(ctx: Ctx, **_kw) -> dict:
    step = "s05_asr_alt"
    cfg = ctx.step_cfg(step)
    enabled = bool(cfg.get("enabled", False)) and not ctx.skip_alt
    m = ctx.state.get_video(ctx.video_id)
    up = (m.active_versions or {}).get("s03_audio", "") if m else ""
    frag = {"enabled": enabled, "engine": (ctx.asr.get("alt") or {}).get("engine", "sensevoice")}
    vk = ctx.compute_vk(step, frag, upstream_hash=up)
    existing = ctx.state.find_done(ctx.video_id, step, vk)
    if existing and not ctx.force:
        return {"skipped": True, "version_key": vk}

    ctx.state.ensure_step(ctx.video_id, step, vk)
    if not enabled:
        ctx.state.mark_skipped(ctx.video_id, step, vk, "skip-alt default / disabled")
        log.info("s05 skipped (alt disabled)")
        return {"skipped": True, "version_key": vk, "reason": "disabled"}

    # Production path would run SenseVoice; for now mark failed if forced on without cache
    ctx.state.claim(ctx.video_id, step, vk, ctx.worker_id)
    outdir = ctx.outdir(step, vk)
    # Try sensevoice cache
    if ctx.from_cache and ctx.cache_dir and m:
        p = ctx.cache_dir / f"{m.series_id}.sensevoice.json"
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            alt = {
                "video_id": ctx.video_id,
                "engine": "sensevoice",
                "text": data.get("text", ""),
                "from_cache": True,
            }
            art.atomic_write_json(outdir / "asr_alt.json", alt)
            oh = art.hash_dir_files(outdir, ["asr_alt.json"])
            art.write_success(outdir, {"chars": len(alt["text"])}, oh)
            m.active_versions[step] = vk
            ctx.state.upsert_video(m)
            ctx.state.mark_done(ctx.video_id, step, vk, str(outdir), oh, {"chars": len(alt["text"])})
            return {"version_key": vk, "outdir": str(outdir)}

    ctx.state.mark_failed(ctx.video_id, step, vk, "SenseVoice live path not configured; use --from-cache")
    raise RuntimeError("s05 SenseVoice live path not configured")
