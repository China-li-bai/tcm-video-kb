"""s04_asr: FunASR SeACo-Paraformer (+ VAD + ct-punc) with hotwords.

Live path: `asr_engine.FunAsrEngine` (one model per process, shared by `batch`),
per-part checkpoints, real SeACo char/token timestamps (+ part offset).
--from-cache ingests existing asr-bench JSON without loading FunASR (demo).
"""
from __future__ import annotations
import json, pathlib, time
from typing import Any
from tcmkb_ingest import artifacts as art
from tcmkb_ingest.clean import (
    synthesize_tokens_from_sentences, tokens_from_timestamp_pairs, strip_punct,
)
from tcmkb_ingest.steps.base import Ctx, log

def _hotword_path(ctx: Ctx, series_id: str) -> pathlib.Path:
    d = ctx.root / "lexicon" / "dist" / "hotwords"
    p = d / f"{series_id}.txt"
    if p.exists():
        return p
    return d / "global.txt"

def _lexicon_ver(ctx: Ctx) -> str:
    bi = ctx.root / "lexicon" / "dist" / "build_info.json"
    if bi.exists():
        return json.loads(bi.read_text(encoding="utf-8")).get("lexicon_ver", "")
    return ""

def _load_cache(ctx: Ctx, series_id: str) -> dict[str, Any]:
    """Prefer paraformer_hot, then paraformer, for the series slug."""
    assert ctx.cache_dir is not None
    cd = ctx.cache_dir
    # Map demo video ids like zj-demo -> zj
    slug = series_id
    for stem in (f"{slug}.paraformer_hot", f"{slug}.paraformer", f"{ctx.video_id}.paraformer_hot"):
        p = cd / f"{stem}.json"
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            data["_cache_path"] = str(p)
            # Prefer companion rawts for char timestamps if present
            rawts = cd / f"{stem}.rawts.json"
            if not rawts.exists():
                rawts = cd / f"{slug}.paraformer.rawts.json"
            if rawts.exists():
                data["_rawts"] = json.loads(rawts.read_text(encoding="utf-8"))
                data["_rawts_path"] = str(rawts)
            return data
    raise FileNotFoundError(f"no ASR cache for series={series_id} under {cd}")

def _normalize_cache_to_asr_raw(ctx: Ctx, cache: dict[str, Any], series_id: str,
                                 hotword_set: str) -> dict[str, Any]:
    text = cache.get("text") or ""
    tokens: list[dict[str, Any]] = []
    rawts = cache.get("_rawts")
    if rawts and isinstance(rawts.get("timestamp"), list):
        tokens = tokens_from_timestamp_pairs(rawts.get("text") or text, rawts["timestamp"])
        if rawts.get("text"):
            text = rawts["text"]
    elif cache.get("timestamp"):
        tokens = tokens_from_timestamp_pairs(text, cache["timestamp"])
    elif cache.get("tokens"):
        tokens = cache["tokens"]
    elif cache.get("sentences"):
        # Synthesize char timing from sentence_info
        text2, tokens = synthesize_tokens_from_sentences(cache["sentences"])
        if not text:
            text = text2
    else:
        # Last resort: no timing
        tokens = [{"t": c, "s": i * 0.08, "e": (i + 1) * 0.08} for i, c in enumerate(strip_punct(text))]

    return {
        "video_id": ctx.video_id,
        "engine": "seaco-paraformer",
        "model": ctx.asr.get("model", ""),
        "model_rev": "cache",
        "hotword_set": hotword_set,
        "from_cache": True,
        "cache_path": cache.get("_cache_path"),
        "parts": [{"part": 0, "offset_s": 0.0}],
        "text": text,
        "tokens": tokens,
        "metrics": {
            "proc_sec": cache.get("proc_sec"),
            "audio_sec": cache.get("audio_sec"),
            "rtf": cache.get("rtf"),
            "n_tokens": len(tokens),
            "n_chars": len(strip_punct(text)),
        },
    }

def _run_live(ctx: Ctx, hot_path: pathlib.Path, hotword_set: str,
              outdir: pathlib.Path) -> dict[str, Any]:
    """Real FunASR path. One engine per process (ctx.engine or the module cache).

    Each s03 part is transcribed separately and checkpointed to
    parts/part_NNN.json, so a crash mid-video resumes at the next part.
    """
    from tcmkb_ingest.asr_engine import get_engine, read_hotwords
    s03 = ctx.active_outdir("s03_audio")
    if not s03:
        raise RuntimeError("s03_audio not done")
    parts = json.loads((s03 / "parts.json").read_text(encoding="utf-8"))["parts"]
    engine = ctx.engine or get_engine(ctx.asr)
    hotwords = read_hotwords(hot_path, ctx.asr.get("hotword_max"))
    was_loaded = getattr(engine, "_m", None) is not None
    pdir = outdir / "parts"
    pdir.mkdir(parents=True, exist_ok=True)
    all_text: list[str] = []
    all_tokens: list[dict[str, Any]] = []
    proc_sec = 0.0
    audio_sec = 0.0
    reused = 0
    for pinfo in parts:
        idx = int(pinfo["part"])
        offset = float(pinfo.get("offset_s", 0))
        dur = float(pinfo.get("duration_s") or 0)
        ck = pdir / f"part_{idx:03d}.json"
        if ck.exists() and not ctx.force:
            res = json.loads(ck.read_text(encoding="utf-8"))
            reused += 1
        else:
            wav = s03 / pinfo["path"]
            r = engine.transcribe(wav, hotwords)
            res = {"part": idx, "offset_s": offset, "duration_s": dur,
                   "proc_sec": float(r.get("proc_sec") or 0), "text": r.get("text") or "",
                   "tokens": [{"t": t["t"], "s": round(float(t["s"]) + offset, 3),
                               "e": round(float(t["e"]) + offset, 3)} for t in r.get("tokens") or []]}
            art.atomic_write_json(ck, res)
            log.info("s04 %s part %d/%d dur=%.0fs proc=%.1fs rtf=%.4f tokens=%d",
                     ctx.video_id, idx + 1, len(parts), dur, res["proc_sec"],
                     res["proc_sec"] / dur if dur else 0, len(res["tokens"]))
        proc_sec += float(res.get("proc_sec") or 0)
        audio_sec += dur
        all_text.append(res["text"])
        all_tokens.extend(res["tokens"])
    text = "".join(all_text)
    metrics = {
        "audio_sec": round(audio_sec, 3),
        "proc_sec": round(proc_sec, 3),
        "rtf": round(proc_sec / audio_sec, 5) if audio_sec else None,
        "n_parts": len(parts),
        "parts_reused": reused,
        "n_tokens": len(all_tokens),
        "n_chars": len(strip_punct(text)),
        "n_hotwords": len(hotwords),
        "hotword_sha": art.hash_file(hot_path)[:12] if hot_path.exists() else "",
        "model_load_sec": (None if was_loaded else round(float(getattr(engine, "load_sec", 0) or 0), 2)),
    }
    return {
        "video_id": ctx.video_id,
        "engine": getattr(engine, "name", "seaco-paraformer"),
        "model": ctx.asr.get("model", ""),
        "vad_model": ctx.asr.get("vad_model", ""),
        "punc_model": ctx.asr.get("punc_model", ""),
        "model_rev": getattr(engine, "model_rev", ""),
        "hotword_set": hotword_set,
        "hotword_file": str(hot_path),
        "hotwords": hotwords,
        "from_cache": False,
        "timestamp_source": "seaco_char_timestamp",
        "parts": [{"part": p["part"], "offset_s": p["offset_s"], "duration_s": p.get("duration_s")}
                  for p in parts],
        "text": text,
        "tokens": all_tokens,
        "metrics": metrics,
    }

def run(ctx: Ctx, **_kw) -> dict:
    step = "s04_asr"
    m = ctx.state.get_video(ctx.video_id)
    if not m:
        raise RuntimeError(f"{ctx.video_id} not registered")
    series_id = m.series_id
    hot_path = _hotword_path(ctx, series_id)
    hot_hash = art.hash_file(hot_path) if hot_path.exists() else ""
    # Pin hotword set: lexicon rebuild does NOT change version_key (ARCHITECTURE §5.1)
    pin = bool(ctx.step_cfg(step).get("hotword_set_pin", True))
    frag = {
        "engine": ctx.asr.get("engine", "seaco-paraformer"),
        "model": ctx.asr.get("model", ""),
        "hotword_set_pin": pin,
        # Only include hotword content hash when NOT pinned (explicit force path)
        **({} if pin else {"hotword_hash": hot_hash}),
        "from_cache": bool(ctx.from_cache),
        **({} if ctx.from_cache else {
            "vad_model": ctx.asr.get("vad_model", ""),
            "punc_model": ctx.asr.get("punc_model", ""),
            "batch_size_s": ctx.asr.get("batch_size_s"),
            "hotword_max": ctx.asr.get("hotword_max"),
        }),
    }
    up = (m.active_versions or {}).get("s03_audio", "")
    vk = ctx.compute_vk(step, frag, upstream_hash=up)
    existing = ctx.state.find_done(ctx.video_id, step, vk)
    if existing and not ctx.force:
        log.info("skip %s %s", ctx.video_id, step)
        return {"skipped": True, "version_key": vk}

    ctx.state.ensure_step(ctx.video_id, step, vk)
    ctx.state.claim(ctx.video_id, step, vk, ctx.worker_id)
    outdir = ctx.outdir(step, vk)

    lex_ver = _lexicon_ver(ctx)
    hotword_set = f"{series_id}@{lex_ver}" if lex_ver else series_id

    if ctx.from_cache:
        cache = _load_cache(ctx, series_id)
        asr_raw = _normalize_cache_to_asr_raw(ctx, cache, series_id, hotword_set)
    else:
        asr_raw = _run_live(ctx, hot_path, hotword_set, outdir)

    # Also write a stable convenience copy at artifacts/{vid}/asr_raw.json via symlink note in success
    art.atomic_write_json(outdir / "asr_raw.json", asr_raw)
    # Mirror at video-level pointer for demo convenience
    demo_ptr = ctx.artifacts_base / ctx.video_id / "asr_raw.json"
    art.atomic_write_json(demo_ptr, asr_raw)

    metrics = dict(asr_raw.get("metrics") or {})
    oh = art.hash_dir_files(outdir, ["asr_raw.json"])
    art.write_success(outdir, metrics, oh)
    m.active_versions[step] = vk
    ctx.state.upsert_video(m)
    ctx.state.mark_done(ctx.video_id, step, vk, str(outdir), oh, metrics)
    log.info("s04 asr %s tokens=%s from_cache=%s", ctx.video_id, metrics.get("n_tokens"), ctx.from_cache)
    return {"version_key": vk, "outdir": str(outdir), "metrics": metrics}
