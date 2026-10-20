"""s03 split / s04 live path / batch — with a mocked ASR engine (no FunASR needed)."""
from __future__ import annotations
import json, math, pathlib, shutil, struct, wave
import pytest

from tcmkb_core.config import repo_root
from tcmkb_ingest.asr_engine import read_hotwords, tokens_from_funasr_result
from tcmkb_ingest.steps.s03_audio import parse_silencedetect, plan_cuts
from tcmkb_ingest.batch import items_from_dir, items_from_manifest, run_batch
from tcmkb_ingest.state import StateDB

HAS_FFMPEG = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


# ------------------------------------------------------------------ pure units
def test_tokens_from_raw_text_exact_alignment():
    r0 = {"text": "针扎到足三里，Ok好。", "raw_text": "针 扎 到 足 三 里 ok 好",
          "timestamp": [[0, 100], [100, 200], [200, 300], [300, 400], [400, 500],
                        [500, 600], [600, 800], [800, 900]]}
    toks = tokens_from_funasr_result(r0)
    assert [t["t"] for t in toks] == ["针", "扎", "到", "足", "三", "里", "ok", "好"]
    assert toks[6] == {"t": "ok", "s": 0.6, "e": 0.8}


def test_tokens_fallback_when_raw_text_mismatch():
    r0 = {"text": "足三里。", "raw_text": "足 三", "timestamp": [[0, 10], [10, 20], [20, 30]]}
    toks = tokens_from_funasr_result(r0)
    assert "".join(t["t"] for t in toks) == "足三里"
    assert toks[-1]["e"] == pytest.approx(0.03)
    assert tokens_from_funasr_result({"text": "x", "timestamp": []}) == []


def test_read_hotwords(tmp_path):
    p = tmp_path / "zj.txt"
    p.write_text("足三里\n# comment\n\n梁丘 10\n足三里\n伏兔\n", encoding="utf-8")
    assert read_hotwords(p) == ["足三里", "梁丘", "伏兔"]
    assert read_hotwords(p, limit=2) == ["足三里", "梁丘"]
    assert read_hotwords(tmp_path / "missing.txt") == []


def test_parse_silencedetect():
    err = ("[silencedetect @ 0x1] silence_start: 10.5\n"
           "[silencedetect @ 0x1] silence_end: 11.5 | silence_duration: 1\n"
           "[silencedetect @ 0x1] silence_start: 20\n")  # unterminated -> ignored
    assert parse_silencedetect(err) == [(10.5, 11.5)]


def test_plan_cuts_prefers_longest_silence_and_bounds_parts():
    sil = [(1090.0, 1090.5), (1150.0, 1152.0), (1199.0, 1199.2), (2300.0, 2301.0)]
    cuts = plan_cuts(3000.0, sil, max_part_s=1200, search_s=120)
    assert cuts[0] == pytest.approx(1151.0)          # longest silence in (1080, 1200]
    bounds = [0.0, *cuts, 3000.0]
    assert all(b - a <= 1200 + 1e-6 for a, b in zip(bounds, bounds[1:]))
    # no silences -> hard cuts
    assert plan_cuts(2500.0, [], 1200) == [1200.0, 2400.0]
    assert plan_cuts(600.0, [], 1200) == []


def test_items_from_manifest_csv_and_yaml(tmp_path):
    (tmp_path / "a.wav").write_bytes(b"x")
    csvp = tmp_path / "m.csv"
    csvp.write_text("# comment\nvideo_id,file,series,title\nzj-001,a.wav,zj,T\n"
                    ",/abs/shl 03.mp4,shl,\n", encoding="utf-8")
    items = items_from_manifest(csvp)
    assert items[0].video_id == "zj-001" and items[0].file == str(tmp_path / "a.wav")
    assert items[1].video_id == "shl-003" and items[1].episode == 3
    y = tmp_path / "m.yaml"
    y.write_text("series: nj\nvideos:\n  - {file: /x/第12讲.mp4}\n  - {file: /x/intro.mp4, video_id: nj-intro}\n",
                 encoding="utf-8")
    yi = items_from_manifest(y)
    assert [i.video_id for i in yi] == ["nj-012", "nj-intro"]
    dup = tmp_path / "d.csv"
    dup.write_text("file,series,video_id\n/a.mp4,zj,zj-1\n/b.mp4,zj,zj-1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        items_from_manifest(dup)


def test_items_from_dir_id_schemes(tmp_path):
    for n in ("针灸 01.mp4", "针灸 02.mp4", "notes.txt"):
        (tmp_path / n).write_bytes(b"x")
    items = items_from_dir(tmp_path, "zj")
    assert [i.video_id for i in items] == ["zj-001", "zj-002"]
    (tmp_path / "extra lecture.mp4").write_bytes(b"x")    # no number -> auto falls back to stem
    items = items_from_dir(tmp_path, "zj")
    ids = {i.video_id for i in items}
    assert "zj-extra-lecture" in ids and len(ids) == 3
    with pytest.raises(ValueError):
        items_from_dir(tmp_path, "zj", id_scheme="episode")


# ------------------------------------------------------- pipeline with mocks
class MockEngine:
    """Stands in for FunAsrEngine: one instance shared by the batch."""
    name = "mock-seaco"
    model_rev = "mock"
    load_sec = 0.0

    def __init__(self, fail_on: set[str] | None = None):
        self._m = object()
        self.calls: list[tuple[str, int]] = []
        self.fail_on = fail_on or set()

    def transcribe(self, wav, hotwords):
        wav = pathlib.Path(wav)
        self.calls.append((str(wav), len(hotwords)))
        if any(f in str(wav) for f in self.fail_on):
            raise RuntimeError(f"boom on {wav.name}")
        with wave.open(str(wav), "rb") as w:
            dur = w.getnframes() / w.getframerate()
        # one 4-char sentence per second, part-relative timestamps
        text, toks = "", []
        for k in range(int(dur)):
            chars = "足三里好"
            for j, c in enumerate(chars):
                s = k + j * 0.2
                toks.append({"t": c, "s": round(s, 3), "e": round(s + 0.2, 3)})
            text += chars + "。"
        return {"text": text, "tokens": toks, "proc_sec": dur * 0.01}


def _write_wav(path: pathlib.Path, seconds: float, silences: list[tuple[float, float]] = ()):
    sr = 16000
    frames = bytearray()
    for i in range(int(seconds * sr)):
        t = i / sr
        quiet = any(a <= t < b for a, b in silences)
        v = 0 if quiet else int(8000 * math.sin(2 * math.pi * 440 * t))
        frames += struct.pack("<h", v)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(bytes(frames))


@pytest.fixture
def kb_root(tmp_path, monkeypatch):
    """Minimal repo root: configs + lexicon/dist (hotwords, corrections) in tmp."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TCMKB_LLM_API_KEY", raising=False)
    real = repo_root()
    root = tmp_path / "kb"
    (root / "packages").mkdir(parents=True)
    shutil.copytree(real / "configs", root / "configs")
    dist = root / "lexicon" / "dist"
    (dist / "hotwords").mkdir(parents=True)
    (dist / "hotwords" / "zj.txt").write_text("足三里\n梁丘\n", encoding="utf-8")
    (dist / "hotwords" / "global.txt").write_text("倪海厦\n", encoding="utf-8")
    (dist / "corrections.json").write_text(json.dumps({
        "rules": [{"id": "t#1", "from": "竹山里", "to": "足三里"}], "protected_surfaces": ["足三里"]},
        ensure_ascii=False), encoding="utf-8")
    (dist / "build_info.json").write_text(json.dumps({"lexicon_ver": "0.0.0#test"}), encoding="utf-8")
    pipe = root / "configs" / "pipeline.yaml"
    txt = pipe.read_text(encoding="utf-8").replace("max_part_s: 1200", "max_part_s: 4") \
        .replace("split_search_s: 120", "split_search_s: 2")
    pipe.write_text(txt, encoding="utf-8")
    return root


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_batch_shared_engine_split_resume_and_failure(kb_root, tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    _write_wav(media / "zj 01.wav", 10.0, silences=[(3.2, 3.8), (7.0, 7.6)])
    _write_wav(media / "zj 02.wav", 3.0)
    (media / "zj 03.wav").write_bytes(b"RIFF-not-really-a-wav")      # corrupt -> fails, batch continues
    items = items_from_dir(media, "zj")
    assert [i.video_id for i in items] == ["zj-001", "zj-002", "zj-003"]

    eng = MockEngine()
    rep = run_batch(items, root=kb_root, engine=eng, run_id="t1")
    by = {r["video_id"]: r for r in rep["items"]}
    assert by["zj-001"]["status"] == "ok" and by["zj-002"]["status"] == "ok"
    assert by["zj-003"]["status"] == "failed" and by["zj-003"]["error"]
    assert rep["n_failed"] == 1 and rep["n_ok"] == 2
    assert (kb_root / "data" / "batch" / "t1.json").exists()
    assert (kb_root / "data" / "batch" / "t1.csv").exists()

    # long audio was split at silences; tokens carry part offsets and stay monotonic
    art = kb_root / "data" / "artifacts" / "zj-001"
    asr = json.loads((art / "asr_raw.json").read_text(encoding="utf-8"))
    assert asr["from_cache"] is False and asr["hotwords"] == ["足三里", "梁丘"]
    offs = [p["offset_s"] for p in asr["parts"]]
    assert len(offs) >= 3 and offs[0] == 0.0
    assert 3.2 <= offs[1] <= 3.8                     # cut inside the first silence
    starts = [t["s"] for t in asr["tokens"]]
    assert starts == sorted(starts) and starts[-1] > 7.0
    m = asr["metrics"]
    assert m["n_parts"] == len(offs) and m["audio_sec"] == pytest.approx(10.0, abs=0.05)
    assert m["rtf"] == pytest.approx(0.01, rel=0.05)
    assert by["zj-001"]["rtf"] == pytest.approx(0.01, rel=0.05)
    assert by["zj-001"]["n_chapters"] >= 1 and by["zj-001"]["n_segments"] >= 1
    assert all(n == 2 for _, n in eng.calls)        # series hotwords passed through
    n_calls = len(eng.calls)

    db = StateDB(kb_root / "data" / "state.sqlite")
    failed = db.failed_steps("zj-003")
    db.close()
    assert failed and failed[-1]["error"]

    # rerun: done version_keys are skipped (no ASR calls); failure is retried and recorded again
    rep2 = run_batch(items, root=kb_root, engine=eng, run_id="t2")
    by2 = {r["video_id"]: r for r in rep2["items"]}
    assert len(eng.calls) == n_calls
    assert by2["zj-001"]["asr_reused"] is True
    assert "s04_asr" in by2["zj-001"]["steps_skipped"] and not by2["zj-001"]["steps_run"]
    assert by2["zj-003"]["status"] == "failed"


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg not installed")
def test_s04_part_checkpoint_resume(kb_root, tmp_path):
    src = tmp_path / "zj 07.wav"
    _write_wav(src, 9.0, silences=[(3.5, 3.9), (6.5, 6.9)])
    items = items_from_dir(tmp_path, "zj", pattern="*.wav", recursive=False)
    eng = MockEngine(fail_on={"part_001"})
    rep = run_batch(items, root=kb_root, engine=eng, run_id="p1")
    assert rep["items"][0]["status"] == "failed" and rep["items"][0]["failed_step"] == "s04_asr"
    assert [pathlib.Path(c).name for c, _ in eng.calls] == ["part_000.wav", "part_001.wav"]
    eng.fail_on.clear()
    eng.calls.clear()
    rep = run_batch(items, root=kb_root, engine=eng, run_id="p2")
    assert rep["items"][0]["status"] == "ok"
    # part_000 came from its checkpoint; only the remaining parts were transcribed
    assert "part_000.wav" not in [pathlib.Path(c).name for c, _ in eng.calls]
    asr = json.loads((kb_root / "data/artifacts/zj-007/asr_raw.json").read_text(encoding="utf-8"))
    assert asr["metrics"]["parts_reused"] == 1


def test_s04_live_requires_funasr_message(monkeypatch):
    """Without funasr, the engine fails with an actionable message (not a bare ImportError)."""
    import builtins
    from tcmkb_ingest.asr_engine import FunAsrEngine
    real_import = builtins.__import__

    def fake(name, *a, **k):
        if name == "funasr":
            raise ImportError("no funasr")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(RuntimeError, match="uv sync --extra asr"):
        FunAsrEngine({}).load()
