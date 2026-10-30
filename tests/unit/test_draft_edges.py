"""Hard gate for candidate treats / indicates. Nothing is marked approved."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from tcmkb_core.config import repo_root
from tcmkb_graph.cli import main
from tcmkb_graph.draft import consider_kp, materialize, retrieval_edges
from tcmkb_graph.lexicon_index import Ent
from tcmkb_graph.models import CandidateEdge
from tcmkb_graph.subgraph import build_paths, build_subgraph

Q12 = "一二三四五六七八九十甲乙"  # 12 chars
Q11 = "一二三四五六七八九十甲"


def _ent(eid: str, term: str, category: str, rels: tuple[tuple[str, str], ...] = ()) -> Ent:
    return Ent(eid, term, category, rels)


INDEX = {
    "formula.gui_zhi_tang": _ent(
        "formula.gui_zhi_tang", "桂枝汤", "formula",
        (("composed_of", "herb.gui_zhi"), ("composed_of", "herb.shao_yao")),
    ),
    "formula.ma_huang_tang": _ent("formula.ma_huang_tang", "麻黄汤", "formula"),
    "herb.gui_zhi": _ent("herb.gui_zhi", "桂枝", "herb"),
    "herb.shao_yao": _ent("herb.shao_yao", "芍药", "herb"),
    "syndrome.tai_yang_zhong_feng": _ent("syndrome.tai_yang_zhong_feng", "太阳中风", "syndrome"),
    "syndrome.wen_bing": _ent("syndrome.wen_bing", "温病", "syndrome"),
    "syndrome.tai_yang_bing": _ent("syndrome.tai_yang_bing", "太阳病", "syndrome"),
    "symptom.e_han": _ent("symptom.e_han", "恶寒", "symptom"),
    "symptom.han_chu": _ent("symptom.han_chu", "汗出", "symptom"),
    "symptom.e_feng": _ent("symptom.e_feng", "恶风", "symptom"),
    "pulse.fu": _ent("pulse.fu", "浮脉", "pulse"),
    "six_channel.taiyang": _ent("six_channel.taiyang", "太阳", "six_channel"),
}


def kp(**over) -> dict:
    base = {
        "kp_id": "shl-001.kp9001",
        "video_id": "shl-001",
        "type": "formula_indication",
        "statement": "桂枝汤对应太阳中风。",
        "entity_ids": ["formula.gui_zhi_tang", "syndrome.tai_yang_zhong_feng"],
        "evidence_quote": Q12,
        "start_s": 100.0,
        "end_s": 130.0,
        "confidence": 0.95,
        "citation": {"youtube_id": "W-z7WGZXmp8", "title": "太阳症", "series": "shl", "episode": 1},
    }
    base.update(over)
    return base


def test_fi_unambiguous_pair_is_candidate_treats():
    edges, held = consider_kp(kp(), INDEX)
    assert held is None
    assert len(edges) == 1
    edge = edges[0]
    assert edge["pred"] == "treats"
    assert edge["subj_id"] == "formula.gui_zhi_tang"
    assert edge["obj_id"] == "syndrome.tai_yang_zhong_feng"
    assert edge["source"] == "lecture"
    assert edge["review_status"] == "candidate"
    assert edge["kp_id"] == "shl-001.kp9001"
    assert "youtube.com/watch" in edge["citation"]["youtube_t_url"]
    assert "t=100s" in edge["citation"]["youtube_t_url"]
    assert edge["citation"]["t_url"] == "/watch/shl-001?t=100&end=130"
    assert retrieval_edges(edges) == []


def test_hard_gate_blocks_confidence_evidence_and_window():
    _, low = consider_kp(kp(confidence=0.85), INDEX)
    assert low and any(r.startswith("confidence 0.85") for r in low["reasons"])
    _, short = consider_kp(kp(evidence_quote=Q11), INDEX)
    assert short and any(r.startswith("evidence 11") for r in short["reasons"])
    _, narrow = consider_kp(kp(start_s=0, end_s=14.9), INDEX)
    assert narrow and any("window" in r for r in narrow["reasons"])
    assert consider_kp(kp(confidence=0.89), INDEX)[0] == []
    assert consider_kp(kp(evidence_quote=Q11), INDEX)[0] == []
    assert consider_kp(kp(start_s=0, end_s=14.9), INDEX)[0] == []
    edges, held = consider_kp(kp(confidence=0.90, evidence_quote=Q12, start_s=0, end_s=15), INDEX)
    assert held is None and len(edges) == 1


def test_non_canonical_and_asr_uncertain_are_not_endpoints():
    edges, held = consider_kp(kp(entity_ids=["new.formula.桂枝汤", "syndrome.tai_yang_zhong_feng"]), INDEX)
    assert edges == []
    assert held and any(r.startswith("non_canonical:") for r in held["reasons"])

    edges, held = consider_kp(
        kp(entity_ids=["formula.gui_zhi_tang", "syndrome.tai_yang_zhong_feng"]),
        INDEX,
        uncertain={"formula.gui_zhi_tang"},
    )
    assert edges == []
    assert held and any(r.startswith("asr_uncertain:") for r in held["reasons"])

    # the uncertain sign is dropped; the clean sign still becomes one candidate
    dr = kp(
        type="diagnostic_rule",
        statement="脉浮、恶寒，是太阳病的表证。",
        entity_ids=["pulse.fu", "symptom.e_han", "syndrome.tai_yang_bing"],
    )
    edges, held = consider_kp(dr, INDEX, uncertain={"pulse.fu"})
    assert held is None
    assert [(e["subj_id"], e["obj_id"]) for e in edges] == [("symptom.e_han", "syndrome.tai_yang_bing")]


def test_fi_multi_pair_is_held_not_crossed():
    edges, held = consider_kp(kp(entity_ids=[
        "formula.gui_zhi_tang", "formula.ma_huang_tang",
        "syndrome.tai_yang_zhong_feng", "syndrome.wen_bing",
    ]), INDEX)
    assert edges == []
    assert held and "ambiguous_multi_pair" in held["reasons"]


def test_fi_one_formula_two_syndromes_are_equal_candidates():
    edges, held = consider_kp(kp(entity_ids=[
        "formula.gui_zhi_tang", "syndrome.wen_bing", "syndrome.tai_yang_zhong_feng",
    ]), INDEX)
    assert held is None
    assert {(e["obj_id"]) for e in edges} == {"syndrome.wen_bing", "syndrome.tai_yang_zhong_feng"}
    assert {e["review_status"] for e in edges} == {"candidate"}
    assert "rank" not in edges[0]


def test_dr_one_syndrome_many_signs_and_rejects_multi_pattern_and_negation():
    dr = kp(
        type="diagnostic_rule",
        statement="脉浮与恶寒同见，是太阳病表证。",
        entity_ids=["pulse.fu", "symptom.e_han", "syndrome.tai_yang_bing", "new.symptom.头项强痛"],
    )
    edges, held = consider_kp(dr, INDEX)
    assert held is None
    assert sorted(e["subj_id"] for e in edges) == ["pulse.fu", "symptom.e_han"]
    assert {e["pred"] for e in edges} == {"indicates"}
    assert all(not e["subj_id"].startswith("new.") for e in edges)

    multi, held = consider_kp(kp(
        type="diagnostic_rule",
        statement="汗出恶风可以是中风，温病另有处方。",
        entity_ids=["symptom.han_chu", "symptom.e_feng", "syndrome.tai_yang_zhong_feng", "syndrome.wen_bing"],
    ), INDEX)
    assert multi == []
    assert held and "multi_pattern_unpaired" in held["reasons"]

    negated, held = consider_kp(kp(
        type="diagnostic_rule",
        statement="呕吐不是太阳病本证。",
        entity_ids=["symptom.e_han", "syndrome.tai_yang_bing"],
    ), INDEX)
    assert negated == []
    assert held and "negation" in held["reasons"]

    # 六经 id is not a 证
    edges, held = consider_kp(kp(
        type="diagnostic_rule",
        statement="恶寒放在太阳经里讲。",
        entity_ids=["symptom.e_han", "six_channel.taiyang"],
    ), INDEX)
    assert edges == [] and held is None


def test_formula_composition_does_not_become_an_edge():
    edges, held = consider_kp(kp(
        type="formula_composition",
        entity_ids=["formula.gui_zhi_tang", "herb.gui_zhi", "herb.shao_yao"],
    ), INDEX)
    assert edges == [] and held is None


def test_candidate_model_rejects_approved():
    edges, _ = consider_kp(kp(), INDEX)
    payload = dict(edges[0])
    payload["review_status"] = "approved"
    with pytest.raises(ValidationError):
        CandidateEdge.model_validate(payload)


def test_paths_order_by_id_not_confidence():
    high, _ = consider_kp(kp(
        kp_id="shl-001.kp2", confidence=0.99,
        entity_ids=["formula.gui_zhi_tang", "syndrome.wen_bing"],
    ), INDEX)
    low, _ = consider_kp(kp(
        kp_id="shl-001.kp1", confidence=0.91,
        entity_ids=["formula.gui_zhi_tang", "syndrome.tai_yang_zhong_feng"],
    ), INDEX)
    from tcmkb_graph.draft import Materialization
    mat = Materialization(edges=high + low, held=[], index=INDEX, knowledge_root=Path("/none"))
    paths = build_paths("formula.gui_zhi_tang", mat)
    assert paths["equal_weight"] is True
    assert [t["syndrome_id"] for t in paths["tracks"]] == [
        "syndrome.tai_yang_zhong_feng",
        "syndrome.wen_bing",
    ]
    assert "confidence" not in paths["tracks"][0]["treats"][0]
    assert "score" not in paths["tracks"][0]


def _write_mini(tmp: Path) -> None:
    entries = [
        {"id": "formula.gui_zhi_tang", "term": "桂枝汤", "category": "formula",
         "relations": [{"pred": "composed_of", "obj": "herb.gui_zhi"}]},
        {"id": "herb.gui_zhi", "term": "桂枝", "category": "herb"},
        {"id": "syndrome.tai_yang_zhong_feng", "term": "太阳中风", "category": "syndrome"},
    ]
    lex = tmp / "lexicon" / "entries"
    lex.mkdir(parents=True)
    (lex / "mini.yaml").write_text(yaml.dump(entries, allow_unicode=True), encoding="utf-8")
    kdir = tmp / "data" / "knowledge" / "shl-001"
    kdir.mkdir(parents=True)
    row = kp()
    (kdir / "knowledge_points.jsonl").write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")


def test_cli_writes_candidate_file(tmp_path: Path):
    _write_mini(tmp_path)
    out = tmp_path / "out" / "candidates.jsonl"
    held = tmp_path / "out" / "held.jsonl"
    code = main(["draft", "--root", str(tmp_path), "--out", str(out), "--held", str(held)])
    assert code == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["review_status"] == "candidate"
    assert retrieval_edges(rows) == []
    assert held.read_text(encoding="utf-8") == ""


def test_shl001_real_kp_gate():
    """shl-001.kp0018 clears the gate; kp0069 (桂枝汤→太阳中风, conf 0.85) stays held."""
    root = repo_root()
    if not (root / "data/knowledge/shl-001/knowledge_points.jsonl").is_file():
        pytest.skip("shl-001 knowledge is not in this checkout")
    mat = materialize(root, videos=["shl-001"])
    pairs = {(e["subj_id"], e["pred"], e["obj_id"], e["kp_id"]) for e in mat.edges}
    assert pairs == {
        ("pulse.fu", "indicates", "syndrome.tai_yang_bing", "shl-001.kp0018"),
        ("symptom.e_han", "indicates", "syndrome.tai_yang_bing", "shl-001.kp0018"),
    }
    assert all(e["review_status"] == "candidate" and e["source"] == "lecture" for e in mat.edges)
    assert retrieval_edges(mat.edges) == []
    assert all("youtube.com" in e["citation"]["youtube_t_url"] for e in mat.edges)
    held = next(h for h in mat.held if h["kp_id"] == "shl-001.kp0069")
    assert "formula.gui_zhi_tang" in held["subj_ids"]
    assert "syndrome.tai_yang_zhong_feng" in held["obj_ids"]
    assert any("0.85" in r for r in held["reasons"])
    assert "太阳中风" in held["obj_labels"]

    sub = build_subgraph("formula.gui_zhi_tang", mat)
    herbs = {e["obj_id"] for e in sub["edges"] if e["pred"] == "composed_of"}
    assert herbs == {
        "herb.gui_zhi", "herb.shao_yao", "herb.gan_cao", "herb.sheng_jiang", "herb.da_zao",
    }
    assert all(e["review_status"] != "approved" for e in sub["edges"])
    assert any(h["kp_id"] == "shl-001.kp0069" for h in sub["held"])
    focus = next(n for n in sub["nodes"] if n["id"] == "formula.gui_zhi_tang")
    assert any(c.get("youtube_t_url") for c in focus["citations"])

    paths = build_paths("syndrome.tai_yang_bing", mat)
    assert paths["equal_weight"] is True
    assert [c["subj_id"] for c in paths["tracks"][0]["cards"]] == ["pulse.fu", "symptom.e_han"]
    assert all("confidence" not in c for c in paths["tracks"][0]["cards"])
    formula_paths = build_paths("formula.gui_zhi_tang", mat)
    assert formula_paths["tracks"] == []
    assert any(h["kp_id"] == "shl-001.kp0069" for h in formula_paths["held"])
