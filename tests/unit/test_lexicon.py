"""Lexicon v0.1 tests: schema/semantic validation, build artifacts, correction & match cases."""
import json, pathlib, re
import pytest
from tcmkb_lexicon import load_lexicon, Corrector
from tcmkb_lexicon.build import build
from tcmkb_lexicon.cases import run_cases, corrector_for

ROOT = pathlib.Path(__file__).resolve().parents[2] / "lexicon"

@pytest.fixture(scope="module")
def lx(): return load_lexicon(ROOT)

@pytest.fixture(scope="module")
def dist(lx, tmp_path_factory):
    d = tmp_path_factory.mktemp("dist"); build(lx, d); return d

def test_validates_without_errors(lx):
    assert lx.errors == []

def test_all_entries_are_draft(lx):
    assert {e["status"] for e in lx.entries} == {"draft"}

def test_361_standard_acupoints_with_codes(lx):
    std = [e for e in lx.entries if e["category"] == "acupoint" and not e.get("attrs", {}).get("extra_point")]
    codes = {e["attrs"]["code"] for e in std}
    assert len(std) == 361 and len(codes) == 361
    per = {}
    for c in codes: per[re.sub(r"\d+$", "", c)] = per.get(re.sub(r"\d+$", "", c), 0) + 1
    assert per == {"LU": 11, "LI": 20, "ST": 45, "SP": 21, "HT": 9, "SI": 19, "BL": 67, "KI": 27, "PC": 9, "TE": 23, "GB": 44, "LR": 14, "GV": 28, "CV": 24}

def test_shanghanlun_398_clauses(lx):
    shl = next(c for c in lx.classics if c["book_id"] == "shanghanlun")
    cl = shl["clauses"]
    assert len(cl) == 398
    assert cl[0]["text"].startswith("太阳之为病，脉浮，头项强痛而恶寒")
    assert "桂枝汤主之" in cl[11]["text"]            # 第12条
    assert cl[300]["text"].startswith("少阴病，始得之，反发热，脉沉者，麻黄细辛附子汤主之")  # 第301条
    assert cl[397]["text"].startswith("病人脉已解，而日暮微烦")  # 第398条

def test_dist_artifacts(lx, dist):
    info = json.loads((dist / "build_info.json").read_text())
    cap = lx.config["hotword"]["max_per_series"]
    for name in ["global", *lx.config["hotword"]["series"]]:
        words = (dist / "hotwords" / f"{name}.txt").read_text().split()
        assert 0 < len(words) <= cap and len(words) == len(set(words))
        assert not {"太阳", "阳明", "少阳", "太阴", "少阴", "厥阴"} & set(words), "six_channel must not be hotwords"
    lines = (dist / "lexicon.jsonl").read_text().splitlines()
    assert len(lines) == info["entries"] + info["clauses"]
    rules = json.loads((dist / "corrections.json").read_text())["rules"]
    assert len({r["id"] for r in rules}) == len(rules)
    for l in (dist / "jieba_userdict.txt").read_text().splitlines():
        w, f, tag = l.split(" "); assert int(f) > 0 and tag.startswith("n_")

def test_cases_yaml(lx):
    n, fails = run_cases(lx)
    assert not fails, "\n".join(" | ".join(map(str, f)) for f in fails)

def test_edits_are_recorded(lx):
    out, edits = corrector_for(lx).correct("针扎到竹山里")
    assert out == "针扎到足三里" and edits == [{"pos": 3, "from": "竹山里", "to": "足三里", "rule": "acupoint.st36#e1"}]

def test_protected_surface_blocks_rule():
    c = Corrector([{"id": "x", "from": "金方", "to": "经方"}], protected={"千金方"})
    assert c.correct("千金方")[0] == "千金方" and c.correct("金方家")[0] == "经方家"
