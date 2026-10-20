"""Run lexicon/tests/cases.yaml (must_fix / must_not_fix / match)."""
from __future__ import annotations
import yaml
from .load import Lexicon, selected
from .correct import Corrector
from .match import Matcher

def corrector_for(lx: Lexicon) -> Corrector:
    ents = selected(lx)
    prot = {s for e in ents for s in [e["term"], *e.get("aliases", [])]}
    return Corrector(lx.correction_rules(ents), protected=prot)

def run_cases(lx: Lexicon, path=None):
    path = path or lx.root / "tests" / "cases.yaml"
    cases = yaml.safe_load(open(path))
    cor = corrector_for(lx); mat = Matcher(selected(lx))
    fails, n = [], 0
    for c in cases.get("must_fix", []):
        n += 1; got, _ = cor.correct(c["in"])
        if got != c["out"]: fails.append(("must_fix", c["in"], c["out"], got))
    for c in cases.get("must_not_fix", []):
        n += 1; got, ed = cor.correct(c["in"])
        if got != c["in"]: fails.append(("must_not_fix", c["in"], c["in"], got))
    for c in cases.get("match", []):
        n += 1
        found = {i for m in mat.find(c["in"]) for i in m["ids"]}
        missing = set(c.get("expect", [])) - found; extra = set(c.get("not_expect", [])) & found
        if missing or extra: fails.append(("match", c["in"], f"expect {sorted(c.get('expect', []))} not {sorted(c.get('not_expect', []))}", sorted(found)))
    return n, fails
