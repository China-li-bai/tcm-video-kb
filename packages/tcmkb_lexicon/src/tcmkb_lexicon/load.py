"""Load + validate lexicon sources (entries/, corrections/, classics/)."""
from __future__ import annotations
import json, re, hashlib, pathlib
from dataclasses import dataclass, field
import yaml, jsonschema

STATUS_RANK = {"draft": 0, "reviewed": 1}

@dataclass
class Lexicon:
    root: pathlib.Path
    version: str
    config: dict
    entries: list[dict]
    general_rules: list[dict]
    classics: list[dict]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def by_id(self): return {e["id"]: e for e in self.entries}

    def content_hash(self) -> str:
        h = hashlib.sha256()
        for p in sorted(self.root.glob("entries/*.yaml")) + sorted(self.root.glob("corrections/*.yaml")) + sorted(self.root.glob("classics/*.yaml")):
            h.update(p.name.encode()); h.update(p.read_bytes())
        return h.hexdigest()[:8]

    def surfaces(self, entries=None):
        """surface -> list[entry] (term + aliases)."""
        out: dict[str, list[dict]] = {}
        for e in entries if entries is not None else self.entries:
            for s in [e["term"], *e.get("aliases", [])]:
                out.setdefault(s, []).append(e)
        return out

    def correction_rules(self, entries=None) -> list[dict]:
        rules = []
        for e in entries if entries is not None else self.entries:
            for n, r in enumerate(e.get("asr_errors", []), 1):
                rr = {k: v for k, v in r.items() if k != "note"}
                rr.setdefault("to", e["term"]); rr["id"] = f"{e['id']}#e{n}"; rr["entity_id"] = e["id"]
                rules.append(rr)
        for r in self.general_rules:
            rules.append({k: v for k, v in r.items() if k not in ("evidence", "status")})
        return rules

def _schema(root, name):
    return json.loads((root / "schema" / name).read_text())

def load_lexicon(root: str | pathlib.Path, min_status: str | None = None) -> Lexicon:
    root = pathlib.Path(root)
    cfg = yaml.safe_load((root / "build.yaml").read_text()) if (root / "build.yaml").exists() else {}
    if min_status: cfg["min_status"] = min_status
    lx = Lexicon(root, (root / "VERSION").read_text().strip(), cfg, [], [], [])
    es = _schema(root, "lexicon_entry.schema.json"); cs = _schema(root, "correction_rule.schema.json")
    ks = _schema(root, "classic_clauses.schema.json")
    ev, cv, kv = (jsonschema.Draft202012Validator(x) for x in (es, cs, ks))
    for p in sorted(root.glob("entries/*.yaml")):
        data = yaml.safe_load(p.read_text()) or []
        for i, e in enumerate(data):
            for err in ev.iter_errors(e):
                lx.errors.append(f"{p.name}[{i}] {e.get('id')}: schema: {err.message}")
            if e.get("category") and p.stem != e["category"]:
                lx.errors.append(f"{p.name}[{i}] {e.get('id')}: category {e['category']} in wrong file")
            lx.entries.append(e)
    for p in sorted(root.glob("corrections/*.yaml")):
        for i, r in enumerate(yaml.safe_load(p.read_text()) or []):
            for err in cv.iter_errors(r):
                lx.errors.append(f"{p.name}[{i}] {r.get('id')}: schema: {err.message}")
            lx.general_rules.append(r)
    for p in sorted(root.glob("classics/*.yaml")):
        d = yaml.safe_load(p.read_text())
        for err in kv.iter_errors(d):
            lx.errors.append(f"{p.name}: schema: {err.message} at {list(err.path)[:3]}")
        lx.classics.append(d)
    _semantic_checks(lx)
    return lx

def selected(lx: Lexicon) -> list[dict]:
    rank = STATUS_RANK[lx.config.get("min_status", "reviewed")]
    return [e for e in lx.entries if STATUS_RANK[e["status"]] >= rank]

def _guarded(r): return any(r.get(k) for k in ("left", "left_not", "right", "right_not", "near_any"))

def _semantic_checks(lx: Lexicon):
    seen = {}
    for e in lx.entries:
        if e["id"] in seen: lx.errors.append(f"duplicate id {e['id']}")
        seen[e["id"]] = e
        if not e["id"].startswith(e["category"] + "."):
            lx.errors.append(f"{e['id']}: id prefix must be '{e['category']}.'")
        if e.get("match_policy") == "context" and not e.get("context_any"):
            lx.errors.append(f"{e['id']}: match_policy=context needs context_any")
        if not e.get("sources"):
            lx.errors.append(f"{e['id']}: no sources")
    for e in lx.entries:
        for r in e.get("relations", []):
            if r["obj"] not in seen: lx.errors.append(f"{e['id']}: relation obj {r['obj']} not found")
    surf = lx.surfaces()
    for s, es in surf.items():
        if len({x["id"] for x in es}) > 1:
            lx.warnings.append(f"ambiguous surface 「{s}」: {', '.join(sorted({x['id'] for x in es}))}")
    gids = set()
    for r in lx.correction_rules():
        if r["id"] in gids: lx.errors.append(f"duplicate correction id {r['id']}")
        gids.add(r["id"])
        try:
            pat = re.compile(r["from"] if r.get("type") == "regex" else re.escape(r["from"]))
            for k in ("left", "left_not", "right", "right_not"):
                if r.get(k): re.compile(r[k])
        except re.error as ex:
            lx.errors.append(f"{r['id']}: bad regex: {ex}"); continue
        if r.get("type") != "regex" and r["from"] in surf and not _guarded(r):
            lx.errors.append(f"{r['id']}: unguarded rule rewrites a valid lexicon surface 「{r['from']}」")
        elif r.get("type") != "regex" and r["from"] in surf:
            lx.warnings.append(f"{r['id']}: guarded rule rewrites valid surface 「{r['from']}」")
    for c in lx.classics:
        nos = [x["no"] for x in c["clauses"]]
        if nos != list(range(1, len(nos) + 1)): lx.errors.append(f"classics/{c['book_id']}: clause numbers not contiguous")
        for x in c["clauses"]:
            for eid in x.get("entities", []):
                if eid not in seen: lx.errors.append(f"{x['id']}: entity {eid} not found")
