"""Site cite links + play URL construction (no real audio binaries committed)."""
from __future__ import annotations
import json, os, pathlib

import pytest

from tcmkb_core.play import (
    construct_play_url, play_audio_key, site_watch_url, verify_media_token, youtube_t_url,
)
from tcmkb_ingest.backfill_cites import backfill_video
from tcmkb_ingest.sources import cite


def test_site_watch_and_youtube_backup():
    assert site_watch_url("shl-003", 125.9) == "/watch/shl-003?t=125"
    assert site_watch_url("shl-003", 0, end=10.1) == "/watch/shl-003?t=0&end=10"
    assert site_watch_url("shl-003", 1, base="https://kb.example.com") == \
        "https://kb.example.com/watch/shl-003?t=1"
    assert youtube_t_url("AbC", 61.2) == "https://www.youtube.com/watch?v=AbC&t=61s"
    assert site_watch_url(None, 1) is None


def test_cite_primary_is_site():
    c = cite({"video_id": "shl-006", "youtube_id": "9zCCln-3KaE",
              "url": "https://www.youtube.com/watch?v=9zCCln-3KaE",
              "title": "T", "series_id": "shl", "episode": 6}, 591.84, 592.08)
    assert c["t_url"] == "/watch/shl-006?t=591"
    assert c["youtube_t_url"].endswith("&t=591s")
    assert c["url"].startswith("https://www.youtube.com/")
    assert c["video_id"] == "shl-006"


def test_construct_play_url_local(tmp_path, monkeypatch):
    monkeypatch.delenv("R2_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("R2_ACCESS_KEY_ID", raising=False)
    mirror = tmp_path / "data" / "r2-mirror"
    key = play_audio_key("demo-001")
    (mirror / key).parent.mkdir(parents=True)
    (mirror / key).write_bytes(b"fake-m4a-not-a-real-file")  # tiny stub, not a media binary asset
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "pipeline.yaml").write_text("r2_mirror: data/r2-mirror\n", encoding="utf-8")
    (tmp_path / "lexicon").mkdir()
    (tmp_path / "packages").mkdir()
    meta = construct_play_url("demo-001", root=tmp_path)
    assert meta["mode"] == "local"
    assert meta["key"] == "play/demo-001.m4a"
    assert meta["url"] == "/api/media/demo-001"
    assert meta["path"] and meta["path"].endswith("play/demo-001.m4a")


def test_construct_play_url_r2_stub(monkeypatch):
    monkeypatch.setenv("R2_ACCOUNT_ID", "acc")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "sekrit")
    monkeypatch.setenv("R2_BUCKET", "tcm-media")
    monkeypatch.setenv("R2_PUBLIC_BASE", "https://media.example.com")
    meta = construct_play_url("shl-001", expires_s=3600)
    assert meta["mode"] == "r2-presign-stub"
    assert meta["key"] == "play/shl-001.m4a"
    assert meta["url"].startswith("https://media.example.com/play/shl-001.m4a?")
    assert "token=" in meta["url"] and "exp=" in meta["url"]
    # token verifies
    from urllib.parse import parse_qs, urlparse
    q = parse_qs(urlparse(meta["url"]).query)
    assert verify_media_token("shl-001", q["exp"][0], q["token"][0])
    assert not verify_media_token("shl-001", q["exp"][0], "deadbeef")


def test_backfill_cites_rewrites_without_asr(tmp_path):
    """Old YouTube t_url → site; asr_raw untouched."""
    root = tmp_path
    for d in ("configs", "lexicon", "packages", "data/artifacts/shl-099/s06_clean/vk1",
              "data/artifacts/shl-099/s08_chapter/vk2"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "configs" / "pipeline.yaml").write_text(
        "state_db: data/state.sqlite\nartifacts_dir: data/artifacts\nr2_mirror: data/r2-mirror\n",
        encoding="utf-8")
    from tcmkb_ingest.state import StateDB
    from tcmkb_core.models import VideoManifest
    db = StateDB(root / "data" / "state.sqlite")
    m = VideoManifest(
        video_id="shl-099", series_id="shl", episode=99, title="旧集",
        source_path="/missing.m4a", source_sha256="0" * 64,
        meta={"source": {"video_id": "shl-099", "youtube_id": "OLDID",
                         "url": "https://www.youtube.com/watch?v=OLDID",
                         "title": "旧集", "series_id": "shl", "episode": 99}},
        active_versions={"s06_clean": "vk1", "s08_chapter": "vk2"},
    )
    db.upsert_video(m)
    db.close()

    old_yt = "https://www.youtube.com/watch?v=OLDID&t=10s"
    segs = [
        {"video_id": "shl-099", "seq": 0, "start_s": 10.5, "end_s": 12.0, "text": "甲",
         "text_raw": "甲", "edits": [], "cite": {"youtube_id": "OLDID", "t_url": old_yt,
                                                  "url": "https://www.youtube.com/watch?v=OLDID",
                                                  "start_s": 10.5, "end_s": 12.0}},
    ]
    chaps = [{"seq": 1, "title": "章", "start_s": 10.5, "end_s": 12.0, "summary": "",
              "key_points": [], "seg_from": 0, "seg_to": 0,
              "cite": {"youtube_id": "OLDID", "t_url": old_yt}}]
    seg_p = root / "data/artifacts/shl-099/s06_clean/vk1/segments.jsonl"
    seg_p.write_text(json.dumps(segs[0], ensure_ascii=False) + "\n", encoding="utf-8")
    (root / "data/artifacts/shl-099/segments.jsonl").write_text(seg_p.read_text(encoding="utf-8"),
                                                                 encoding="utf-8")
    chap_p = root / "data/artifacts/shl-099/s08_chapter/vk2/chapters.json"
    chap_p.write_text(json.dumps(chaps, ensure_ascii=False), encoding="utf-8")
    asr_dir = root / "data/artifacts/shl-099/s04_asr/vk0"
    asr_dir.mkdir(parents=True)
    asr_p = asr_dir / "asr_raw.json"
    asr_body = {"text": "甲", "tokens": [{"t": "甲", "s": 10.5, "e": 11.0}], "source": {"youtube_id": "OLDID"}}
    asr_p.write_text(json.dumps(asr_body), encoding="utf-8")
    before = asr_p.read_bytes()

    info = backfill_video(root, "shl-099")
    assert info["n_segments_rewritten"] >= 1
    new_seg = json.loads((seg_p.read_text(encoding="utf-8").splitlines()[0]))
    assert new_seg["cite"]["t_url"] == "/watch/shl-099?t=10"
    assert new_seg["cite"]["youtube_t_url"] == old_yt
    new_ch = json.loads(chap_p.read_text(encoding="utf-8"))
    assert new_ch[0]["cite"]["t_url"] == "/watch/shl-099?t=10"
    lecture = (root / "data/artifacts/shl-099/s08_chapter/vk2/lecture.md").read_text(encoding="utf-8")
    assert "/watch/shl-099?t=10" in lecture
    assert asr_p.read_bytes() == before  # ASR untouched
