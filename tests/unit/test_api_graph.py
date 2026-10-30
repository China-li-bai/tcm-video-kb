"""API: health and a non-empty formula subgraph (fixture, plus the real 桂枝汤 slice)."""
from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from tcmkb_api.app import create_app
from tcmkb_core.config import repo_root
from tcmkb_graph.draft import retrieval_edges

Q12 = "一二三四五六七八九十甲乙"


def _write_repo(tmp: Path) -> None:
    entries = [
        {
            "id": "formula.gui_zhi_tang",
            "term": "桂枝汤",
            "category": "formula",
            "relations": [
                {"pred": "composed_of", "obj": "herb.gui_zhi"},
                {"pred": "composed_of", "obj": "herb.shao_yao"},
            ],
        },
        {"id": "herb.gui_zhi", "term": "桂枝", "category": "herb"},
        {"id": "herb.shao_yao", "term": "芍药", "category": "herb"},
        {"id": "syndrome.tai_yang_zhong_feng", "term": "太阳中风", "category": "syndrome"},
        {"id": "syndrome.tai_yang_bing", "term": "太阳病", "category": "syndrome"},
        {"id": "symptom.e_han", "term": "恶寒", "category": "symptom"},
        {"id": "pulse.fu", "term": "浮脉", "category": "pulse"},
    ]
    lex = tmp / "lexicon" / "entries"
    lex.mkdir(parents=True)
    (lex / "mini.yaml").write_text(yaml.dump(entries, allow_unicode=True), encoding="utf-8")
    kdir = tmp / "data" / "knowledge" / "shl-001"
    kdir.mkdir(parents=True)
    rows = [
        {
            "kp_id": "shl-001.kp0069",
            "video_id": "shl-001",
            "type": "formula_indication",
            "statement": "桂枝汤归到太阳中风。",
            "entity_ids": ["formula.gui_zhi_tang", "syndrome.tai_yang_zhong_feng"],
            "evidence_quote": "大概百分之六十以上的处方都是桂枝汤",
            "start_s": 5046.16,
            "end_s": 5105.62,
            "confidence": 0.85,
            "citation": {"youtube_id": "W-z7WGZXmp8", "title": "太阳症"},
        },
        {
            "kp_id": "shl-001.kp0018",
            "video_id": "shl-001",
            "type": "diagnostic_rule",
            "statement": "脉浮、恶寒，是太阳病表证。",
            "entity_ids": ["pulse.fu", "symptom.e_han", "syndrome.tai_yang_bing", "new.symptom.头项强痛"],
            "evidence_quote": Q12,
            "start_s": 1642.71,
            "end_s": 1668.57,
            "confidence": 0.9,
            "citation": {"youtube_id": "W-z7WGZXmp8", "title": "太阳症"},
        },
    ]
    (kdir / "knowledge_points.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )
    mention = {
        "entity_id": "formula.gui_zhi_tang",
        "video_id": "shl-001",
        "first_start_s": 1624.33,
        "first_url": "https://www.youtube.com/watch?v=W-z7WGZXmp8&t=1624s",
        "asr_uncertain": False,
    }
    (kdir / "entities.jsonl").write_text(json.dumps(mention, ensure_ascii=False) + "\n", encoding="utf-8")


def test_health_and_subgraph_fixture(tmp_path: Path):
    _write_repo(tmp_path)
    client = TestClient(create_app(tmp_path))
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/graph/subgraph").status_code == 422
    missing = client.get("/graph/subgraph", params={"focus": "formula.missing"})
    assert missing.status_code == 404

    body = client.get("/graph/subgraph", params={"focus": "formula.gui_zhi_tang"}).json()
    assert body["nodes"]
    assert body["edges"]
    assert {e["obj_id"] for e in body["edges"] if e["pred"] == "composed_of"} == {
        "herb.gui_zhi", "herb.shao_yao",
    }
    assert all(e["review_status"] != "approved" for e in body["edges"])
    assert retrieval_edges(body["edges"]) == []
    assert any(h["kp_id"] == "shl-001.kp0069" for h in body["held"])
    focus = next(n for n in body["nodes"] if n["id"] == "formula.gui_zhi_tang")
    assert any("youtube.com" in (c.get("youtube_t_url") or "") for c in focus["citations"])

    paths = client.get("/graph/paths", params={"focus": "formula.gui_zhi_tang"}).json()
    assert paths["equal_weight"] is True
    assert paths["tracks"] == []

    tracked = client.get("/graph/paths", params={"focus": "syndrome.tai_yang_bing"}).json()
    cards = tracked["tracks"][0]["cards"]
    assert [c["subj_id"] for c in cards] == ["pulse.fu", "symptom.e_han"]
    assert all("confidence" not in c and c["review_status"] == "candidate" for c in cards)
    assert "t=" in cards[0]["youtube_t_url"]


def test_real_guizhi_subgraph_nonempty():
    root = repo_root()
    if not (root / "lexicon/entries/formula.yaml").is_file():
        return
    client = TestClient(create_app(root))
    health = client.get("/health")
    assert health.status_code == 200 and health.json()["status"] == "ok"
    res = client.get("/graph/subgraph", params={"focus": "formula.gui_zhi_tang"})
    assert res.status_code == 200
    body = res.json()
    assert body["nodes"] and body["edges"]
    assert any(e["pred"] == "composed_of" and e["obj_id"] == "herb.gui_zhi" for e in body["edges"])
    assert all(e.get("review_status") != "approved" for e in body["edges"])
    assert any(h["kp_id"] == "shl-001.kp0069" for h in body["held"])
