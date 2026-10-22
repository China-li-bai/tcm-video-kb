"""Run pipeline steps for a video with resume (version_key skip)."""
from __future__ import annotations
import pathlib
from typing import Any
from tcmkb_ingest.steps import steps_up_to, get_runner, normalize_step, STEP_ORDER
from tcmkb_ingest.steps.base import Ctx, log

# Steps that need the local media; skipped for purged videos.
MEDIA_STEPS = ("s00_register", "s01_upload", "s02_media", "s03_audio", "s04_asr", "s05_asr_alt")

def run_pipeline(
    video_id: str,
    *,
    to_step: str = "s08",
    from_step: str | None = None,
    force: bool = False,
    from_cache: bool = False,
    skip_alt: bool = True,
    cache_dir: str | None = None,
    source_path: str | None = None,
    series_id: str | None = None,
    episode: int = 0,
    title: str = "",
    source_meta: dict[str, Any] | None = None,
    root: pathlib.Path | None = None,
    engine: Any = None,
) -> dict[str, Any]:
    """Run steps up to `to_step`. Steps whose version_key is already done are skipped.

    On a step exception the step_run row is marked `failed` (error text kept) and
    the exception is re-raised; `batch` catches it and moves to the next video.
    """
    to_step = normalize_step(to_step)
    ctx = Ctx.build(
        video_id, force=force, from_cache=from_cache, skip_alt=skip_alt, cache_dir=cache_dir,
        root=root, engine=engine,
    )
    plan = steps_up_to(to_step)
    if from_step:
        from_step = normalize_step(from_step)
        if from_step not in STEP_ORDER:
            raise ValueError(from_step)
        plan = [s for s in plan if STEP_ORDER.index(s) >= STEP_ORDER.index(from_step)]

    results: dict[str, Any] = {}
    # Media purged after verified outputs: never re-run / re-require the audio steps.
    # s06+ still run from the kept asr_raw.json (e.g. a lexicon change).
    purged = ctx.state.is_purged(video_id)
    try:
        for step in plan:
            if purged and step in MEDIA_STEPS:
                m = ctx.state.get_video(video_id)
                results[step] = {"skipped": True, "purged": True,
                                 "version_key": (m.active_versions or {}).get(step) if m else None}
                continue
            runner = get_runner(step)
            kw: dict[str, Any] = {}
            if step == "s00_register":
                kw.update(source_path=source_path, series_id=series_id, episode=episode, title=title,
                          source_meta=source_meta)
            log.info("=== %s / %s ===", video_id, step)
            try:
                results[step] = runner(ctx, **kw)
            except Exception as e:
                log.exception("step %s failed: %s", step, e)
                try:
                    ctx.state.fail_running(video_id, step, f"{type(e).__name__}: {e}")
                except Exception:  # pragma: no cover - state db broken
                    pass
                raise
    finally:
        ctx.state.close()
    return {"video_id": video_id, "steps": results}
