"""Compile lexicon -> dist/ artifacts consumed by ASR (hotwords), s06_clean (corrections), s09/s10 (jieba dict, lexicon.jsonl)."""
from __future__ import annotations
import json, pathlib, datetime, re, collections
from .load import Lexicon, selected

CAT_ORDER = ["formula", "acupoint", "herb", "classic", "person", "meridian", "course_term", "syndrome", "pulse",
             "concept", "method", "symptom", "disease", "zangfu", "tongue", "six_channel", "clause"]
JIEBA_TAG = {c: "n_" + c for c in CAT_ORDER}

def clause_entities(lx: Lexicon):
    out = []
    for c in lx.classics:
        title = c["title"]
        for x in c["clauses"]:
            out.append({"id": x["id"], "term": f"{title}第{x['no']}条", "category": "clause", "aliases": [],
                        "hotword": False, "hotword_scope": [], "match_policy": "never",
                        "attrs": {"book": c["book_id"], "no": x["no"], "section": x["section"], "text": x["text"],
                                  "entities": x.get("entities", [])},
                        "sources": [c["source"]] if isinstance(c["source"], dict) else [{"ref": str(c["source"])}],
                        "status": c.get("status", "draft")})
    return out

def _load_pins(lx: Lexicon, series: str | None) -> list[str]:
    """Load pin list: pins/{series}.txt then pins/global.txt. One term per line; # comments ok."""
    pins_dir = lx.root / "pins"
    names = []
    if series:
        names.append(series)
    names.append("global")
    out, seen = [], set()
    for name in names:
        p = pins_dir / f"{name}.txt"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            t = line.split("#", 1)[0].strip()
            if not t or t in seen:
                continue
            seen.add(t)
            out.append(t)
    return out

def _term_freq(repo_root: pathlib.Path, terms: set[str]) -> dict[str, int]:
    """Count term occurrences in sample ASR transcripts (if present)."""
    counts: collections.Counter[str] = collections.Counter()
    files: list[pathlib.Path] = []
    for pattern in (
        "eval/asr/**/*.txt",
        "eval/asr/out/*.txt",
        "eval/asr/*.txt",
    ):
        files.extend(repo_root.glob(pattern))
    ab = pathlib.Path("/workspace/asr-bench/out")
    if ab.is_dir():
        files.extend(ab.glob("*.paraformer*.txt"))
    seen_files: set[pathlib.Path] = set()
    for f in files:
        try:
            f = f.resolve()
        except OSError:
            continue
        if not f.is_file() or f in seen_files:
            continue
        seen_files.add(f)
        try:
            body = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for t in terms:
            n = body.count(t)
            if n:
                counts[t] += n
    return dict(counts)

def hotwords(lx: Lexicon, entries, series: str | None, freq: dict[str, int] | None = None):
    """Rank: pins first (file order), then frequency desc, then priority/category; cap 50; len 2–8; no six_channel/1-char."""
    hc = lx.config.get("hotword", {})
    cap, lo, hi = hc.get("max_per_series", 50), hc.get("min_len", 2), hc.get("max_len", 8)
    bad = {r["from"] for r in lx.correction_rules(entries) if r.get("type") != "regex"}
    freq = freq or {}
    pins = _load_pins(lx, series)

    eligible = {}
    for e in entries:
        if not e.get("hotword", True) or e["category"] in ("six_channel", "clause"):
            continue
        t = e["term"]
        if not (lo <= len(t) <= hi) or t in bad:
            continue
        sc = e.get("hotword_scope", [])
        if series is None:
            if "global" not in sc:
                continue
            specific = 1
        else:
            if series not in sc and "global" not in sc:
                continue
            specific = 0 if series in sc else 1
        eligible[t] = (e, specific)

    # Allow pins that are not in lexicon entries (still valid ASR bias terms)
    pin_ok = []
    for t in pins:
        if not (lo <= len(t) <= hi) or t in bad:
            continue
        pin_ok.append(t)

    seen, out = set(), []
    for t in pin_ok:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)

    # Remaining candidates sorted by (-freq, priority rank, category, term)
    rest = []
    for t, (e, specific) in eligible.items():
        if t in seen:
            continue
        # rank: lower is better. Use -freq so higher freq sorts first via key.
        pri = 2 * e.get("hotword_priority", 2) + specific
        rest.append((-freq.get(t, 0), pri, CAT_ORDER.index(e["category"]), t))
    rest.sort()
    for item in rest:
        t = item[-1]
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out[:cap], max(0, len(out) - cap)

def build(lx: Lexicon, dist: pathlib.Path, repo_root: pathlib.Path | None = None) -> dict:
    if lx.errors:
        raise SystemExit("lexicon has validation errors:\n  " + "\n  ".join(lx.errors[:50]))
    ents = selected(lx)
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "hotwords").mkdir(exist_ok=True)
    ver = f"{lx.version}#{lx.content_hash()}"
    repo_root = repo_root or lx.root.parent

    # Precompute frequency over all candidate terms (once)
    all_terms = {e["term"] for e in ents if e.get("hotword", True) and e["category"] not in ("six_channel", "clause")}
    for sname in [None, *lx.config.get("hotword", {}).get("series", [])]:
        for t in _load_pins(lx, sname):
            all_terms.add(t)
    freq = _term_freq(repo_root, all_terms)

    # lexicon.jsonl
    allents = ents + clause_entities(lx)
    with open(dist / "lexicon.jsonl", "w") as f:
        for e in allents:
            f.write(json.dumps({**e, "lexicon_ver": ver}, ensure_ascii=False) + "\n")
    # corrections.json
    rules = lx.correction_rules(ents)
    protected = sorted({s for e in ents for s in [e["term"], *e.get("aliases", [])] if len(s) >= 2})
    (dist / "corrections.json").write_text(json.dumps({"lexicon_ver": ver, "apply_after": "opencc_t2s", "rules": rules,
                                                        "protected_surfaces": protected}, ensure_ascii=False, indent=1))
    # hotwords
    manifest = {}
    for sname in [None, *lx.config.get("hotword", {}).get("series", [])]:
        words, dropped = hotwords(lx, ents, sname, freq=freq)
        name = sname or "global"
        (dist / "hotwords" / f"{name}.txt").write_text("\n".join(words) + "\n")
        pin_hits = [w for w in words if w in set(_load_pins(lx, sname))]
        manifest[name] = {"count": len(words), "dropped_over_cap": dropped, "pins_in_list": len(pin_hits),
                          "freq_nonzero": sum(1 for w in words if freq.get(w, 0) > 0)}
    # jieba user dict: "word freq tag"
    lines, seen = [], set()
    for e in ents:
        for s in [e["term"], *e.get("aliases", [])]:
            if len(s) < 2 or s in seen or e.get("match_policy") == "never":
                continue
            seen.add(s)
            lines.append(f"{s} {2000 if len(s) >= 3 else 1000} {JIEBA_TAG[e['category']]}")
    (dist / "jieba_userdict.txt").write_text("\n".join(lines) + "\n")
    counts = {}
    for e in allents:
        counts[e["category"]] = counts.get(e["category"], 0) + 1
    info = {"lexicon_ver": ver, "built_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "min_status": lx.config.get("min_status"), "entries": len(ents), "clauses": len(allents) - len(ents),
            "counts": counts, "correction_rules": len(rules), "hotwords": manifest, "jieba_terms": len(lines),
            "warnings": len(lx.warnings), "freq_sources_terms": len(freq)}
    (dist / "build_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1))
    (dist / "warnings.txt").write_text("\n".join(lx.warnings) + "\n")
    return info
