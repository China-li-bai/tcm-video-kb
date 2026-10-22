"""Lexicon entity candidates and 伤寒论 clause matching (deterministic)."""
from __future__ import annotations
import collections, difflib, json, pathlib, re
from functools import lru_cache
from typing import Any

from tcmkb_core.knowledge import LEXICON_CATEGORY_TO_TYPE
from tcmkb_lexicon.match import Matcher

# lexicon categories that are noise for entity mentions in free speech
SKIP_CATEGORIES = {"course_term"}
# single, very generic words we never report as standalone mentions
GENERIC = {"寒", "热", "风", "气", "血", "水", "心", "肝", "脾", "肺", "肾", "胃", "阴", "阳", "脉"}


@lru_cache(maxsize=4)
def _load_entries(path: str) -> tuple[dict[str, Any], ...]:
    out = []
    for ln in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        if ln.strip():
            out.append(json.loads(ln))
    return tuple(out)


class Lexicon:
    def __init__(self, root: pathlib.Path):
        p = root / "lexicon" / "dist" / "lexicon.jsonl"
        if not p.exists():
            raise FileNotFoundError(f"{p} missing: run `python -m tcmkb_lexicon build --root lexicon`")
        self.entries = list(_load_entries(str(p)))
        self.by_id = {e["id"]: e for e in self.entries}
        usable = [e for e in self.entries if e["category"] not in SKIP_CATEGORIES
                  and e["category"] in LEXICON_CATEGORY_TO_TYPE]
        self.matcher = Matcher(usable)
        self.asr_from: dict[str, str] = {}
        for e in usable:                       # unguarded asr_errors -> entity id
            for r in e.get("asr_errors") or []:
                if not any(k in r for k in ("left", "right", "near_any")) and "to" not in r:
                    self.asr_from[r["from"]] = e["id"]
        self.clauses = {e["attrs"]["no"]: e for e in self.entries if e["category"] == "clause"}

    def type_of(self, entity_id: str) -> str | None:
        e = self.by_id.get(entity_id)
        if e:
            return LEXICON_CATEGORY_TO_TYPE.get(e["category"])
        if entity_id.startswith("new."):
            return entity_id.split(".")[1]
        return None

    def canonical(self, entity_id: str) -> str | None:
        e = self.by_id.get(entity_id)
        if e:
            return e["term"]
        if entity_id.startswith("new."):
            return entity_id.split(".", 2)[2]
        return None

    def clause_id(self, no: int) -> str | None:
        e = self.clauses.get(int(no))
        return e["id"] if e else None

    def find(self, text: str) -> list[dict[str, Any]]:
        """Matcher hits (canonical/aliases) on corrected text, minus generic 1-char hits."""
        hits = []
        for h in self.matcher.find(text):
            if h["surface"] in GENERIC:
                continue
            hits.append(h)
        return hits


def segment_mentions(lx: Lexicon, seg: dict[str, Any]) -> list[dict[str, Any]]:
    """Lexicon mentions in one segment: surface (raw ASR) vs corrected (cleaned text)."""
    text = seg["text"]
    edits = {e.get("to"): e.get("from") for e in seg.get("edits") or [] if e.get("to")}
    out = []
    for h in lx.find(text):
        eid = h["ids"][0]
        out.append({"entity_id": eid, "corrected": h["surface"],
                    "surface": edits.get(h["surface"], h["surface"]), "seq": seg["seq"],
                    "ambiguous": h["ids"][1:]})
    return out


def window_candidates(lx: Lexicon, segments: list[dict[str, Any]]) -> list[tuple[str, str, int, int]]:
    """[(entity_id, term, count, first_seq)] for a window, most frequent first."""
    cnt: collections.Counter[str] = collections.Counter()
    first: dict[str, int] = {}
    for s in segments:
        for m in segment_mentions(lx, s):
            cnt[m["entity_id"]] += 1
            first.setdefault(m["entity_id"], s["seq"])
    return [(eid, lx.canonical(eid) or eid, n, first[eid]) for eid, n in cnt.most_common()]


_PUNCT = re.compile(r"[\s，。、；：！？,.;:!?「」『』“”‘’（）()…—-]")


def _norm(s: str) -> str:
    return _PUNCT.sub("", s)


def match_clauses(lx: Lexicon, segments: list[dict[str, Any]], min_ratio: float = 0.6,
                  min_len: int = 8) -> list[dict[str, Any]]:
    """Clauses read aloud: fuzzy match each clause against a sliding text window.

    Returns [{no, clause_id, seq, ratio}] best hit per clause with ratio >= min_ratio.
    Cheap prefilter: a clause is tried only if a 4-gram of it appears in the text.
    """
    flat, owners = [], []
    for s in segments:
        t = _norm(s["text"])
        flat.append(t)
        owners.extend([s["seq"]] * len(t))
    text = "".join(flat)
    grams = {text[i:i + 4] for i in range(len(text) - 3)}
    res = []
    for no, e in lx.clauses.items():
        ct = _norm(e["attrs"]["text"])
        if len(ct) < min_len:
            continue
        cg = [ct[i:i + 4] for i in range(len(ct) - 3)]
        shared = [g for g in cg if g in grams]
        if len(shared) < max(2, len(cg) // 4):
            continue
        best = (0.0, 0)
        for g in shared[:6]:
            pos = text.find(g)
            while pos != -1:
                a = max(0, pos - len(ct))
                cand = text[a:pos + len(ct)]
                sm = difflib.SequenceMatcher(None, ct, cand, autojunk=False)
                blocks = sm.get_matching_blocks()
                matched = sum(b.size for b in blocks)
                r = matched / len(ct)
                if r > best[0]:
                    first = next((b for b in blocks if b.size), None)
                    best = (r, owners[a + first.b] if first else owners[pos])
                pos = text.find(g, pos + 1)
        if best[0] >= min_ratio:
            res.append({"no": no, "clause_id": e["id"], "seq": best[1], "ratio": round(best[0], 2)})
    return sorted(res, key=lambda r: r["seq"])
