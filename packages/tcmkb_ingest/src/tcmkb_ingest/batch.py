"""Batch ingest: many videos -> s00..s08 with one shared ASR model.

- Inputs: a manifest (CSV or YAML) or a directory + series.
- Resumable: each video goes through `run_pipeline`, which skips steps whose
  version_key is already done; s04 also checkpoints per audio part.
- Failures: a video that raises is recorded (step_run row -> failed, plus the
  batch report) and the batch continues with the next video.
- One ASR model per process: the engine is created once and passed to every
  video; it loads lazily on first real transcription (a fully-resumed batch
  never loads FunASR).
- Report: data/batch/<run_id>.json + .csv with per-video wall time, audio
  seconds, ASR RTF, corrections, chapters; peak memory for the process.
"""
from __future__ import annotations
import csv, datetime, hashlib, json, os, pathlib, re, threading, time, traceback
from dataclasses import dataclass, asdict, field
from typing import Any, Iterable

import yaml

from tcmkb_core.config import repo_root, load_asr_config, load_pipeline_config
from tcmkb_ingest.scheduler import run_pipeline
from tcmkb_ingest.state import StateDB
from tcmkb_ingest.steps import normalize_step
from tcmkb_ingest.steps.base import log

MEDIA_EXTS = (".mp4", ".mkv", ".avi", ".flv", ".mov", ".wmv", ".rmvb", ".ts", ".webm",
              ".m4a", ".mp3", ".aac", ".wav", ".flac")


@dataclass
class BatchItem:
    file: str
    series_id: str
    video_id: str
    episode: int = 0
    title: str = ""
    source: dict[str, Any] | None = None   # YouTube citation (sources.MediaEntry.source())


@dataclass
class ItemResult:
    video_id: str
    series_id: str
    file: str
    status: str = "pending"          # ok | failed
    failed_step: str | None = None
    error: str | None = None
    wall_sec: float = 0.0
    audio_sec: float | None = None
    asr_proc_sec: float | None = None
    rtf: float | None = None
    asr_reused: bool = False
    n_tokens: int | None = None
    n_segments: int | None = None
    n_corrections: int | None = None
    n_chapters: int | None = None
    steps_run: list[str] = field(default_factory=list)
    steps_skipped: list[str] = field(default_factory=list)


# --------------------------------------------------------------------- inputs
_NUM = re.compile(r"(\d+)")


def _episode_from_name(stem: str) -> int | None:
    m = _NUM.search(stem)
    return int(m.group(1)) if m else None


def _stem_id(series: str, stem: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9 ._-]+", stem):
        slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
        if slug:
            return f"{series}-{slug}"[:64]
    return f"{series}-{hashlib.sha1(stem.encode('utf-8')).hexdigest()[:8]}"


def items_from_dir(folder: str | pathlib.Path, series_id: str, *, pattern: str | None = None,
                   recursive: bool = True, id_scheme: str = "auto") -> list[BatchItem]:
    """Media files under `folder` -> items. video_id:
    - episode: `{series}-{NNN}` from the first number in the filename (must be unique);
    - stem:    `{series}-{ascii-stem}` or `{series}-{sha1(stem)[:8]}` for non-ASCII names;
    - auto:    episode if every file has a unique number, else stem.
    """
    folder = pathlib.Path(folder)
    globber = folder.rglob if recursive else folder.glob
    files = sorted(p for p in globber(pattern or "*")
                   if p.is_file() and (pattern or p.suffix.lower() in MEDIA_EXTS))
    eps = [_episode_from_name(p.stem) for p in files]
    use_ep = id_scheme == "episode" or (
        id_scheme == "auto" and files and all(e is not None for e in eps) and len(set(eps)) == len(eps))
    if id_scheme == "episode" and (None in eps or len(set(eps)) != len(eps)):
        raise ValueError("id_scheme=episode but filenames lack unique episode numbers")
    out = []
    for p, ep in zip(files, eps):
        vid = f"{series_id}-{ep:03d}" if use_ep else _stem_id(series_id, p.stem)
        out.append(BatchItem(file=str(p.resolve()), series_id=series_id, video_id=vid,
                             episode=ep or 0, title=p.stem))
    _check_unique(out)
    return out


def _norm_row(row: dict[str, Any], default_series: str | None, base: pathlib.Path) -> BatchItem:
    row = {str(k).strip().lower(): (v.strip() if isinstance(v, str) else v)
           for k, v in row.items() if k is not None}
    f = row.get("file") or row.get("path") or row.get("source")
    if not f:
        raise ValueError(f"manifest row without file: {row}")
    fp = pathlib.Path(str(f)).expanduser()
    if not fp.is_absolute():
        fp = (base / fp)
    series = row.get("series") or row.get("series_id") or default_series
    if not series:
        raise ValueError(f"manifest row without series (and no --series): {row}")
    ep_raw = row.get("episode")
    ep = int(ep_raw) if ep_raw not in (None, "") else (_episode_from_name(fp.stem) or 0)
    vid = row.get("video_id") or row.get("video") or (
        f"{series}-{ep:03d}" if ep else _stem_id(str(series), fp.stem))
    return BatchItem(file=str(fp), series_id=str(series), video_id=str(vid), episode=ep,
                     title=str(row.get("title") or fp.stem))


def items_from_manifest(path: str | pathlib.Path, default_series: str | None = None) -> list[BatchItem]:
    """CSV (header: file,series[,video_id,episode,title]) or YAML (list, or {videos: [...]})."""
    path = pathlib.Path(path)
    base = path.parent.resolve()
    if path.suffix.lower() in (".yaml", ".yml", ".json"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        rows = data.get("videos", []) if isinstance(data, dict) else (data or [])
        default_series = (data.get("series") if isinstance(data, dict) else None) or default_series
    else:
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows = [r for r in csv.DictReader(
                (ln for ln in fh if ln.strip() and not ln.lstrip().startswith("#")))]
    items = [_norm_row(r, default_series, base) for r in rows]
    _check_unique(items)
    return items


def _check_unique(items: Iterable[BatchItem]) -> None:
    seen: dict[str, str] = {}
    for it in items:
        if it.video_id in seen:
            raise ValueError(f"duplicate video_id {it.video_id}: {seen[it.video_id]} / {it.file}")
        seen[it.video_id] = it.file


# --------------------------------------------------------------------- memory
class MemMonitor:
    """Samples this process' RSS / anon RSS (Linux /proc) to report peaks."""

    def __init__(self, interval: float = 0.2):
        self.interval = interval
        self.peak_rss_mb = 0.0
        self.peak_anon_mb = 0.0
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, daemon=True)

    @staticmethod
    def read() -> dict[str, float]:
        out: dict[str, float] = {}
        try:
            for line in open("/proc/self/status", encoding="ascii"):
                k, _, v = line.partition(":")
                if k in ("VmRSS", "RssAnon", "VmHWM"):
                    out[k] = int(v.split()[0]) / 1024.0
        except OSError:
            pass
        return out

    def _run(self):
        while not self._stop.is_set():
            r = self.read()
            self.peak_rss_mb = max(self.peak_rss_mb, r.get("VmRSS", 0))
            self.peak_anon_mb = max(self.peak_anon_mb, r.get("RssAnon", 0))
            self._stop.wait(self.interval)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join(timeout=2)

    def summary(self) -> dict[str, float]:
        r = self.read()
        return {"peak_rss_mb": round(max(self.peak_rss_mb, r.get("VmHWM", 0)), 1),
                "peak_anon_rss_mb": round(self.peak_anon_mb, 1)}


# ---------------------------------------------------------------------- run
def _done_metrics(db: StateDB, video_id: str) -> dict[str, dict[str, Any]]:
    m = db.get_video(video_id)
    out: dict[str, dict[str, Any]] = {}
    if not m:
        return out
    for step, vk in (m.active_versions or {}).items():
        sr = db.get_step(video_id, step, vk)
        if sr and sr.status in ("done", "skipped"):
            out[step] = sr.metrics or {}
    return out


def _fmt_eta(sec: float) -> str:
    return str(datetime.timedelta(seconds=int(max(sec, 0))))


def run_batch(items: list[BatchItem], *, to_step: str = "s08", from_step: str | None = None,
              force: bool = False, from_cache: bool = False, skip_alt: bool = True,
              cache_dir: str | None = None, root: pathlib.Path | None = None,
              engine: Any = None, fail_fast: bool = False,
              report_dir: pathlib.Path | None = None, run_id: str | None = None,
              after_item: Any = None) -> dict[str, Any]:
    root = root or repo_root()
    to_step = normalize_step(to_step)
    pipe = load_pipeline_config(root)
    if engine is None and not from_cache:
        from tcmkb_ingest.asr_engine import get_engine
        engine = get_engine(load_asr_config(root))  # lazy: loads on first transcription
    run_id = run_id or datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report_dir = report_dir or (root / pipe.get("data_dir", "data") / "batch")
    report_dir.mkdir(parents=True, exist_ok=True)
    results: list[ItemResult] = []
    t_batch = time.time()
    audio_done = 0.0
    with MemMonitor() as mem:
        for i, it in enumerate(items, 1):
            r = ItemResult(video_id=it.video_id, series_id=it.series_id, file=it.file)
            log.info("[batch %d/%d] %s (%s) %s", i, len(items), it.video_id, it.series_id, it.file)
            t0 = time.time()
            try:
                out = run_pipeline(
                    it.video_id, to_step=to_step, from_step=from_step, force=force,
                    from_cache=from_cache, skip_alt=skip_alt, cache_dir=cache_dir,
                    source_path=it.file, series_id=it.series_id, episode=it.episode,
                    title=it.title or it.video_id, source_meta=it.source, root=root, engine=engine,
                )
                r.status = "ok"
                for step, v in out["steps"].items():
                    (r.steps_skipped if isinstance(v, dict) and v.get("skipped") else r.steps_run).append(step)
            except Exception as e:  # keep going; failure is recorded
                r.status = "failed"
                r.error = f"{type(e).__name__}: {e}"
                log.error("[batch %d/%d] %s FAILED: %s\n%s", i, len(items), it.video_id, r.error,
                          traceback.format_exc(limit=3))
            r.wall_sec = round(time.time() - t0, 2)
            db = StateDB(root / pipe.get("state_db", "data/state.sqlite"))
            try:
                if r.status == "failed":
                    fs = db.failed_steps(it.video_id)
                    r.failed_step = fs[-1]["step"] if fs else None
                dm = _done_metrics(db, it.video_id)
            finally:
                db.close()
            a = dm.get("s04_asr", {})
            r.audio_sec = a.get("audio_sec") or dm.get("s03_audio", {}).get("duration_s")
            r.asr_proc_sec = a.get("proc_sec")
            r.rtf = a.get("rtf") or ((a["proc_sec"] / r.audio_sec) if a.get("proc_sec") and r.audio_sec else None)
            r.asr_reused = "s04_asr" in r.steps_skipped
            r.n_tokens = a.get("n_tokens")
            r.n_segments = dm.get("s06_clean", {}).get("n_segments")
            r.n_corrections = dm.get("s06_clean", {}).get("n_edits")
            r.n_chapters = dm.get("s08_chapter", {}).get("n_chapters")
            results.append(r)
            if after_item is not None:        # e.g. budget mode: verify + purge right away
                try:
                    after_item(it, r)
                except Exception as e:  # never lose the batch over cleanup
                    log.error("after_item %s failed: %s", it.video_id, e)
            audio_done += float(r.audio_sec or 0)
            el = time.time() - t_batch
            eta = el / i * (len(items) - i)
            mm = MemMonitor.read()
            log.info("[batch %d/%d] %s %s wall=%.1fs audio=%.0fs rtf=%s edits=%s chapters=%s "
                     "| elapsed=%s eta=%s rss=%.0fMB",
                     i, len(items), it.video_id, r.status, r.wall_sec, r.audio_sec or 0,
                     f"{r.rtf:.4f}" if r.rtf else "-", r.n_corrections, r.n_chapters,
                     _fmt_eta(el), _fmt_eta(eta), mm.get("VmRSS", 0))
            _write_report(report_dir, run_id, results, t_batch, mem, engine, partial=True)
            if fail_fast and r.status == "failed":
                break
    return _write_report(report_dir, run_id, results, t_batch, mem, engine, partial=False)


def _write_report(report_dir: pathlib.Path, run_id: str, results: list[ItemResult], t_batch: float,
                  mem: MemMonitor, engine: Any, partial: bool) -> dict[str, Any]:
    wall = time.time() - t_batch
    audio = sum(float(r.audio_sec or 0) for r in results if r.status == "ok")
    asr = sum(float(r.asr_proc_sec or 0) for r in results if r.status == "ok" and not r.asr_reused)
    rep = {
        "run_id": run_id,
        "finished": not partial,
        "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "n_items": len(results),
        "n_ok": sum(r.status == "ok" for r in results),
        "n_failed": sum(r.status == "failed" for r in results),
        "wall_sec": round(wall, 2),
        "audio_sec_ok": round(audio, 2),
        "asr_proc_sec_fresh": round(asr, 2),
        "model_load_sec": round(float(getattr(engine, "load_sec", 0) or 0), 2) if engine else None,
        "model_loaded": bool(getattr(engine, "_m", None) is not None) if engine else False,
        "overall_rtf_wall": round(wall / audio, 5) if audio else None,
        **mem.summary(),
        "items": [asdict(r) for r in results],
    }
    jp = report_dir / f"{run_id}.json"
    tmp = jp.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, jp)
    cols = ["video_id", "series_id", "status", "failed_step", "wall_sec", "audio_sec",
            "asr_proc_sec", "rtf", "asr_reused", "n_tokens", "n_segments", "n_corrections",
            "n_chapters", "error", "file"]
    with (report_dir / f"{run_id}.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in results:
            w.writerow(asdict(r))
    rep["report_path"] = str(jp)
    return rep
