"""OpenCC + lexicon corrections used by s06."""
import json, pathlib
import pytest
from tcmkb_lexicon.correct import Corrector
from tcmkb_core.config import repo_root

@pytest.fixture(scope="module")
def corrector():
    root = repo_root()
    p = root / "lexicon" / "dist" / "corrections.json"
    if not p.exists():
        pytest.skip("lexicon dist not built")
    data = json.loads(p.read_text(encoding="utf-8"))
    return Corrector(data["rules"], protected=set(data.get("protected_surfaces") or []))

def test_zusanli_correction(corrector):
    out, edits = corrector.correct("针扎到竹山里以后")
    assert "足三里" in out
    assert any(e["to"] == "足三里" for e in edits)

def test_jiu_correction(corrector):
    out, edits = corrector.correct("常常揪足三里的")
    assert "灸" in out
    assert any(e["from"] == "揪" for e in edits)

def test_opencc_t2s():
    from opencc import OpenCC
    assert "经络" in OpenCC("t2s").convert("經絡")
