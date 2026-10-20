"""s07_flag: agreement vs alt ASR; without alt, pass-through segments (no flags)."""
from __future__ import annotations
import json, pathlib
from tcmkb_ingest import artifacts as art
from tcmkb_ingest.steps.base import Ctx, log

def _char_agreement(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    # Simple ratio of matching chars via set overlap / length (fast MVP)
    import difflib
    return difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio()

def run(ctx: Ctx, **_kw) -> dict:
    step = "s07_flag"
    m = ctx.state.get_video(ctx.video_id)
    if not m:
        raise RuntimeError(f"{ctx.video_id} not registered")
    thr = float(ctx.step_cfg(step).get("agreement_threshold", 0.75))
    up = (m.active_versions or {}).get("s06_clean", "")
    alt_vk = (m.active_versions or {}).get("s05_asr_alt")
    frag = {"agreement_threshold": thr, "has_alt": bool(alt_vk)}
    vk = ctx.compute_vk(step, frag, upstream_hash=up)
    existing = ctx.state.find_done(ctx.video_id, step, vk)
    if existing and not ctx.force:
        return {"skipped": True, "version_key": vk}

    s06 = ctx.active_outdir("s06_clean")
    if not s06:
        raise RuntimeError("s06_clean not done")
    lines = (s06 / "segments.jsonl").read_text(encoding="utf-8").splitlines()
    segs = [json.loads(x) for x in lines if x.strip()]

    ctx.state.ensure_step(ctx.video_id, step, vk)
    ctx.state.claim(ctx.video_id, step, vk, ctx.worker_id)
    outdir = ctx.outdir(step, vk)

    alt_text = ""
    s05 = ctx.active_outdir("s05_asr_alt")
    if s05 and (s05 / "asr_alt.json").exists():
        alt_text = json.loads((s05 / "asr_alt.json").read_text(encoding="utf-8")).get("text") or ""

    flagged = 0
    if alt_text:
        # Align alt text roughly by sliding through segments
        # MVP: compute whole-segment agreement against substring search
        cursor = 0
        for seg in segs:
            t = seg["text"]
            window = alt_text[max(0, cursor - 20): cursor + max(len(t) * 2, 40)]
            # Find best matching window slice
            import difflib
            sm = difflib.SequenceMatcher(a=t, b=window, autojunk=False)
            match = sm.find_longest_match(0, len(t), 0, len(window))
            piece = window[match.b: match.b + match.size] if match.size else ""
            # Also try exact length slice
            piece2 = window[: len(t)]
            agr = max(_char_agreement(t, piece), _char_agreement(t, piece2))
            seg["alt_text"] = piece or None
            seg["agreement"] = round(agr, 3)
            seg["review_flag"] = bool(agr < thr)
            if seg["review_flag"]:
                flagged += 1
            cursor += len(t)
    else:
        for seg in segs:
            seg["alt_text"] = None
            seg["agreement"] = None
            seg["review_flag"] = False

    body = "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in segs)
    art.atomic_write_text(outdir / "segments.jsonl", body)
    art.atomic_write_text(ctx.artifacts_base / ctx.video_id / "segments.jsonl", body)
    metrics = {"n_segments": len(segs), "flagged": flagged, "has_alt": bool(alt_text)}
    oh = art.hash_dir_files(outdir, ["segments.jsonl"])
    art.write_success(outdir, metrics, oh)
    m.active_versions[step] = vk
    ctx.state.upsert_video(m)
    ctx.state.mark_done(ctx.video_id, step, vk, str(outdir), oh, metrics)
    log.info("s07 flag %s flagged=%d", ctx.video_id, flagged)
    return {"version_key": vk, "metrics": metrics}
