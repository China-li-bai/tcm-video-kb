"""Disk-budgeted batches: plan -> run -> verify -> purge heavy media.

Per item the pipeline now writes (see docs/DISK_BUDGET.md):
  source audio (data/media, already on disk)        ~45 MB/h @ 96 kbps
  s03 wav parts (16 kHz mono s16le, transient)      115.2 MB/h
  lightweight outputs (asr_raw, segments, chapters) ~3-5 MB/h
A batch is a set of pending items whose estimated working set
(source + wav + overhead) fits `budget_gb`, and whose *new* bytes (wav + outputs)
keep at least `min_free_gb` free. After an item's outputs are verified, its heavy
files are deleted and a `media_purge` row is written (SQLite) plus
data/media/{series}/_purged.json, keeping the YouTube URL as the citation /
re-fetch reference. Purged items are never re-planned and their s00..s05 are
skipped by the scheduler; `refetch` re-downloads from the URL and re-enables them.
"""
from __future__ import annotations
import datetime, json, os, pathlib, re, shutil, subprocess, time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Iterable

from tcmkb_core.config import repo_root, load_pipeline_config
from tcmkb_ingest import artifacts as art
from tcmkb_ingest.batch import BatchItem, run_batch
from tcmkb_ingest.sources import MediaEntry, is_stable, load_catalog, media_dir
from tcmkb_ingest.state import StateDB
from tcmkb_ingest.steps.base import log

GB = 1024 ** 3


class DiskSpaceError(RuntimeError):
    pass


@dataclass
class Budget:
    budget_bytes: int = 40 * GB
    min_free_bytes: int = 15 * GB
    wav_bytes_per_s: int = 32000
    overhead_bytes: int = 50_000_000
    min_age_s: float = 120.0

    @classmethod
    def from_config(cls, root: pathlib.Path, budget_gb: float | None = None,
                    min_free_gb: float | None = None) -> "Budget":
        c = load_pipeline_config(root).get("budget") or {}
        return cls(
            budget_bytes=int(float(budget_gb if budget_gb is not None else c.get("budget_gb", 40)) * GB),
            min_free_bytes=int(float(min_free_gb if min_free_gb is not None else c.get("min_free_gb", 15)) * GB),
            wav_bytes_per_s=int(c.get("wav_bytes_per_s", 32000)),
            overhead_bytes=int(c.get("overhead_bytes", 50_000_000)),
            min_age_s=float(c.get("min_age_s", 120)),
        )


@dataclass
class Estimate:
    video_id: str
    source_bytes: int
    wav_bytes: int
    overhead_bytes: int

    @property
    def working_set(self) -> int:
        return self.source_bytes + self.wav_bytes + self.overhead_bytes

    @property
    def new_bytes(self) -> int:        # bytes the run adds to the disk (source is already there)
        return self.wav_bytes + self.overhead_bytes


def estimate(e: MediaEntry, b: Budget) -> Estimate:
    dur = float(e.extra.get("probed_duration_s") or e.duration_s or 0.0)
    if not dur and e.size_bytes:                       # unknown duration: assume 64 kbps
        dur = e.size_bytes / 8000.0
    return Estimate(e.video_id, int(e.size_bytes), int(dur * b.wav_bytes_per_s), b.overhead_bytes)


# ------------------------------------------------------------------ item state
def verify_outputs(db: StateDB, artifacts_base: pathlib.Path, video_id: str,
                   expect_duration_s: float | None = None, min_coverage: float = 0.95,
                   require_cite: bool = True) -> tuple[bool, dict[str, Any]]:
    """Transcript JSON present & non-empty, segments/chapters present, citations attached."""
    info: dict[str, Any] = {"video_id": video_id}
    m = db.get_video(video_id)
    if not m:
        return False, {**info, "error": "not registered"}
    av = m.active_versions or {}
    for step in ("s04_asr", "s06_clean", "s08_chapter"):
        vk = av.get(step)
        if not vk or not db.find_done(video_id, step, vk):
            return False, {**info, "error": f"{step} not done"}
    d = artifacts_base / video_id
    try:
        asr = json.loads((d / "s04_asr" / av["s04_asr"] / "asr_raw.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return False, {**info, "error": f"asr_raw.json unreadable: {e}"}
    n_tok, n_chars = len(asr.get("tokens") or []), len((asr.get("text") or "").strip())
    audio = float((asr.get("metrics") or {}).get("audio_sec") or 0)
    info.update(n_tokens=n_tok, n_chars=n_chars, audio_sec=audio)
    if not n_tok or not n_chars:
        return False, {**info, "error": "empty transcript"}
    exp = expect_duration_s if expect_duration_s is not None else float(m.duration_s or 0)
    if exp and audio < min_coverage * exp:
        return False, {**info, "error": f"audio coverage {audio:.0f}s < {min_coverage:.0%} of {exp:.0f}s"}
    seg_p = d / "s06_clean" / av["s06_clean"] / "segments.jsonl"
    segs = [json.loads(x) for x in seg_p.read_text(encoding="utf-8").splitlines() if x.strip()] \
        if seg_p.exists() else []
    chap_p = d / "s08_chapter" / av["s08_chapter"] / "chapters.json"
    chaps = json.loads(chap_p.read_text(encoding="utf-8")) if chap_p.exists() else []
    info.update(n_segments=len(segs), n_chapters=len(chaps))
    if not segs or not chaps:
        return False, {**info, "error": "no segments/chapters"}
    src = (m.meta or {}).get("source") or {}
    if require_cite and src.get("url"):
        bad = sum(1 for s in segs if not (s.get("cite") or {}).get("t_url"))
        bad += sum(1 for c in chaps if not (c.get("cite") or {}).get("t_url"))
        if bad:
            return False, {**info, "error": f"{bad} segments/chapters without citation"}
    info["source_url"] = src.get("url")
    return True, info


def item_status(db: StateDB, e: MediaEntry, artifacts_base: pathlib.Path, b: Budget,
                now: float | None = None) -> str:
    """purged | done (verified, media still present) | pending | downloading | missing."""
    if db.is_purged(e.video_id):
        return "purged"
    if db.get_video(e.video_id):
        ok, _ = verify_outputs(db, artifacts_base, e.video_id)
        if ok:
            return "done"
    if not e.file:
        return "missing"
    if not is_stable(e, min_age_s=b.min_age_s, now=now):
        return "downloading"
    exp = e.duration_s
    probed = e.extra.get("probed_duration_s")
    if exp and probed and probed < 0.97 * exp:
        return "downloading"                         # truncated / partial file
    return "pending"


def plan_batch(candidates: Iterable[MediaEntry], b: Budget, free_bytes: int
               ) -> tuple[list[MediaEntry], list[dict[str, Any]]]:
    """Greedy, in catalog order. Pure: the caller supplies status filtering and free space.

    - refuses (DiskSpaceError) when free space is already below the safety margin;
    - an item joins while sum(working_set) <= budget and free - sum(new_bytes) >= margin;
    - an item that is bigger than the whole budget runs alone if the margin allows.
    """
    if free_bytes < b.min_free_bytes:
        raise DiskSpaceError(f"free {free_bytes / GB:.1f} GB < safety margin {b.min_free_bytes / GB:.1f} GB")
    chosen: list[MediaEntry] = []
    deferred: list[dict[str, Any]] = []
    ws = new = 0
    for e in candidates:
        est = estimate(e, b)
        fits_budget = ws + est.working_set <= b.budget_bytes or (not chosen and est.working_set > b.budget_bytes)
        fits_disk = free_bytes - (new + est.new_bytes) >= b.min_free_bytes
        if fits_budget and fits_disk:
            chosen.append(e)
            ws += est.working_set
            new += est.new_bytes
        else:
            deferred.append({"video_id": e.video_id, "working_set_gb": round(est.working_set / GB, 2),
                             "reason": "budget" if not fits_budget else "free_disk"})
    return chosen, deferred


# ------------------------------------------------------------------ purge
# Purge may only ever delete an item's *own* heavy media. Everything is resolved and
# checked against a per-item allowlist; anything else (repo dirs such as eval/asr/out,
# lexicon/, configs/, a source file outside data/media/<series>/, git-tracked files, an
# empty/odd video_id that would widen a glob) is refused and logged, never deleted.
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*$")
_MEDIA_EXT = (".m4a", ".mp4", ".wav", ".mp3", ".webm", ".opus", ".aac", ".flac", ".part")


class UnsafePurgePath(RuntimeError):
    pass


def _inside(p: pathlib.Path, base: pathlib.Path) -> bool:
    """p strictly inside base (both resolved, without following p's final symlink)."""
    try:
        rp = p.parent.resolve() / p.name
        rb = base.resolve()
    except OSError:
        return False
    return rp != rb and rb in rp.parents


def _git_tracked_under(root: pathlib.Path, p: pathlib.Path) -> list[str]:
    """Git-tracked files at/under p (empty when not a git checkout)."""
    if not (root / ".git").exists():
        return []
    try:
        rel = (p.parent.resolve() / p.name).relative_to(root.resolve())
    except ValueError:
        return []
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", str(rel)],
                           capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    return [x for x in r.stdout.decode("utf-8", "replace").split("\0") if x]


def purge_roots(root: pathlib.Path, artifacts_base: pathlib.Path, video_id: str,
                series_id: str | None) -> dict[str, pathlib.Path]:
    pipe = load_pipeline_config(root)
    mirror = root / (pipe.get("r2_mirror") or "data/r2-mirror")
    out = {"artifacts": artifacts_base / video_id, "mirror": mirror}
    if series_id and _SAFE_ID.match(series_id):
        out["media"] = media_dir(root, series_id)
    return out


def check_purge_path(root: pathlib.Path, p: pathlib.Path, video_id: str,
                     roots: dict[str, pathlib.Path]) -> str:
    """Return the allowlist rule that permits deleting p, or raise UnsafePurgePath."""
    if not _SAFE_ID.match(video_id or ""):
        raise UnsafePurgePath(f"unsafe video_id {video_id!r}")
    rp = p.parent.resolve() / p.name
    rr = root.resolve()
    if rp == rr or rp in rr.parents:
        raise UnsafePurgePath(f"{p} is the repo root or above it")
    media, arts, mirror = roots.get("media"), roots["artifacts"], roots["mirror"]
    rule = None
    if media is not None and _inside(p, media) and rp.parent == media.resolve() \
            and rp.name.startswith(video_id + ".") and not p.is_dir():
        rule = "media_source"                      # data/media/<series>/<id>.<ext>
    elif _inside(p, arts):
        rel = rp.relative_to(arts.resolve()).parts
        if len(rel) == 3 and rel[0] == "s03_audio" and rel[2] == "audio":
            rule = "wav_parts"                     # data/artifacts/<id>/s03_audio/<vk>/audio
        elif len(rel) == 3 and rel[0] == "s04_asr" and rel[2] == "parts":
            rule = "asr_checkpoints"               # data/artifacts/<id>/s04_asr/<vk>/parts
        elif len(rel) == 3 and rel[0] == "s02_media" and rp.suffix.lower() in _MEDIA_EXT and not p.is_dir():
            rule = "media_copy"
        elif len(rel) == 3 and rel[0] == "s01_upload" and rel[2].startswith("source.") and not p.is_dir():
            rule = "upload_copy"
    elif _inside(p, mirror):
        rel = rp.relative_to(mirror.resolve()).parts
        if len(rel) == 2 and rel[0] in ("source", "play") and rel[1].startswith(video_id + "."):
            rule = "mirror_media"
        elif len(rel) == 2 and rel[0] == "artifacts" and rel[1] == video_id:
            rule = "mirror_artifacts"
    if rule is None:
        raise UnsafePurgePath(f"{p} is outside {video_id}'s heavy-media allowlist")
    tracked = _git_tracked_under(root, p)
    if tracked:
        raise UnsafePurgePath(f"{p} contains git-tracked files (e.g. {tracked[0]})")
    return rule


def heavy_paths(root: pathlib.Path, artifacts_base: pathlib.Path, video_id: str,
                source_path: str | None, keep_source: bool = False, series_id: str | None = None,
                refused: list[dict[str, str]] | None = None) -> list[pathlib.Path]:
    """Heavy files/dirs of one item that pass `check_purge_path`; refusals go to `refused`."""
    if not _SAFE_ID.match(video_id or ""):
        raise UnsafePurgePath(f"unsafe video_id {video_id!r}")
    if series_id is None:
        series_id = video_id.split("-", 1)[0] if "-" in video_id else None
    roots = purge_roots(root, artifacts_base, video_id, series_id)
    out: list[pathlib.Path] = []
    if source_path and not keep_source:
        out.append(pathlib.Path(source_path))
    d = roots["artifacts"]
    out += sorted(d.glob("s03_audio/*/audio"))                    # wav parts (all versions)
    out += sorted(d.glob("s04_asr/*/parts"))                      # per-part ASR checkpoints
    out += [p for p in d.glob("s02_media/*/*") if p.suffix.lower() in _MEDIA_EXT]
    out += [p for p in d.glob("s01_upload/*/source.*")]
    mirror = roots["mirror"]
    out += sorted(mirror.glob(f"source/{video_id}.*")) + sorted(mirror.glob(f"play/{video_id}.*"))
    out.append(mirror / "artifacts" / video_id)
    seen, uniq = set(), []
    for p in out:
        if not (p.exists() or p.is_symlink()) or str(p) in seen:
            continue
        seen.add(str(p))
        try:
            check_purge_path(root, p, video_id, roots)
        except UnsafePurgePath as ex:
            log.warning("purge %s: REFUSED %s", video_id, ex)
            if refused is not None:
                refused.append({"path": str(p), "reason": str(ex)})
            continue
        uniq.append(p)
    return uniq


def _size(p: pathlib.Path) -> int:
    if p.is_symlink() or p.is_file():
        return p.lstat().st_size if p.is_symlink() else p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())


def purge_item(root: pathlib.Path, db: StateDB, artifacts_base: pathlib.Path, e: MediaEntry | None,
               video_id: str, verify: dict[str, Any], *, batch_id: str | None = None,
               keep_source: bool = False, dry_run: bool = False) -> dict[str, Any]:
    m = db.get_video(video_id)
    if not m:
        raise RuntimeError(f"{video_id} not registered")
    src = (m.meta or {}).get("source") or (e.source() if e else {}) or {}
    refused: list[dict[str, str]] = []
    paths = heavy_paths(root, artifacts_base, video_id, m.source_path, keep_source=keep_source,
                        series_id=m.series_id, refused=refused)
    files = [{"path": str(p), "bytes": _size(p)} for p in paths]
    freed = sum(f["bytes"] for f in files)
    rec = {"video_id": video_id, "series_id": m.series_id, "episode": m.episode, "title": m.title,
           "youtube_id": src.get("youtube_id"), "source_url": src.get("url"),
           "source_path": m.source_path, "source_sha256": m.source_sha256,
           "source_bytes": m.source_bytes, "duration_s": m.duration_s,
           "bytes_freed": freed, "files": files, "refused": refused, "verify": verify,
           "batch_id": batch_id}
    if dry_run:
        return {**rec, "dry_run": True}
    roots = purge_roots(root, artifacts_base, video_id, m.series_id)
    for p in paths:
        check_purge_path(root, p, video_id, roots)        # re-check right before deleting
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p, ignore_errors=True)
        else:
            try:
                p.unlink()
            except FileNotFoundError:
                pass
    db.record_purge(rec)
    _append_purged_manifest(root, m.series_id, rec)
    log.info("purged %s: %.1f MB freed (%d paths); cite=%s", video_id, freed / 1e6, len(paths),
             src.get("url"))
    return rec


def _append_purged_manifest(root: pathlib.Path, series_id: str, rec: dict[str, Any]) -> None:
    """data/media/{series}/_purged.json: file -> YouTube URL map for media no longer on disk."""
    p = media_dir(root, series_id) / "_purged.json"
    data = {"series": series_id, "items": {}}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            pass
    data.setdefault("items", {})[rec["video_id"]] = {
        k: rec.get(k) for k in ("video_id", "episode", "title", "youtube_id", "source_url",
                                "source_path", "source_sha256", "source_bytes", "duration_s",
                                "bytes_freed", "batch_id")}
    data["items"][rec["video_id"]]["purged_at"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    data["updated_at"] = data["items"][rec["video_id"]]["purged_at"]
    art.atomic_write_json(p, data)
    ids = media_dir(root, series_id) / "_purged_ids.txt"
    lines = set(ids.read_text().split()) if ids.exists() else set()
    if rec.get("youtube_id"):
        lines.add(rec["youtube_id"])
    art.atomic_write_text(ids, "".join(f"{x}\n" for x in sorted(lines)))


# ------------------------------------------------------------------ driver
def entry_to_item(e: MediaEntry) -> BatchItem:
    return BatchItem(file=str(e.file), series_id=e.series_id, video_id=e.video_id,
                     episode=e.episode, title=e.title or e.video_id, source=e.source())


def _free_bytes(root: pathlib.Path) -> int:
    return shutil.disk_usage(root / "data").free


def collect(root: pathlib.Path, series: list[str], db: StateDB, artifacts_base: pathlib.Path,
            b: Budget) -> list[tuple[MediaEntry, str]]:
    out = []
    for s in series:
        for e in load_catalog(root, s):
            out.append((e, item_status(db, e, artifacts_base, b)))
    return out


def run_budgeted(series: list[str], *, root: pathlib.Path | None = None, budget: Budget | None = None,
                 purge: bool = True, keep_source: bool = False, max_batches: int = 0,
                 limit: int = 0, only: set[str] | None = None, engine: Any = None,
                 dry_run: bool = False, free_bytes_fn: Callable[[pathlib.Path], int] | None = None,
                 run_id: str | None = None, **batch_kw) -> dict[str, Any]:
    root = root or repo_root()
    b = budget or Budget.from_config(root)
    pipe = load_pipeline_config(root)
    abase = root / pipe.get("artifacts_dir", "data/artifacts")
    dbp = root / pipe.get("state_db", "data/state.sqlite")
    free_fn = free_bytes_fn or _free_bytes
    run_id = run_id or datetime.datetime.now().strftime("budget-%Y%m%d-%H%M%S")
    summary: dict[str, Any] = {"run_id": run_id, "batches": [], "purged": [], "refused": None}
    done_now: set[str] = set()
    n = 0
    while True:
        db = StateDB(dbp)
        try:
            rows = collect(root, series, db, abase, b)
            if purge and not dry_run:      # verified but unpurged (e.g. crash after s08): purge first
                for e, st in rows:
                    if st == "done" and (not only or e.video_id in only):
                        ok, info = verify_outputs(db, abase, e.video_id)
                        if ok:
                            summary["purged"].append(purge_item(root, db, abase, e, e.video_id, info,
                                                                batch_id=run_id, keep_source=keep_source))
                rows = collect(root, series, db, abase, b)
        finally:
            db.close()
        pending = [e for e, st in rows if st == "pending" and e.video_id not in done_now
                   and (not only or e.video_id in only)]
        if limit:
            pending = pending[: max(limit - len(done_now), 0)]
        summary["status_counts"] = _counts(rows)
        if not pending:
            break
        free = free_fn(root)
        try:
            chosen, deferred = plan_batch(pending, b, free)
        except DiskSpaceError as ex:
            summary["refused"] = str(ex)
            log.error("refusing batch: %s", ex)
            break
        if not chosen:
            summary["refused"] = f"nothing fits: {deferred[:3]}"
            break
        n += 1
        bid = f"{run_id}-b{n:02d}"
        plan = {"batch_id": bid, "free_gb": round(free / GB, 2),
                "working_set_gb": round(sum(estimate(e, b).working_set for e in chosen) / GB, 2),
                "items": [e.video_id for e in chosen], "deferred": deferred}
        log.info("batch %s: %d items, working set %.2f GB, free %.1f GB: %s", bid, len(chosen),
                 plan["working_set_gb"], free / GB, plan["items"])
        if dry_run:
            summary["batches"].append(plan)
            done_now.update(plan["items"])
            if max_batches and n >= max_batches:
                break
            continue

        by_id = {e.video_id: e for e in chosen}
        purged_here: list[dict[str, Any]] = []

        def after_item(it: BatchItem, r: Any) -> None:
            if r.status != "ok" or not purge:
                return
            db2 = StateDB(dbp)
            try:
                ok, info = verify_outputs(db2, abase, it.video_id)
                r_ok = "verified" if ok else f"NOT verified: {info.get('error')}"
                log.info("verify %s: %s %s", it.video_id, r_ok, info)
                if ok:
                    purged_here.append(purge_item(root, db2, abase, by_id.get(it.video_id), it.video_id,
                                                  info, batch_id=bid, keep_source=keep_source))
            finally:
                db2.close()

        rep = run_batch([entry_to_item(e) for e in chosen], root=root, engine=engine, run_id=bid,
                        after_item=after_item, **batch_kw)
        plan.update(n_ok=rep["n_ok"], n_failed=rep["n_failed"], report=rep.get("report_path"),
                    purged=[p["video_id"] for p in purged_here],
                    freed_gb=round(sum(p["bytes_freed"] for p in purged_here) / GB, 3),
                    free_after_gb=round(free_fn(root) / GB, 2))
        summary["batches"].append(plan)
        summary["purged"] += purged_here
        done_now.update(plan["items"])        # failed items are not retried in the same run
        if max_batches and n >= max_batches:
            break
    summary["purged"] = [{k: p[k] for k in ("video_id", "source_url", "bytes_freed")} for p in summary["purged"]]
    out = root / pipe.get("data_dir", "data") / "batch" / f"{run_id}.plan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    art.atomic_write_json(out, summary)
    summary["summary_path"] = str(out)
    return summary


def _counts(rows: list[tuple[MediaEntry, str]]) -> dict[str, dict[str, int]]:
    c: dict[str, dict[str, int]] = {}
    for e, st in rows:
        c.setdefault(e.series_id, {}).setdefault(st, 0)
        c[e.series_id][st] += 1
    return c


def refetch(root: pathlib.Path, video_id: str, *, run: bool = True) -> dict[str, Any]:
    """Re-download a purged item from its YouTube URL and re-enable s00..s05."""
    pipe = load_pipeline_config(root)
    db = StateDB(root / pipe.get("state_db", "data/state.sqlite"))
    try:
        rec = db.get_purge(video_id) or db.get_purge(video_id, active_only=False)
        if not rec or not rec.get("youtube_id"):
            raise RuntimeError(f"{video_id}: no purge record with a YouTube id")
        series, idx = video_id.split("-", 1)
        cmd = [str(root / "scripts" / "download_one_audio.sh"), series, idx, rec["youtube_id"],
               str(int(rec.get("duration_s") or 0))]
        if run:
            env = {**os.environ, "FORCE_REFETCH": "1"}
            subprocess.run(cmd, check=True, env=env)
            if not pathlib.Path(rec["source_path"]).is_file():
                raise RuntimeError(f"download did not produce {rec['source_path']}")
            db.clear_purge(video_id)
        return {"video_id": video_id, "cmd": cmd, "source_url": rec["source_url"], "refetched": run}
    finally:
        db.close()
