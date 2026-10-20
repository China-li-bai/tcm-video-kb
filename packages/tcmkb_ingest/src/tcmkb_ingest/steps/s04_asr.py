"""s04_asr: FunASR SeACo-Paraformer (+ VAD + ct-punc) with hotwords.

Supports --from-cache to ingest existing asr-bench JSON without loading FunASR
(for local demo when FunASR install is slow / not in the workspace venv).
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

def _run_funasr(ctx: Ctx, wav: pathlib.Path, hotword_file: pathlib.Path) -> dict[str, Any]:
    """Real FunASR SeACo path (production). Raises if funasr not installed."""
    try:
        from funasr import AutoModel
    except ImportError as e:
        raise RuntimeError(
            "funasr not installed in this environment. Use --from-cache for demo, "
            "or: uv pip install 'tcmkb-ingest[asr]' (or reuse /workspace/asr-bench/venv)."
        ) from e

    model_id = ctx.asr.get("model") or (
        "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    )
    vad = ctx.asr.get("vad_model", "fsmn-vad")
    punc = ctx.asr.get("punc_model", "ct-punc")
    batch_s = int(ctx.asr.get("batch_size_s", 300))
    t0 = time.time()
    m = AutoModel(model=model_id, vad_model=vad, punc_model=punc, disable_update=True)
    hotword = hotword_file.read_text(encoding="utf-8").replace("\n", " ").strip()
    # Prefer char timestamps; sentence_timestamp kept for fallback only
    kw: dict[str, Any] = {"batch_size_s": batch_s, "hotword": hotword}
    # FunASR versions differ: try output with timestamp
    r = m.generate(input=str(wav), **kw)
    dt = time.time() - t0
    r0 = r[0] if isinstance(r, list) else r
    text = r0.get("text") or ""
    tokens: list[dict[str, Any]] = []
    if "timestamp" in r0 and r0["timestamp"]:
        tokens = tokens_from_timestamp_pairs(text, r0["timestamp"])
    elif "sentence_info" in r0 and r0["sentence_info"]:
        sents = [{"start_ms": x["start"], "end_ms": x["end"], "text": x["text"]} for x in r0["sentence_info"]]
        _, tokens = synthesize_tokens_from_sentences(sents)
    return {
        "text": text,
        "tokens": tokens,
        "proc_sec": dt,
        "model_rev": getattr(m, "model_path", model_id),
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
    }
    up = (m.active_versions or {}).get("s03_audio", "")
    vk = ctx.compute_vk(step, frag, upstream_hash=up)
    existing = ctx.state.find_done(ctx.video_id, step, vk)
    if existing and not ctx.force:
        log.info("skip %s %s", ctx.video_id, step)
        return {"skipped": True, "version_key": vk}

    ctx.state.ensure_step(ctx.video_id, step, vk)
    ctx.state.claim(ctx.video_id, step, vk, "local")
    outdir = ctx.outdir(step, vk)

    lex_ver = _lexicon_ver(ctx)
    hotword_set = f"{series_id}@{lex_ver}" if lex_ver else series_id

    if ctx.from_cache:
        cache = _load_cache(ctx, series_id)
        asr_raw = _normalize_cache_to_asr_raw(ctx, cache, series_id, hotword_set)
    else:
        # Locate wav from s03
        s03 = ctx.active_outdir("s03_audio")
        if not s03:
            raise RuntimeError("s03_audio not done")
        parts = json.loads((s03 / "parts.json").read_text(encoding="utf-8"))
        all_text = []
        all_tokens: list[dict[str, Any]] = []
        t0 = time.time()
        model_rev = ""
        for pinfo in parts["parts"]:
            wav = s03 / pinfo["path"]
            offset = float(pinfo.get("offset_s", 0))
            res = _run_funasr(ctx, wav, hot_path)
            model_rev = str(res.get("model_rev") or "")
            all_text.append(res["text"])
            for tok in res["tokens"]:
                all_tokens.append({
                    "t": tok["t"],
                    "s": round(float(tok["s"]) + offset, 3),
                    "e": round(float(tok["e"]) + offset, 3),
                })
        asr_raw = {
            "video_id": ctx.video_id,
            "engine": "seaco-paraformer",
            "model": ctx.asr.get("model", ""),
            "model_rev": model_rev,
            "hotword_set": hotword_set,
            "from_cache": False,
            "parts": [{"part": p["part"], "offset_s": p["offset_s"]} for p in parts["parts"]],
            "text": "".join(all_text),
            "tokens": all_tokens,
            "metrics": {
                "proc_sec": time.time() - t0,
                "n_tokens": len(all_tokens),
                "n_chars": len(strip_punct("".join(all_text))),
            },
        }

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
