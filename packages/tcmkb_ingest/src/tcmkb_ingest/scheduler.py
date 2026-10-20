"""Run pipeline steps for a video with resume (version_key skip)."""
from __future__ import annotations
from typing import Any
from tcmkb_ingest.steps import steps_up_to, get_runner, normalize_step, STEP_ORDER
from tcmkb_ingest.steps.base import Ctx, log

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
) -> dict[str, Any]:
    to_step = normalize_step(to_step)
    ctx = Ctx.build(
        video_id, force=force, from_cache=from_cache, skip_alt=skip_alt, cache_dir=cache_dir,
    )
    plan = steps_up_to(to_step)
    if from_step:
        from_step = normalize_step(from_step)
        if from_step not in STEP_ORDER:
            raise ValueError(from_step)
        plan = [s for s in plan if STEP_ORDER.index(s) >= STEP_ORDER.index(from_step)]

    results: dict[str, Any] = {}
    for step in plan:
        runner = get_runner(step)
        kw: dict[str, Any] = {}
        if step == "s00_register":
            kw.update(source_path=source_path, series_id=series_id, episode=episode, title=title)
        log.info("=== %s / %s ===", video_id, step)
        try:
            results[step] = runner(ctx, **kw)
        except Exception as e:
            log.exception("step %s failed: %s", step, e)
            # ensure failed is recorded if a version was claimed — runner usually does it
            raise
    return {"video_id": video_id, "steps": results}
