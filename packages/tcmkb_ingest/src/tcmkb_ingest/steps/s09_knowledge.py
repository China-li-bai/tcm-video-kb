"""s09_knowledge: knowledge layer (chapters / entities / knowledge points) over the transcript.

Two phases, both file-based under data/knowledge/<video_id>/:
  * no annotations yet  -> write reading windows (_work/windows/wNN.txt) and stop (status
    "needs_annotation"); the step is NOT marked done so a later run picks it up.
  * annotations present -> validate + resolve them into chapters.json, entities.jsonl,
    knowledge_points.jsonl, outline.md and mark the step done.
The version key covers the annotations, the upstream transcript version and knowledge.yaml,
so editing an annotation re-runs the build. Not part of the default `--to s08` plan.
"""
from __future__ import annotations
import hashlib
from tcmkb_ingest.steps.base import Ctx, log
from tcmkb_ingest import artifacts as art


def run(ctx: Ctx, **_kw) -> dict:
    from tcmkb_ingest.knowledge.build import build, knowledge_dir, load_config
    from tcmkb_ingest.knowledge.prep import prepare

    step = "s09_knowledge"
    m = ctx.state.get_video(ctx.video_id)
    if not m:
        raise RuntimeError(f"{ctx.video_id} not registered")
    kdir = knowledge_dir(ctx.root, ctx.video_id)
    cfg = load_config(ctx.root)
    anns = sorted((kdir / "annotations").glob("*.yaml")) if (kdir / "annotations").is_dir() else []
    if not anns:
        rep = prepare(ctx.root, ctx.video_id, float(cfg.get("window_s", 720)))
        log.info("s09 %s: no annotations; prepared %d windows in %s", ctx.video_id,
                 len(rep.get("windows", [])), kdir / "_work")
        return {"status": "needs_annotation", "windows": len(rep.get("windows", []))}

    h = hashlib.sha256()
    for p in anns:
        h.update(p.name.encode() + b"\0" + p.read_bytes())
    av = m.active_versions or {}
    up = av.get("s07_flag") or av.get("s06_clean", "")
    frag = {"annotations": h.hexdigest()[:16], "config": cfg}
    vk = ctx.compute_vk(step, frag, upstream_hash=up)
    if ctx.state.find_done(ctx.video_id, step, vk) and not ctx.force:
        log.info("skip %s %s", ctx.video_id, step)
        return {"skipped": True, "version_key": vk}
    ctx.state.ensure_step(ctx.video_id, step, vk)
    ctx.state.claim(ctx.video_id, step, vk, ctx.worker_id)
    report = build(ctx.root, ctx.video_id, strict=True)
    names = ["chapters.json", "entities.jsonl", "knowledge_points.jsonl", "outline.md"]
    oh = art.hash_dir_files(kdir, names)
    metrics = {k: report[k] for k in ("n_chapters", "n_sections", "n_entities", "n_knowledge_points")}
    m.active_versions[step] = vk
    ctx.state.upsert_video(m)
    ctx.state.mark_done(ctx.video_id, step, vk, str(kdir), oh, metrics)
    log.info("s09 knowledge %s %s", ctx.video_id, metrics)
    return {"version_key": vk, "outdir": str(kdir), "metrics": metrics}
