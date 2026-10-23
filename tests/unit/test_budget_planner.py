"""Disk-budget planner, verification, purge + resume, citations (mock ASR, no FunASR)."""
from __future__ import annotations
import json, os, pathlib, shutil, time
import pytest

from tcmkb_ingest.planner import (
    GB, Budget, DiskSpaceError, estimate, item_status, plan_batch, run_budgeted, verify_outputs,
)
from tcmkb_ingest.sources import MediaEntry, cite, load_catalog, parse_playlist, youtube_url
from tcmkb_ingest.state import StateDB

from test_asr_batch import HAS_FFMPEG, MockEngine, _write_wav, kb_root  # noqa: F401 (fixture)


def _e(vid: str, size_mb: float, dur_h: float) -> MediaEntry:
    return MediaEntry(video_id=vid, series_id="shl", episode=int(vid[-3:]), idx=vid[-3:],
                      youtube_id="x" + vid[-3:], duration_s=dur_h * 3600, file=f"/m/{vid}.m4a",
                      size_bytes=int(size_mb * 1e6))


B = Budget(budget_bytes=2 * GB, min_free_bytes=15 * GB, overhead_bytes=0)


# ------------------------------------------------------------------ pure units
def test_youtube_url_and_cite():
    assert youtube_url("abc") == "https://www.youtube.com/watch?v=abc"
    assert youtube_url("abc", 61.9) == "https://www.youtube.com/watch?v=abc&t=61s"
    src = {"video_id": "shl-003", "youtube_id": "abc", "url": youtube_url("abc"), "title": "T",
           "series_id": "shl", "series_title": "伤寒论", "episode": 3}
    c = cite(src, 125.4, 130.0)
    assert c["t_url"] == "/watch/shl-003?t=125"
    assert c["youtube_t_url"] == "https://www.youtube.com/watch?v=abc&t=125s"
    assert c["episode"] == 3 and c["end_s"] == 130.0 and c["video_id"] == "shl-003"
    assert cite(None, 0, 1) is None
    # video_id alone (no youtube) still yields a site cite
    c2 = cite({"video_id": "zj-001"}, 1.2, 2.0, video_id="zj-001")
    assert c2["t_url"] == "/watch/zj-001?t=1" and c2["youtube_t_url"] is None


def test_parse_playlist_tabs_in_title():
    rows = parse_playlist("001\tW-z7\t20040\t倪海廈 1\textra\n\n002\tAB\tNA\t\n")
    assert rows[0] == {"idx": "001", "youtube_id": "W-z7", "duration_s": 20040.0, "title": "倪海廈 1\textra"}
    assert rows[1]["duration_s"] == 0.0


def test_estimate_working_set():
    est = estimate(_e("shl-001", 250, 5.5), B)
    assert est.wav_bytes == int(5.5 * 3600 * 32000)
    assert est.working_set == est.source_bytes + est.wav_bytes
    assert est.new_bytes == est.wav_bytes            # source already on disk


def test_plan_batch_budget_and_free_disk():
    items = [_e("shl-001", 250, 5.5), _e("shl-002", 260, 5.9), _e("shl-005", 33, 0.7)]
    # budget 1.75 GiB: 001 (~0.82) + 002 (~0.88) fit; 005 (~0.11) would exceed -> deferred
    b = Budget(budget_bytes=int(1.75 * GB), min_free_bytes=15 * GB, overhead_bytes=0)
    chosen, deferred = plan_batch(items, b, free_bytes=100 * GB)
    assert [e.video_id for e in chosen] == ["shl-001", "shl-002"]
    assert deferred == [{"video_id": "shl-005", "working_set_gb": pytest.approx(0.11, abs=0.01),
                         "reason": "budget"}]
    # free disk close to margin: only what keeps >= 15 GB free after the new wav bytes
    chosen, deferred = plan_batch(items, b, free_bytes=int(15.7 * GB))
    assert [e.video_id for e in chosen] == ["shl-001", "shl-005"]
    assert deferred[0]["reason"] == "free_disk"
    # below the margin: refuse outright
    with pytest.raises(DiskSpaceError):
        plan_batch(items, B, free_bytes=14 * GB)


def test_plan_batch_oversized_item_runs_alone():
    big = _e("nj-001", 400, 20)                       # ~2.7 GB > 2 GB budget
    chosen, deferred = plan_batch([big, _e("nj-002", 10, 0.1)], B, free_bytes=100 * GB)
    assert [e.video_id for e in chosen] == ["nj-001"] and deferred[0]["video_id"] == "nj-002"


def test_catalog_and_status(tmp_path):
    root = tmp_path
    (root / "configs" / "sources").mkdir(parents=True)
    (root / "configs" / "series.yaml").write_text("series:\n  - {series_id: shl, title: 伤寒论}\n",
                                                  encoding="utf-8")
    (root / "configs" / "sources" / "youtube_renji.yaml").write_text(
        "series:\n  shl:\n    title: 伤寒论\n    best: {url: 'https://yt/pl', channel: C}\n", encoding="utf-8")
    d = root / "data" / "media" / "shl"
    d.mkdir(parents=True)
    (d / "_playlist.txt").write_text("001\tAAA\t600\tEp 1\n002\tBBB\t600\tEp 2\n003\tCCC\t600\tEp 3\n",
                                     encoding="utf-8")
    (d / "shl-001.m4a").write_bytes(b"x" * 5000)
    (d / "shl-002.m4a").write_bytes(b"x" * 5000)
    old = time.time() - 600
    os.utime(d / "shl-001.m4a", (old, old))          # 002 is fresh -> still downloading
    cat = {e.video_id: e for e in load_catalog(root, "shl")}
    assert cat["shl-001"].url == "https://www.youtube.com/watch?v=AAA"
    assert cat["shl-001"].source()["series_title"] == "伤寒论"
    assert cat["shl-001"].source()["playlist_url"] == "https://yt/pl"
    assert cat["shl-003"].file is None
    db = StateDB(root / "data" / "state.sqlite")
    b = Budget()
    st = {v: item_status(db, e, root / "data" / "artifacts", b) for v, e in cat.items()}
    assert st == {"shl-001": "pending", "shl-002": "downloading", "shl-003": "missing"}
    db.record_purge({"video_id": "shl-001", "youtube_id": "AAA"})
    assert item_status(db, cat["shl-001"], root / "data" / "artifacts", b) == "purged"
    db.clear_purge("shl-001")
    assert item_status(db, cat["shl-001"], root / "data" / "artifacts", b) == "pending"
    db.close()


# ------------------------------------------------------- end to end with mocks
def _media(kb_root: pathlib.Path, n: int = 2) -> pathlib.Path:
    d = kb_root / "data" / "media" / "shl"
    d.mkdir(parents=True, exist_ok=True)
    lines = []
    for i in range(1, n + 1):
        _write_wav(d / f"shl-{i:03d}.wav", 5.0 + i, silences=[(2.5, 3.0)])
        old = time.time() - 600
        os.utime(d / f"shl-{i:03d}.wav", (old, old))
        lines.append(f"{i:03d}\tYT{i:03d}\t6\t伤寒论 第{i}集")
    (d / "_playlist.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_budgeted_run_verifies_purges_and_resumes(kb_root):
    media = _media(kb_root, 2)
    eng = MockEngine()
    big_free = lambda _r: 100 * GB
    summ = run_budgeted(["shl"], root=kb_root, engine=eng, free_bytes_fn=big_free,
                        budget=Budget(budget_bytes=40 * GB, min_free_bytes=15 * GB, min_age_s=60),
                        run_id="bt1")
    assert len(summ["batches"]) == 1 and summ["batches"][0]["n_ok"] == 2
    assert {p["video_id"] for p in summ["purged"]} == {"shl-001", "shl-002"}
    assert summ["status_counts"] == {"shl": {"purged": 2}}
    # heavy files gone: source audio, wav parts, checkpoints; light outputs kept
    assert not (media / "shl-001.wav").exists()
    art = kb_root / "data" / "artifacts" / "shl-001"
    assert not list(art.glob("s03_audio/*/audio")) and not list(art.glob("s04_asr/*/parts"))
    # play audio retained for domestic site playback; source copies gone
    play = list((kb_root / "data" / "r2-mirror" / "play").glob("shl-001.*"))
    assert play, "expected retained play/{id}.m4a after purge"
    assert not list((kb_root / "data" / "r2-mirror" / "source").glob("shl-001.*"))
    segs = [json.loads(x) for x in (art / "segments.jsonl").read_text(encoding="utf-8").splitlines()]
    assert segs and all(s["cite"]["t_url"].startswith("/watch/shl-001?t=") for s in segs)
    assert segs[0]["cite"]["youtube_t_url"].startswith("https://www.youtube.com/watch?v=YT001&t=")
    assert segs[0]["cite"]["title"] == "伤寒论 第1集" and segs[0]["cite"]["episode"] == 1
    chaps = json.loads((art / "chapters.json").read_text(encoding="utf-8"))
    assert chaps[0]["cite"]["youtube_id"] == "YT001"
    assert chaps[0]["cite"]["t_url"].startswith("/watch/shl-001?t=")
    asr = json.loads((art / "asr_raw.json").read_text(encoding="utf-8"))
    assert asr["source"]["url"] == "https://www.youtube.com/watch?v=YT001"
    lecture = (art / "lecture.md").read_text(encoding="utf-8")
    assert "/watch/shl-001?t=" in lecture
    # purge recorded in SQLite + media manifest, with the URL as the re-fetch reference
    db = StateDB(kb_root / "data" / "state.sqlite")
    rec = db.get_purge("shl-001")
    assert rec["source_url"] == "https://www.youtube.com/watch?v=YT001" and rec["bytes_freed"] > 0
    assert rec["verify"]["n_segments"] == len(segs)
    assert db.get_video("shl-001").meta["media_purged"] is True
    db.close()
    pj = json.loads((media / "_purged.json").read_text(encoding="utf-8"))
    assert pj["items"]["shl-002"]["youtube_id"] == "YT002"
    assert (media / "_purged_ids.txt").read_text().split() == ["YT001", "YT002"]

    # resume: purged items are neither re-planned nor re-required (no source on disk)
    n = len(eng.calls)
    summ2 = run_budgeted(["shl"], root=kb_root, engine=eng, free_bytes_fn=big_free, run_id="bt2")
    assert summ2["batches"] == [] and len(eng.calls) == n

    # downstream steps can still re-run for a purged item from the kept asr_raw.json
    from tcmkb_ingest.scheduler import run_pipeline
    out = run_pipeline("shl-001", root=kb_root, engine=eng, force=True)
    assert out["steps"]["s03_audio"] == {"skipped": True, "purged": True,
                                         "version_key": out["steps"]["s03_audio"]["version_key"]}
    assert "skipped" not in out["steps"]["s06_clean"] and len(eng.calls) == n


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_budgeted_run_refuses_low_disk_and_keeps_unverified(kb_root):
    media = _media(kb_root, 1)
    summ = run_budgeted(["shl"], root=kb_root, engine=MockEngine(),
                        free_bytes_fn=lambda _r: 10 * GB, run_id="low")
    assert summ["refused"] and "safety margin" in summ["refused"] and summ["batches"] == []
    assert (media / "shl-001.wav").exists()

    # ASR fails -> not verified -> nothing purged, source kept for the retry
    eng = MockEngine(fail_on={"part_000"})
    summ = run_budgeted(["shl"], root=kb_root, engine=eng, free_bytes_fn=lambda _r: 100 * GB,
                        run_id="fail")
    assert summ["batches"][0]["n_failed"] == 1 and summ["purged"] == []
    assert (media / "shl-001.wav").exists()
    db = StateDB(kb_root / "data" / "state.sqlite")
    ok, info = verify_outputs(db, kb_root / "data" / "artifacts", "shl-001")
    assert not ok and "s04_asr not done" in info["error"]
    db.close()
    # retry succeeds and purges
    eng.fail_on.clear()
    summ = run_budgeted(["shl"], root=kb_root, engine=eng, free_bytes_fn=lambda _r: 100 * GB,
                        run_id="retry")
    assert [p["video_id"] for p in summ["purged"]] == ["shl-001"]
    assert not (media / "shl-001.wav").exists()


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_s03_writes_no_full_wav_and_keeps_play_mirror(kb_root):
    _media(kb_root, 1)
    run_budgeted(["shl"], root=kb_root, engine=MockEngine(), free_bytes_fn=lambda _r: 100 * GB,
                 purge=False, run_id="np")
    art = kb_root / "data" / "artifacts" / "shl-001"
    (s03,) = list(art.glob("s03_audio/*"))
    wavs = sorted(p.name for p in (s03 / "audio").iterdir())
    assert wavs == ["part_000.wav", "part_001.wav"]           # split at the silence, no full.wav
    mirror = kb_root / "data" / "r2-mirror"
    # domestic play: 64k m4a landed in mirror; s03 parts are NOT mirrored
    assert (mirror / "play" / "shl-001.m4a").is_file()
    assert not list(mirror.glob("artifacts/**"))
    assert list(art.glob("s02_media/*/*.m4a"))                # play_copy: true
