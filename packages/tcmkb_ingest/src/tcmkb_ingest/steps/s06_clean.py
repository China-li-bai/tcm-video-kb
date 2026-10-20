"""s06_clean: char-timestamp sentence rebuild → OpenCC t2s → lexicon corrections → segments.jsonl."""
from __future__ import annotations
import json, pathlib
from tcmkb_ingest import artifacts as art
from tcmkb_ingest.clean import rebuild_sentences
from tcmkb_ingest.steps.base import Ctx, log

def _load_corrector(ctx: Ctx):
    corr_path = ctx.root / "lexicon" / "dist" / "corrections.json"
    if not corr_path.exists():
        return None
    data = json.loads(corr_path.read_text(encoding="utf-8"))
    from tcmkb_lexicon.correct import Corrector
    return Corrector(data.get("rules") or [], protected=set(data.get("protected_surfaces") or []))

def _opencc_t2s(text: str) -> str:
    try:
        from opencc import OpenCC
        return OpenCC("t2s").convert(text)
    except Exception:
        return text

def run(ctx: Ctx, **_kw) -> dict:
    step = "s06_clean"
    m = ctx.state.get_video(ctx.video_id)
    if not m:
        raise RuntimeError(f"{ctx.video_id} not registered")
    cfg = ctx.step_cfg(step)
    gap = float(cfg.get("gap_break_s", 1.2))
    max_s = float(cfg.get("max_sentence_s", 40.0))
    frag = {"gap_break_s": gap, "max_sentence_s": max_s}
    up = (m.active_versions or {}).get("s04_asr", "")
    lxh = ctx.lexicon_hash()  # corrections change → rerun
    vk = ctx.compute_vk(step, frag, upstream_hash=up, lexicon_hash=lxh)
    existing = ctx.state.find_done(ctx.video_id, step, vk)
    if existing and not ctx.force:
        log.info("skip %s %s", ctx.video_id, step)
        return {"skipped": True, "version_key": vk}

    s04 = ctx.active_outdir("s04_asr")
    if not s04:
        raise RuntimeError("s04_asr not done")
    asr = json.loads((s04 / "asr_raw.json").read_text(encoding="utf-8"))
    text = asr.get("text") or ""
    tokens = asr.get("tokens") or []

    ctx.state.ensure_step(ctx.video_id, step, vk)
    ctx.state.claim(ctx.video_id, step, vk, ctx.worker_id)
    outdir = ctx.outdir(step, vk)

    raw_sents = rebuild_sentences(text, tokens, gap_break_s=gap, max_sentence_s=max_s)
    corrector = _load_corrector(ctx)
    segments = []
    n_edits = 0
    for i, s in enumerate(raw_sents):
        text_raw = s["text"]
        text_s = _opencc_t2s(text_raw)
        edits = []
        if corrector is not None:
            text_s, edits = corrector.correct(text_s)
        n_edits += len(edits)
        segments.append({
            "video_id": ctx.video_id,
            "seq": i,
            "start_s": round(float(s["start_s"]), 3),
            "end_s": round(float(s["end_s"]), 3),
            "text": text_s,
            "text_raw": text_raw,
            "edits": edits,
            "alt_text": None,
            "agreement": None,
            "review_flag": False,
        })

    seg_path = outdir / "segments.jsonl"
    body = "".join(json.dumps(seg, ensure_ascii=False) + "\n" for seg in segments)
    art.atomic_write_text(seg_path, body)
    # Demo convenience pointer
    art.atomic_write_text(ctx.artifacts_base / ctx.video_id / "segments.jsonl", body)

    metrics = {"n_segments": len(segments), "n_edits": n_edits,
               "duration_s": segments[-1]["end_s"] if segments else 0.0}
    oh = art.hash_dir_files(outdir, ["segments.jsonl"])
    art.write_success(outdir, metrics, oh)
    m.active_versions[step] = vk
    ctx.state.upsert_video(m)
    ctx.state.mark_done(ctx.video_id, step, vk, str(outdir), oh, metrics)
    log.info("s06 clean %s segs=%d edits=%d", ctx.video_id, len(segments), n_edits)
    return {"version_key": vk, "outdir": str(outdir), "metrics": metrics}
