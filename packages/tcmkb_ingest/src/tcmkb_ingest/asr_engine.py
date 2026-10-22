"""ASR engine wrapper for s04 (FunASR SeACo-Paraformer + fsmn-vad + ct-punc).

Design (see docs/runbooks/batch_asr.md):
- One model load per process: `get_engine(cfg)` caches by config, so `batch`
  shares a single AutoModel across all videos (and parts).
- Long audio: s03 splits audio into <= max_part_s (20 min) parts at silences;
  inside a part FunASR's fsmn-vad cuts speech into <= max_single_segment_time
  (60 s) segments and, on CPU, decodes them one at a time (batch_size=0), so
  peak memory is bounded by part length, not by video length.
- Model weights are loaded with torch.load(mmap=True) to cut the load-time
  memory spike (measured ~5.5 GB -> ~3.8 GB anon RSS peak on this box).
- Timestamps: SeACo returns `timestamp` ([[start_ms, end_ms], ...]) aligned 1:1
  with the space-separated tokens of `raw_text` (`return_raw_text=True`). We
  zip those (exact), falling back to char mapping of the punctuated text.
- Hotwords: passed as a space-joined string (one term per line in the series
  file; never weights). FunASR 1.4.16 does NOT forward nfilter/seaco_weight
  from generate() kwargs (ASF k is hard-coded to 50), so those config keys are
  recorded but not applied.
"""
from __future__ import annotations
import contextlib, json, logging, os, pathlib, time
from typing import Any, Protocol

from tcmkb_ingest.clean import tokens_from_timestamp_pairs

log = logging.getLogger("tcmkb.ingest.asr")

DEFAULT_MODEL = "iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"


class AsrEngine(Protocol):
    name: str
    model_rev: str

    def transcribe(self, wav: str | pathlib.Path, hotwords: list[str]) -> dict[str, Any]:
        """Return {"text", "tokens":[{t,s,e}] (seconds, part-relative), "proc_sec", "n_vad_segments"?}."""
        ...


def read_hotwords(path: pathlib.Path | None, limit: int | None = None) -> list[str]:
    """One term per line; ignore blanks, comments and any trailing weight column."""
    if path is None or not path.exists():
        return []
    out: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        term = line.split()[0]
        if term not in seen:
            seen.add(term)
            out.append(term)
    if limit:
        out = out[: int(limit)]
    return out


def tokens_from_funasr_result(r0: dict[str, Any]) -> list[dict[str, Any]]:
    """Build [{t, s, e}] (seconds) from one FunASR result dict.

    Prefer raw_text tokens (1:1 with timestamp); fall back to mapping the
    punctuated text's non-punct chars onto timestamps.
    """
    ts = r0.get("timestamp") or []
    if not ts:
        return []
    raw = r0.get("raw_text")
    if isinstance(raw, str):
        toks = raw.split()
        if len(toks) == len(ts):
            return [{"t": t, "s": int(a) / 1000.0, "e": int(b) / 1000.0}
                    for t, (a, b) in zip(toks, ts)]
        log.warning("raw_text tokens (%d) != timestamps (%d); falling back to char map",
                    len(toks), len(ts))
    return tokens_from_timestamp_pairs(r0.get("text") or "", ts)


@contextlib.contextmanager
def _mmap_torch_load():
    """Temporarily make torch.load(path) memory-map checkpoints."""
    import torch
    orig = torch.load

    def _load(*a, **k):
        if a and isinstance(a[0], (str, os.PathLike)):
            k.setdefault("mmap", True)
        return orig(*a, **k)

    torch.load = _load
    try:
        yield
    finally:
        torch.load = orig


class FunAsrEngine:
    name = "seaco-paraformer"

    def __init__(self, cfg: dict[str, Any]):
        self.cfg = dict(cfg or {})
        self.model_id = self.cfg.get("model") or DEFAULT_MODEL
        self.vad = self.cfg.get("vad_model", "fsmn-vad")
        self.punc = self.cfg.get("punc_model", "ct-punc")
        self.batch_size_s = int(self.cfg.get("batch_size_s", 300))
        self.max_seg_ms = int(self.cfg.get("vad_max_single_segment_ms", 60000))
        self.threads = self.cfg.get("num_threads")
        self._m = None
        self.load_sec = 0.0
        self.model_rev = ""

    def load(self) -> None:
        if self._m is not None:
            return
        try:
            from funasr import AutoModel
            import torch
        except ImportError as e:
            raise RuntimeError(
                "funasr not installed in this environment. Run `uv sync --extra asr` "
                "(installs funasr + torch CPU), or use --from-cache for the demo."
            ) from e
        if self.threads:
            torch.set_num_threads(int(self.threads))
        t0 = time.time()
        with _mmap_torch_load():
            self._m = AutoModel(
                model=self.model_id, vad_model=self.vad, punc_model=self.punc,
                vad_kwargs={"max_single_segment_time": self.max_seg_ms},
                disable_update=True, disable_pbar=True, log_level="ERROR",
                # AutoModel calls torch.set_num_threads(ncpu) itself (default 4)
                **({"ncpu": int(self.threads)} if self.threads else {}),
            )
        self.load_sec = time.time() - t0
        self.model_rev = self._model_rev()
        log.info("FunASR loaded in %.1fs (%s, rev=%s, threads=%s)",
                 self.load_sec, self.model_id, self.model_rev, torch.get_num_threads())

    def _model_rev(self) -> str:
        path = (getattr(self._m, "kwargs", {}) or {}).get("model_path") or ""
        rev = ""
        for name in ("configuration.json",):
            p = pathlib.Path(path) / name
            if p.exists():
                try:
                    rev = json.loads(p.read_text(encoding="utf-8")).get("model_revision", "") or ""
                except Exception:
                    pass
        try:
            import funasr
            fv = funasr.__version__
        except Exception:
            fv = "?"
        return f"{rev or 'master'}|funasr-{fv}"

    def transcribe(self, wav: str | pathlib.Path, hotwords: list[str]) -> dict[str, Any]:
        self.load()
        assert self._m is not None
        kw: dict[str, Any] = {"batch_size_s": self.batch_size_s, "return_raw_text": True}
        if hotwords:
            kw["hotword"] = " ".join(hotwords)
        t0 = time.time()
        res = self._m.generate(input=str(wav), **kw)
        dt = time.time() - t0
        if not res:
            return {"text": "", "tokens": [], "proc_sec": dt}
        r0 = res[0] if isinstance(res, list) else res
        return {"text": r0.get("text") or "", "tokens": tokens_from_funasr_result(r0), "proc_sec": dt}


_ENGINES: dict[str, AsrEngine] = {}


def get_engine(cfg: dict[str, Any]) -> AsrEngine:
    """Process-wide engine cache: one FunASR model per (model, vad, punc)."""
    key = json.dumps({k: cfg.get(k) for k in ("model", "vad_model", "punc_model", "batch_size_s",
                                               "vad_max_single_segment_ms", "num_threads")},
                     sort_keys=True)
    eng = _ENGINES.get(key)
    if eng is None:
        eng = FunAsrEngine(cfg)
        _ENGINES[key] = eng
    return eng
