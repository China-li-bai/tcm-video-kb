"""Dictionary entity matcher (longest match, match_policy aware). Used by s10_entities and query understanding."""
from __future__ import annotations

class Matcher:
    def __init__(self, entries: list[dict], ctx_window: int = 8):
        self.surf: dict[str, list[dict]] = {}
        for e in entries:
            if e.get("match_policy", "always") == "never": continue
            for s in [e["term"], *e.get("aliases", [])]:
                if len(s) == 1 and e.get("match_policy", "always") != "context": continue
                self.surf.setdefault(s, []).append(e)
        self.lens = sorted({len(s) for s in self.surf}, reverse=True)
        self.w = ctx_window

    def _ctx_ok(self, e, text, i, j):
        if e.get("match_policy", "always") != "context": return True
        around = text[max(0, i - self.w):i] + "\u0000" + text[j:j + self.w]
        return any(c in around for c in e.get("context_any", []))

    def find(self, text: str):
        """-> list of {start, end, surface, ids: [entity_id, ...]} (non-overlapping, longest first)."""
        res, i = [], 0
        while i < len(text):
            hit = None
            for L in self.lens:
                s = text[i:i + L]
                if len(s) < L or s not in self.surf: continue
                ids = [e["id"] for e in self.surf[s] if self._ctx_ok(e, text, i, i + L)]
                if ids: hit = {"start": i, "end": i + L, "surface": s, "ids": ids}; break
            if hit: res.append(hit); i = hit["end"]
            else: i += 1
        return res
