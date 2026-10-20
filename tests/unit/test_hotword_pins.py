"""Hotword pin order: pins first; 足三里 in zj top ~15."""
from tcmkb_lexicon import load_lexicon
from tcmkb_lexicon.build import build, _load_pins
from tcmkb_core.config import repo_root

def test_zj_pins_lead_and_zusanli_top15(tmp_path):
    root = repo_root()
    lx = load_lexicon(root / "lexicon")
    pins = _load_pins(lx, "zj")
    assert pins[0] == "足三里"
    dist = tmp_path / "dist"
    build(lx, dist, repo_root=root)
    words = (dist / "hotwords" / "zj.txt").read_text(encoding="utf-8").splitlines()
    assert words[0] == "足三里"
    assert "足三里" in words[:15]
    # pins that fit length/cap appear at the front in file order
    for i, p in enumerate(pins):
        if p in words:
            # every earlier pin that made it into the list should appear before this one
            for earlier in pins[:i]:
                if earlier in words:
                    assert words.index(earlier) < words.index(p)
