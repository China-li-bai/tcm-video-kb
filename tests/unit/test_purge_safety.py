"""Regression: purge must only delete an item's own heavy media, never repo files.

Bug (2026-10-22): after a budgeted shl batch, the git-tracked eval/asr/out/ was gone.
Purge now resolves every candidate against a per-item allowlist and refuses anything
git-tracked, outside data/media/<series>/<id>.*, data/artifacts/<id>/{s03_audio/*/audio,
s04_asr/*/parts, s02_media/*/<media>, s01_upload/*/source.*} or the r2 mirror's own keys.
"""
import json, pathlib, shutil, subprocess
import pytest
from tcmkb_core.models import VideoManifest
from tcmkb_ingest.planner import UnsafePurgePath, check_purge_path, heavy_paths, purge_item, purge_roots
from tcmkb_ingest.state import StateDB

HAS_GIT = shutil.which("git") is not None


def _repo(tmp_path: pathlib.Path, r2_mirror: str = "data/r2-mirror") -> pathlib.Path:
    root = tmp_path / "kb"
    (root / "configs").mkdir(parents=True)
    (root / "configs" / "pipeline.yaml").write_text(f"r2_mirror: {r2_mirror}\n", encoding="utf-8")
    out = root / "eval" / "asr" / "out"
    (out / "dist_cap100" / "hotwords").mkdir(parents=True)
    (out / "score_v0_1.json").write_text("{}", encoding="utf-8")
    (out / "dist_cap100" / "hotwords" / "shl.txt").write_text("桂枝汤\n", encoding="utf-8")
    (out / "shl-001.lex01.json").write_text("{}", encoding="utf-8")   # id-prefixed tracked file
    if HAS_GIT:
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "add", "eval", "configs"], check=True)
    # heavy media of shl-001
    media = root / "data" / "media" / "shl"
    media.mkdir(parents=True)
    (media / "shl-001.m4a").write_bytes(b"x" * 1000)
    (media / "shl-0010.m4a").write_bytes(b"other episode")          # prefix lookalike, must survive
    (media / "_purged.json").write_text("{}", encoding="utf-8")
    a = root / "data" / "artifacts" / "shl-001"
    (a / "s03_audio" / "vk1" / "audio").mkdir(parents=True)
    (a / "s03_audio" / "vk1" / "audio" / "part_000.wav").write_bytes(b"w" * 500)
    (a / "s03_audio" / "vk1" / "audio.json").write_text("{}", encoding="utf-8")
    (a / "s04_asr" / "vk2" / "parts").mkdir(parents=True)
    (a / "s04_asr" / "vk2" / "parts" / "p0.json").write_text("{}", encoding="utf-8")
    (a / "s04_asr" / "vk2" / "asr_raw.json").write_text('{"tokens":[1]}', encoding="utf-8")
    (a / "s07_flag" / "vk3").mkdir(parents=True)
    (a / "s07_flag" / "vk3" / "segments.jsonl").write_text("{}\n", encoding="utf-8")
    return root


def _register(root: pathlib.Path, source_path: str, video_id: str = "shl-001") -> StateDB:
    db = StateDB(root / "data" / "state.sqlite")
    db.upsert_video(VideoManifest(video_id=video_id, series_id="shl", episode=1, title="t",
                                  source_path=source_path, source_sha256="a" * 64, source_bytes=1,
                                  meta={"source": {"youtube_id": "YT1", "url": "https://youtu.be/YT1"}}))
    return db


def _tracked_intact(root: pathlib.Path) -> None:
    out = root / "eval" / "asr" / "out"
    assert (out / "score_v0_1.json").is_file()
    assert (out / "dist_cap100" / "hotwords" / "shl.txt").is_file()
    assert (out / "shl-001.lex01.json").is_file()
    assert (root / "configs" / "pipeline.yaml").is_file()


def test_purge_deletes_only_own_heavy_media(tmp_path):
    root = _repo(tmp_path)
    db = _register(root, str(root / "data" / "media" / "shl" / "shl-001.m4a"))
    rec = purge_item(root, db, root / "data" / "artifacts", None, "shl-001", {"ok": True})
    a = root / "data" / "artifacts" / "shl-001"
    assert not (root / "data" / "media" / "shl" / "shl-001.m4a").exists()
    assert not (a / "s03_audio" / "vk1" / "audio").exists()
    assert not (a / "s04_asr" / "vk2" / "parts").exists()
    # lightweight outputs, other episodes, manifests and repo files survive
    assert (a / "s04_asr" / "vk2" / "asr_raw.json").is_file()
    assert (a / "s03_audio" / "vk1" / "audio.json").is_file()
    assert (a / "s07_flag" / "vk3" / "segments.jsonl").is_file()
    assert (root / "data" / "media" / "shl" / "shl-0010.m4a").is_file()
    _tracked_intact(root)
    assert rec["refused"] == [] and len(rec["files"]) == 3


@pytest.mark.parametrize("bad_source", ["eval/asr/out", "eval/asr/out/score_v0_1.json", "eval", "."])
def test_purge_refuses_source_path_outside_media(tmp_path, bad_source):
    root = _repo(tmp_path)
    db = _register(root, str(root / bad_source))
    rec = purge_item(root, db, root / "data" / "artifacts", None, "shl-001", {"ok": True})
    _tracked_intact(root)
    assert any(r["path"].endswith(bad_source.strip(".")) or r["path"] == str(root / bad_source)
               for r in rec["refused"])
    assert not (root / "data" / "artifacts" / "shl-001" / "s04_asr" / "vk2" / "parts").exists()


def test_purge_refuses_misconfigured_mirror_and_bad_ids(tmp_path):
    # r2_mirror pointing into the repo's eval tree must not let `source/<id>.*`-style globs hit it
    root = _repo(tmp_path, r2_mirror="eval/asr")
    (root / "eval" / "asr" / "out" / "source").mkdir()
    db = _register(root, str(root / "data" / "media" / "shl" / "shl-001.m4a"))
    purge_item(root, db, root / "data" / "artifacts", None, "shl-001", {"ok": True})
    _tracked_intact(root)
    roots = purge_roots(root, root / "data" / "artifacts", "shl-001", "shl")
    with pytest.raises(UnsafePurgePath):
        check_purge_path(root, root / "eval" / "asr" / "out", "shl-001", roots)
    with pytest.raises(UnsafePurgePath):
        check_purge_path(root, root, "shl-001", roots)
    for bad_id in ("", "..", "../eval", "shl/../../eval", "*"):
        with pytest.raises(UnsafePurgePath):
            heavy_paths(root, root / "data" / "artifacts", bad_id, None)


@pytest.mark.skipif(not HAS_GIT, reason="git not installed")
def test_purge_refuses_git_tracked_media_name(tmp_path):
    root = _repo(tmp_path)
    tracked = root / "data" / "media" / "shl" / "shl-001.m4a"
    subprocess.run(["git", "-C", str(root), "add", "-f", str(tracked)], check=True)
    roots = purge_roots(root, root / "data" / "artifacts", "shl-001", "shl")
    with pytest.raises(UnsafePurgePath, match="git-tracked"):
        check_purge_path(root, tracked, "shl-001", roots)
    assert tracked not in heavy_paths(root, root / "data" / "artifacts", "shl-001", str(tracked))
