"""Dictionary post-ASR correction engine.

Rules (see schema/correction_rule.schema.json and entry.asr_errors):
  from (literal|regex) -> to, with optional guards
  left / left_not   : regex that must / must not match the text immediately LEFT of the match (anchored at the match)
  right / right_not : regex that must / must not match the text immediately RIGHT of the match
  near_any + window : one of these strings must occur within `window` chars on either side
Longest match wins at each position; a match is skipped when it lies inside a longer valid lexicon
surface (e.g. 「金方」 inside 「千金方」). Applied to Simplified text, sentence by sentence; never
changes timestamps — callers keep per-sentence timing and store the returned edits.
"""
from __future__ import annotations
import re
from dataclasses import dataclass

@dataclass
class _Rule:
    id: str; pat: re.Pattern; to: str; plen: int
    left: re.Pattern | None; left_not: re.Pattern | None; right: re.Pattern | None; right_not: re.Pattern | None
    near: list[str]; window: int; first: str | None

def _c(x, anchor_end=False):
    if not x: return None
    return re.compile(f"(?:{x})$" if anchor_end else f"(?:{x})")

class Corrector:
    def __init__(self, rules: list[dict], protected: set[str] | None = None, passes: int = 2):
        self.rules = []
        for r in rules:
            literal = r.get("type", "literal") != "regex"
            src = re.escape(r["from"]) if literal else r["from"]
            self.rules.append(_Rule(r["id"], re.compile(src), r["to"], len(r["from"]) if literal else 0,
                                    _c(r.get("left"), True), _c(r.get("left_not"), True), _c(r.get("right")), _c(r.get("right_not")),
                                    list(r.get("near_any", [])), int(r.get("window", 10)), r["from"][0] if literal else None))
        self.rules.sort(key=lambda x: -x.plen)
        self.by_first: dict[str, list[_Rule]] = {}
        self.regex_rules = [r for r in self.rules if r.first is None]
        for r in self.rules:
            if r.first: self.by_first.setdefault(r.first, []).append(r)
        self.protected = {p for p in (protected or set()) if len(p) >= 2}
        self.plens = sorted({len(p) for p in self.protected}, reverse=True)
        self.passes = passes

    def _inside_protected(self, text, i, j):
        for L in self.plens:
            if L <= j - i: break
            for k in range(max(0, j - L), i + 1):
                if text[k:k + L] in self.protected:
                    return True
        return False

    def _ok(self, r: _Rule, out_tail: str, text: str, i: int, j: int) -> bool:
        right = text[j:j + 30]
        if r.left and not r.left.search(out_tail): return False
        if r.left_not and r.left_not.search(out_tail): return False
        if r.right and not r.right.match(right): return False
        if r.right_not and r.right_not.match(right): return False
        if r.near:
            ctx = out_tail[-r.window:] + "\u0000" + text[j:j + r.window]
            if not any(n in ctx for n in r.near): return False
        return True

    def _one_pass(self, text: str):
        out, edits, i = [], [], 0
        while i < len(text):
            best = None
            cands = self.by_first.get(text[i], []) + self.regex_rules
            tail = "".join(out[-60:])[-60:] if out else ""
            for r in cands:
                m = r.pat.match(text, i)
                if not m or m.end() == i: continue
                if best and m.end() - i <= best[1] - i: continue
                if self._inside_protected(text, i, m.end()): continue
                if not self._ok(r, tail, text, i, m.end()): continue
                best = (r, m.end(), m.group(0))
            if best:
                r, j, frm = best
                pos = sum(len(x) for x in out)
                if frm != r.to:
                    edits.append({"pos": pos, "from": frm, "to": r.to, "rule": r.id})
                out.append(r.to); i = j
            else:
                out.append(text[i]); i += 1
        return "".join(out), edits

    def correct(self, text: str):
        """Return (corrected_text, edits). edits[].pos indexes into the corrected text of that pass."""
        all_edits = []
        for _ in range(self.passes):
            new, edits = self._one_pass(text)
            all_edits += edits
            if new == text: break
            text = new
        return text, all_edits
