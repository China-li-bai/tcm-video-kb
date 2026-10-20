"""CLI: python -m tcmkb_lexicon {validate|build|test|correct|match} [--root lexicon] [--min-status draft]"""
import argparse, json, pathlib, sys
from .load import load_lexicon, selected
from .build import build
from .cases import run_cases, corrector_for
from .match import Matcher

def main(argv=None):
    ap = argparse.ArgumentParser(prog="tcmkb_lexicon")
    ap.add_argument("cmd", choices=["validate", "build", "test", "correct", "match"])
    ap.add_argument("--root", default="lexicon"); ap.add_argument("--dist", default=None)
    ap.add_argument("--min-status", choices=["draft", "reviewed"], default=None)
    ap.add_argument("text", nargs="?")
    a = ap.parse_args(argv)
    lx = load_lexicon(a.root, a.min_status)
    if a.cmd == "validate":
        print(f"entries={len(lx.entries)} errors={len(lx.errors)} warnings={len(lx.warnings)}")
        for e in lx.errors[:100]: print("ERROR", e)
        return 1 if lx.errors else 0
    if a.cmd == "build":
        info = build(lx, pathlib.Path(a.dist or pathlib.Path(a.root) / "dist"))
        print(json.dumps(info, ensure_ascii=False, indent=1)); return 0
    if a.cmd == "test":
        n, fails = run_cases(lx)
        for f in fails: print("FAIL", *f, sep=" | ")
        print(f"cases: {n - len(fails)}/{n} passed"); return 1 if fails else 0
    text = a.text if a.text is not None else sys.stdin.read()
    if a.cmd == "correct":
        out, edits = corrector_for(lx).correct(text)
        print(out); print(json.dumps(edits, ensure_ascii=False), file=sys.stderr); return 0
    if a.cmd == "match":
        print(json.dumps(Matcher(selected(lx)).find(text), ensure_ascii=False, indent=1)); return 0

if __name__ == "__main__":
    sys.exit(main())
