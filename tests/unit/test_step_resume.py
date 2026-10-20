"""Step resume: done version_key is skipped; config change forces rerun."""
import pathlib
import pytest
from tcmkb_core.ids import version_key, sha256_file
from tcmkb_ingest.state import StateDB
from tcmkb_core.models import VideoManifest

def test_state_resume(tmp_path: pathlib.Path):
    db = StateDB(tmp_path / "state.sqlite")
    m = VideoManifest(
        video_id="zj-demo", series_id="zj", episode=0, title="demo",
        source_path=str(tmp_path / "x.wav"), source_sha256="a" * 64, source_bytes=1,
    )
    # create dummy source for completeness
    (tmp_path / "x.wav").write_bytes(b"RIFF")
    db.upsert_video(m)
    vk = version_key("s04_asr", "1", {"from_cache": True}, upstream_hash="u1")
    db.ensure_step("zj-demo", "s04_asr", vk)
    assert db.claim("zj-demo", "s04_asr", vk, "w1")
    db.mark_done("zj-demo", "s04_asr", vk, str(tmp_path), "hash1", {"n": 1})
    assert db.find_done("zj-demo", "s04_asr", vk) is not None
    # different version_key → not done
    vk2 = version_key("s04_asr", "1", {"from_cache": False}, upstream_hash="u1")
    assert db.find_done("zj-demo", "s04_asr", vk2) is None
    # active version recorded
    m2 = db.get_video("zj-demo")
    assert m2.active_versions["s04_asr"] == vk
    db.close()

def test_sha256_file(tmp_path: pathlib.Path):
    p = tmp_path / "a.bin"
    p.write_bytes(b"hello")
    assert len(sha256_file(p)) == 64
