"""Materialize candidate lecture edges from knowledge points.

Product rules (fixed):

- ``treats`` is 方 → 证, ``indicates`` is 症/脉/舌 → 证, ``composed_of`` is 方 → 药
  and comes from the lexicon, not from this scan.
- Hard gate for every lecture edge: confidence ≥ 0.90, evidence quote ≥ 12
  characters, time window ≥ 15s, both ends are canonical lexicon ids, and an
  ``asr_uncertain`` entity is never an endpoint.
- ``formula_indication`` → ``treats`` is semi-automatic: emit only when the
  pairing is unambiguous (one formula × N syndromes, or N formulas × one
  syndrome). N×M is held for a person (``ambiguous_multi_pair``).
- ``diagnostic_rule`` → ``indicates`` is stricter: one syndrome only (several
  signs share it, equal weight, no primary pattern). Two or more syndromes are
  held (``multi_pattern_unpaired``) instead of a cross product or a ranking.
  Negated statements (不是 / 并非 / 排除 / 不可 / 本无 / …) are held.
- Output ``review_status`` is always ``candidate``. Nothing here is ``approved``,
  and ``retrieval_edges`` returns only approved lecture rows (so this pipeline
  contributes nothing to retrieval).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from tcmkb_core.play import site_watch_url, youtube_t_url

from tcmkb_graph.lexicon_index import Ent, load_lexicon_index
from tcmkb_graph.models import (
    CONF_MIN,
    EVIDENCE_MIN,
    WINDOW_MIN_S,
    CandidateEdge,
    HeldKP,
    LectureCitation,
)

# 从严：整句出现这些字样就不当作「症→证」候选，留给人工拆。
_NEGATION = re.compile(r"不是|并非|排除|不可|本无|不属于|不属|勿以|勿当")
_SIGN_CATEGORIES = frozenset({"symptom", "pulse", "tongue"})


@dataclass
class Materialization:
    edges: list[dict]
    held: list[dict]
    index: dict[str, Ent]
    knowledge_root: Path


def retrieval_edges(edges: list[dict]) -> list[dict]:
    """Lecture rows enter retrieval only after a person sets review_status=approved."""
    return [
        e for e in edges
        if e.get("source") == "lecture" and e.get("review_status") == "approved"
    ]


def materialize(root: Path, *, videos: list[str] | None = None) -> Materialization:
    root = Path(root)
    index = load_lexicon_index(root / "lexicon")
    kroot = root / "data" / "knowledge"
    edges: list[dict] = []
    held: list[dict] = []
    for video_dir in _video_dirs(kroot, videos):
        uncertain = uncertain_ids(video_dir / "entities.jsonl")
        kp_path = video_dir / "knowledge_points.jsonl"
        for line in kp_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                kp = json.loads(line)
            except json.JSONDecodeError:
                continue
            got, held_row = consider_kp(kp, index, uncertain)
            edges.extend(got)
            if held_row:
                held.append(held_row)
    edges.sort(key=lambda e: (e["kp_id"], e["pred"], e["subj_id"], e["obj_id"]))
    held.sort(key=lambda h: h["kp_id"])
    return Materialization(edges=edges, held=held, index=index, knowledge_root=kroot)


def consider_kp(
    kp: dict,
    index: dict[str, Ent],
    uncertain: set[str] | None = None,
) -> tuple[list[dict], dict | None]:
    """Return (candidate edge dicts, held dict or None) for one knowledge point."""
    if not isinstance(kp, dict) or not kp.get("kp_id"):
        return [], None
    kind = kp.get("type")
    blocked = uncertain or set()
    if kind == "formula_indication":
        return _pairs(
            kp, index, blocked,
            pred="treats",
            subj_prefixes=("formula.",),
            subj_categories=frozenset({"formula"}),
        )
    if kind == "diagnostic_rule":
        return _pairs(
            kp, index, blocked,
            pred="indicates",
            subj_prefixes=("symptom.", "pulse.", "tongue."),
            subj_categories=_SIGN_CATEGORIES,
        )
    return [], None


def uncertain_ids(path: Path) -> set[str]:
    """Entity ids flagged asr_uncertain in one episode's entities.jsonl."""
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if '"asr_uncertain": true' not in line and '"asr_uncertain":true' not in line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("asr_uncertain") is True and row.get("entity_id"):
            out.add(str(row["entity_id"]))
    return out


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)


def _video_dirs(kroot: Path, videos: list[str] | None) -> list[Path]:
    if not kroot.is_dir():
        return []
    if videos:
        missing = [v for v in videos if not (kroot / v / "knowledge_points.jsonl").is_file()]
        if missing:
            raise FileNotFoundError(
                "missing knowledge_points.jsonl for: " + ", ".join(missing)
            )
        return [kroot / v for v in videos]
    dirs = [
        p for p in kroot.iterdir()
        if p.is_dir() and not p.name.startswith("_") and (p / "knowledge_points.jsonl").is_file()
    ]
    dirs.sort(key=lambda p: p.name)
    return dirs


def _pairs(
    kp: dict,
    index: dict[str, Ent],
    uncertain: set[str],
    *,
    pred: str,
    subj_prefixes: tuple[str, ...],
    subj_categories: frozenset[str],
) -> tuple[list[dict], dict | None]:
    ents = [e for e in (kp.get("entity_ids") or []) if isinstance(e, str)]
    raw_subj = _dedupe([e for e in ents if _prefixed(e, subj_prefixes)])
    raw_obj = _dedupe([e for e in ents if _prefixed(e, ("syndrome.",))])
    if not raw_subj or not raw_obj:
        return [], None

    ok_subj, notes_subj = _canon(raw_subj, index, uncertain, subj_categories)
    ok_obj, notes_obj = _canon(raw_obj, index, uncertain, frozenset({"syndrome"}))
    reasons = _gate_reasons(kp)
    if pred == "indicates" and _NEGATION.search(str(kp.get("statement") or "")):
        reasons.append("negation")
    # FI: N formulas × M syndromes is ambiguous. DR: more than one 证 is unpaired
    # (do not rank a single pattern and do not cross-multiply).
    if pred == "treats" and len(ok_subj) > 1 and len(ok_obj) > 1:
        reasons.append("ambiguous_multi_pair")
    if pred == "indicates" and len(ok_obj) > 1:
        reasons.append("multi_pattern_unpaired")

    if not ok_subj or not ok_obj:
        reasons.extend(notes_subj)
        reasons.extend(notes_obj)
        if not reasons:
            reasons.append("no_canonical_endpoint")
        return [], _held(kp, index, pred, ok_subj or raw_subj, ok_obj or raw_obj, _dedupe(reasons))

    if reasons:
        reasons.extend(notes_subj)
        reasons.extend(notes_obj)
        return [], _held(kp, index, pred, ok_subj, ok_obj, _dedupe(reasons))

    edges = [_edge(kp, pred, subj, obj) for subj in ok_subj for obj in ok_obj]
    return edges, None


def _canon(
    ids: list[str],
    index: dict[str, Ent],
    uncertain: set[str],
    allowed: frozenset[str],
) -> tuple[list[str], list[str]]:
    ok: list[str] = []
    notes: list[str] = []
    for eid in ids:
        if eid.startswith("new.") or eid not in index:
            notes.append(f"non_canonical:{eid}")
            continue
        if eid in uncertain:
            notes.append(f"asr_uncertain:{eid}")
            continue
        cat = index[eid].category
        if cat not in allowed:
            notes.append(f"category:{eid}:{cat}")
            continue
        ok.append(eid)
    return ok, notes


def _gate_reasons(kp: dict) -> list[str]:
    reasons: list[str] = []
    try:
        conf = float(kp.get("confidence"))
    except (TypeError, ValueError):
        conf = -1.0
    if conf < CONF_MIN:
        reasons.append(f"confidence {conf:.2f} < {CONF_MIN:.2f}")
    quote = str(kp.get("evidence_quote") or "").strip()
    if len(quote) < EVIDENCE_MIN:
        reasons.append(f"evidence {len(quote)} < {EVIDENCE_MIN}")
    try:
        window = float(kp["end_s"]) - float(kp["start_s"])
    except (KeyError, TypeError, ValueError):
        window = -1.0
    if window < WINDOW_MIN_S:
        reasons.append(f"window {window:.1f}s < {WINDOW_MIN_S:.0f}s")
    return reasons


def _labels(ids: list[str], index: dict[str, Ent]) -> list[str]:
    return [index[i].term if i in index else i for i in ids]


def _held(
    kp: dict,
    index: dict[str, Ent],
    pred: str,
    subj_ids: list[str],
    obj_ids: list[str],
    reasons: list[str],
) -> dict:
    try:
        conf: float | None = float(kp.get("confidence"))
    except (TypeError, ValueError):
        conf = None
    row = HeldKP(
        kp_id=str(kp["kp_id"]),
        video_id=str(kp.get("video_id") or ""),
        kp_type=str(kp.get("type") or ""),
        pred=pred,  # type: ignore[arg-type]
        subj_ids=list(subj_ids),
        obj_ids=list(obj_ids),
        subj_labels=_labels(subj_ids, index),
        obj_labels=_labels(obj_ids, index),
        reasons=reasons,
        confidence=conf,
        evidence_quote=str(kp.get("evidence_quote") or "").strip(),
        statement=str(kp.get("statement") or ""),
        citation=_citation(kp),
    )
    return row.model_dump(mode="json")


def _edge(kp: dict, pred: str, subj: str, obj: str) -> dict:
    edge = CandidateEdge(
        subj_id=subj,
        pred=pred,  # type: ignore[arg-type]
        obj_id=obj,
        kp_id=str(kp["kp_id"]),
        citation=_citation(kp),
        confidence=float(kp["confidence"]),
        evidence_quote=str(kp.get("evidence_quote") or ""),
        video_id=str(kp.get("video_id") or ""),
        statement=str(kp.get("statement") or ""),
    )
    return edge.model_dump(mode="json")


def _citation(kp: dict) -> LectureCitation:
    cit = kp.get("citation") if isinstance(kp.get("citation"), dict) else {}
    video_id = str(kp.get("video_id") or "")
    try:
        start = float(kp.get("start_s"))
    except (TypeError, ValueError):
        start = 0.0
    try:
        end = float(kp.get("end_s"))
    except (TypeError, ValueError):
        end = start
    yt = cit.get("youtube_id") or None
    if yt is not None:
        yt = str(yt)
    return LectureCitation(
        video_id=video_id,
        start_s=start,
        end_s=end,
        quote=str(kp.get("evidence_quote") or "").strip(),
        title=(str(cit["title"]) if cit.get("title") else None),
        t_url=site_watch_url(video_id, start, end=end) if video_id else None,
        youtube_t_url=youtube_t_url(yt, start) if yt else None,
        youtube_id=yt,
    )


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _prefixed(eid: str, prefixes: tuple[str, ...]) -> bool:
    """Lexicon ids and ``new.<same-prefix>`` attempts (the latter fail the canonical gate)."""
    return any(eid.startswith(p) or eid.startswith("new." + p) for p in prefixes)
