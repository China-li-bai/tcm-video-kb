"""Knowledge layer (s09): schema validation, citations, chapter merge, KP dedupe, end-to-end build."""
from __future__ import annotations
import csv, json, pathlib

import pytest
import yaml
from pydantic import ValidationError

from tcmkb_core.knowledge import (
    Annotation, KChapter, KCitation, KnowledgePoint, json_schemas, t_url, youtube_t_url,
)
from tcmkb_ingest.knowledge.build import KnowledgeBuildError, build, citation
from tcmkb_ingest.knowledge.chunk import make_windows
from tcmkb_ingest.knowledge.episode import Episode
from tcmkb_ingest.knowledge.export import build_index

YT = "AbCdEfGhIjK"
TEXTS = [
    "今天我们讲伤寒论太阳篇",
    "太阳中风的人会汗出恶风",
    "桂枝汤主之这个是第十二条",
    "桂枝要三钱白芍也是三钱",
    "吃完以后要喝一点热稀饭",
    "太阳中风一定有汗出",
    "第十三条头痛发热汗出恶风",
    "桂枝汤的主症就是汗出恶风",
    "如果脖子僵硬可以扎风池",
    "下针以后风池这边就松开",
    "这是大陷胸汤其实是大青龙",
    "今天就讲到这里谢谢大家",
]


def _cite(i: int) -> dict:
    return {"youtube_id": YT, "series_id": "tv", "episode": 1, "title": "测试讲座 第1集"}


def _segments() -> list[dict]:
    return [{"seq": i, "start_s": i * 100.0 + 0.4, "end_s": i * 100.0 + 90.0, "text": t, "cite": _cite(i)}
            for i, t in enumerate(TEXTS)]


LEX = [
    {"id": "formula.gui_zhi_tang", "term": "桂枝汤", "category": "formula"},
    {"id": "formula.da_xian_xiong_tang", "term": "大陷胸汤", "category": "formula"},
    {"id": "formula.da_qing_long_tang", "term": "大青龙汤", "category": "formula"},
    {"id": "herb.gui_zhi", "term": "桂枝", "category": "herb"},
    {"id": "symptom.han_chu", "term": "汗出", "category": "symptom"},
    {"id": "symptom.e_feng", "term": "恶风", "category": "symptom"},
    {"id": "syndrome.tai_yang_zhong_feng", "term": "太阳中风", "category": "syndrome"},
    {"id": "acupoint.gb20", "term": "风池", "category": "acupoint"},
    {"id": "six_channel.taiyang", "term": "太阳", "category": "six_channel"},
    {"id": "clause.shl.012", "term": "太阳中风阳浮而阴弱", "category": "clause",
     "attrs": {"no": 12, "entities": ["six_channel.taiyang"]}},
    {"id": "clause.shl.013", "term": "太阳病头痛发热汗出恶风", "category": "clause",
     "attrs": {"no": 13, "entities": ["six_channel.taiyang"]}},
]

CFG = {"window_s": 600, "max_mentions_per_entity": 30, "kp_dedupe_ratio": 0.82,
       "aliases": {"白芍": "herb.gui_zhi"},  # nonsense mapping is fine for a fake lexicon
       "context_required": {"acupoint": ["针", "扎"]}}


def _ann(window: str, a: int, b: int, **kw) -> dict:
    return {"video_id": "tv-001", "window": window, "seg_from": a, "seg_to": b, **kw}


W0 = _ann("w00", 0, 5,
          chapters=[{"key": "c01", "title": "开场", "start_seq": 0, "summary": "介绍太阳篇。"},
                    {"key": "c02", "title": "第12条 桂枝汤", "start_seq": 1, "summary": "太阳中风用桂枝汤。",
                     "clauses": [12], "topics": ["formula.gui_zhi_tang"]},
                    {"key": "c02.s1", "parent": "c02", "title": "剂量", "start_seq": 3}],
          entities=[{"id": "herb.gui_zhi", "seq": 3, "surface": "桂枝", "dosage": "三钱"}],
          kps=[{"type": "clause_interpretation", "s": "太阳中风有汗出、恶风，用桂枝汤。", "seq": [1, 2],
                "q": "桂枝汤主之", "ents": ["formula.gui_zhi_tang", "clause.shl.012"], "conf": 0.9},
               {"type": "formula_composition", "s": "桂枝与白芍各三钱，等量。", "seq": [3, 3],
                "q": "桂枝要三钱", "ents": ["herb.gui_zhi"], "conf": 0.8},
               {"type": "clinical_tip", "s": "服桂枝汤后喝一点热稀饭助汗。", "seq": [4, 4],
                "q": "喝一点热稀饭", "conf": 0.7}])
W1 = _ann("w01", 5, 11,
          chapters=[{"key": "c02", "title": "第12条 桂枝汤", "start_seq": 1, "clauses": [13]},
                    {"key": "c03", "title": "风池", "start_seq": 8, "summary": "针风池。"}],
          entities=[{"id": "formula.da_xian_xiong_tang", "seq": 10, "surface": "大陷胸汤", "reject": True},
                    {"id": "formula.da_qing_long_tang", "seq": 10, "surface": "大陷胸汤", "corrected": "大青龙汤"},
                    {"id": "new.concept.微汗", "seq": 5, "surface": "有汗"}],
          kps=[{"type": "clause_interpretation", "s": "太阳中风有汗出与恶风，桂枝汤主之。", "seq": [5, 7],
                "q": "汗出恶风", "ents": ["symptom.han_chu"], "conf": 0.95},
               {"type": "acupoint_usage", "s": "脖子僵硬可扎风池。", "seq": [8, 9], "q": "可以扎风池",
                "ents": ["acupoint.gb20"], "conf": 0.8}])


@pytest.fixture()
def root(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "knowledge.yaml").write_text(yaml.safe_dump(CFG, allow_unicode=True), "utf-8")
    (tmp_path / "lexicon" / "dist").mkdir(parents=True)
    (tmp_path / "lexicon" / "dist" / "lexicon.jsonl").write_text(
        "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in LEX), "utf-8")
    a = tmp_path / "data" / "artifacts" / "tv-001"
    a.mkdir(parents=True)
    (a / "segments.jsonl").write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in _segments()),
                                     "utf-8")
    ad = tmp_path / "data" / "knowledge" / "tv-001" / "annotations"
    ad.mkdir(parents=True)
    for w in (W0, W1):
        (ad / f"{w['window']}.yaml").write_text(yaml.safe_dump(w, allow_unicode=True, sort_keys=False), "utf-8")
    return tmp_path


def _jsonl(p: pathlib.Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text("utf-8").splitlines() if x.strip()]


# ---------------------------------------------------------------- schema
def _cit(start=12.7, **kw) -> dict:
    d = {"video_id": "tv-001", "youtube_id": YT, "url": t_url("tv-001", start),
         "youtube_t_url": youtube_t_url(YT, start), "series": "tv", "episode": 1, "title": "t",
         "start_s": start, "end_s": start + 5}
    d.update(kw)
    return d


def _kp(**kw) -> dict:
    d = {"kp_id": "tv-001.kp0001", "video_id": "tv-001", "type": "clinical_tip", "statement": "服药后喝热稀饭。",
         "entity_ids": [], "chapter_id": "tv-001.c01", "evidence_quote": "喝一点热稀饭", "seg_from": 4,
         "seg_to": 4, "start_s": 12.7, "end_s": 17.7, "citation": _cit(), "confidence": 0.7}
    d.update(kw)
    return d


def test_t_url_floors_seconds():
    assert t_url("tv-001", 12.99) == "/watch/tv-001?t=12"
    assert t_url("tv-001", 0) == "/watch/tv-001?t=0"
    assert youtube_t_url(YT, 12.99) == f"https://www.youtube.com/watch?v={YT}&t=12s"


def test_citation_url_must_match_start():
    KCitation(**_cit())
    with pytest.raises(ValidationError):
        KCitation(**_cit(url=t_url("tv-001", 99)))


def test_kp_quote_and_statement_limits():
    KnowledgePoint(**_kp())
    with pytest.raises(ValidationError):
        KnowledgePoint(**_kp(evidence_quote="长" * 41))
    with pytest.raises(ValidationError):
        KnowledgePoint(**_kp(evidence_quote=""))
    with pytest.raises(ValidationError):
        KnowledgePoint(**_kp(statement="短"))
    with pytest.raises(ValidationError):
        KnowledgePoint(**_kp(confidence=1.5))
    with pytest.raises(ValidationError):
        KnowledgePoint(**_kp(type="not_a_type"))
    with pytest.raises(ValidationError):
        KnowledgePoint(**_kp(extra_field=1))


def test_section_requires_parent():
    base = dict(chapter_id="tv-001.c01.s1", video_id="tv-001", level=2, seq=1, title="x", summary="",
                start_s=0.4, end_s=90.0, seg_from=0, seg_to=0, citation=_cit(start=0.4))
    with pytest.raises(ValidationError):
        KChapter(**base, parent_id=None)
    KChapter(**base, parent_id="tv-001.c01")


def test_annotation_seq_range_validated():
    with pytest.raises(ValidationError):
        Annotation(**_ann("w00", 0, 5, kps=[{"type": "clinical_tip", "s": "服药后喝热稀饭。", "seq": [4, 2],
                                             "q": "喝", "conf": 0.5}]))


def test_json_schemas_export():
    s = json_schemas()
    assert {"KnowledgePoint", "KChapter", "KEntity", "Annotation"} <= set(s)


# ---------------------------------------------------------------- citation / windows
def test_citation_rounds_before_url():
    ep = Episode("tv-001", "tv", 1, "t", YT, 1200.0, _segments())
    c = citation(ep, 4052.996, 4060.0)
    assert c.start_s == 4053.0 and c.url == "/watch/tv-001?t=4053"
    assert c.youtube_t_url.endswith("&t=4053s")


def test_make_windows_cover_and_fold_tail():
    segs = _segments()
    ws = make_windows(segs, window_s=500, min_tail_s=250)
    assert ws[0].seg_from == 0 and ws[-1].seg_to == 11
    assert all(b.seg_from == a.seg_to + 1 for a, b in zip(ws, ws[1:]))
    assert len(ws) == 2  # tail of 200s folded into the previous window


# ---------------------------------------------------------------- end-to-end build
def test_build_end_to_end(root: pathlib.Path):
    rep = build(root, "tv-001", strict=True)
    assert rep["errors"] == []
    kdir = root / "data" / "knowledge" / "tv-001"
    chapters = json.loads((kdir / "chapters.json").read_text("utf-8"))
    ids = [c["chapter_id"] for c in chapters]
    assert ids == ["tv-001.c01", "tv-001.c02", "tv-001.c02.s1", "tv-001.c03"]
    c02 = chapters[1]
    # merged across windows: clauses from both, summary kept, ends where c03 starts
    assert c02["clause_refs"] == ["clause.shl.012", "clause.shl.013"]
    assert c02["summary"] == "太阳中风用桂枝汤。"
    assert (c02["seg_from"], c02["seg_to"]) == (1, 7)
    assert c02["six_channel"] == ["six_channel.taiyang"]
    assert chapters[2]["parent_id"] == "tv-001.c02" and chapters[2]["seg_to"] == 7
    assert c02["citation"]["url"] == t_url("tv-001", 100.4)
    assert c02["citation"]["video_id"] == "tv-001"

    kps = _jsonl(kdir / "knowledge_points.jsonl")
    # the two near-identical clause_interpretation KPs in c02 merge; higher confidence wins
    ci = [k for k in kps if k["type"] == "clause_interpretation"]
    assert len(ci) == 1 and ci[0]["confidence"] == 0.95 and ci[0]["seg_from"] == 1
    assert set(ci[0]["entity_ids"]) >= {"formula.gui_zhi_tang", "symptom.han_chu"}
    assert len(kps) == 4
    for k in kps:
        assert k["citation"]["url"] == t_url("tv-001", k["start_s"])
        assert k["kp_id"].startswith("tv-001.kp")
    tip = next(k for k in kps if k["type"] == "clinical_tip")
    assert tip["chapter_id"] == "tv-001.c02.s1"

    ents = {e["entity_id"]: e for e in _jsonl(kdir / "entities.jsonl")}
    assert "formula.da_xian_xiong_tang" not in ents           # rejected false positive
    assert ents["formula.da_qing_long_tang"]["surfaces"] == ["大陷胸汤"]
    assert ents["herb.gui_zhi"]["dosages"] == ["三钱"]
    assert ents["new.concept.微汗"]["in_lexicon"] is False
    assert ents["acupoint.gb20"]["n_mentions"] == 2            # both have 针/扎 nearby
    assert ents["clause.shl.012"]["type"] == "clause"
    outline = (kdir / "outline.md").read_text("utf-8")
    assert f"[01:40]({t_url('tv-001', 100.4)}) **c02 第12条 桂枝汤**" in outline

    idx = build_index(root)
    assert idx["n_knowledge_points"] == 4
    rows = list(csv.DictReader((root / "data/knowledge/_index/knowledge_points.csv").open(encoding="utf-8")))
    assert rows[0]["url"].startswith("/watch/tv-001?t=")
    erows = list(csv.DictReader((root / "data/knowledge/_index/entities.csv").open(encoding="utf-8")))
    assert any(r["entity_id"] == "herb.gui_zhi" and r["videos"] == "tv-001" for r in erows)


def _rewrite(root: pathlib.Path, w: dict) -> None:
    p = root / "data/knowledge/tv-001/annotations" / f"{w['window']}.yaml"
    p.write_text(yaml.safe_dump(w, allow_unicode=True, sort_keys=False), "utf-8")


def test_build_rejects_bad_quote_unknown_entity_and_orphan_section(root: pathlib.Path):
    bad = json.loads(json.dumps(W1))
    bad["kps"][1]["q"] = "这句话不在原文里"
    bad["kps"][1]["ents"] = ["herb.not_in_lexicon"]
    bad["chapters"].append({"key": "c09.s1", "parent": "c09", "title": "孤儿", "start_seq": 9})
    _rewrite(root, bad)
    with pytest.raises(KnowledgeBuildError) as ei:
        build(root, "tv-001", strict=True)
    msg = "\n".join(ei.value.errors)
    assert "not found in seq 8-9" in msg
    assert "herb.not_in_lexicon" in msg
    assert "unknown parent" in msg
    assert not (root / "data/knowledge/tv-001/knowledge_points.jsonl").exists()
    rep = build(root, "tv-001", strict=False)   # non-strict still writes, listing the errors
    assert rep["errors"]


def test_build_reports_overlapping_chapters(root: pathlib.Path):
    bad = json.loads(json.dumps(W0))
    bad["chapters"][1]["end_seq"] = 9          # c02 explicitly runs past c03's start (8)
    _rewrite(root, bad)
    with pytest.raises(KnowledgeBuildError, match="overlaps"):
        build(root, "tv-001", strict=True)


def test_s09_registered_but_not_in_default_plan():
    from tcmkb_ingest.steps import STEP_ORDER, normalize_step, steps_up_to, get_runner
    assert STEP_ORDER[-1] == "s09_knowledge" and normalize_step("s09") == "s09_knowledge"
    assert "s09_knowledge" not in steps_up_to("s08")
    assert callable(get_runner("s09"))
