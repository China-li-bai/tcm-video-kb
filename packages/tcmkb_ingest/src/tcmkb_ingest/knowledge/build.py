"""Annotations (reader output) -> validated chapters / entities / knowledge points.

Deterministic: resolves segment seq -> timestamps, builds site /watch citations, merges
chapters across windows, adds lexicon mentions, dedupes knowledge points, validates
everything against tcmkb_core.knowledge and writes data/knowledge/<video_id>/.
"""
from __future__ import annotations
import difflib, hashlib, json, pathlib, re
from dataclasses import dataclass, field
from typing import Any

import yaml

from tcmkb_core.knowledge import (
    ENTITY_TYPES, KP_TYPE_LABEL_ZH, TYPE_LABEL_ZH, SCHEMA_VERSION, AnnChapter, AnnKP, Annotation,
    KChapter, KCitation, KEntity, KMention, KnowledgePoint, t_url, youtube_t_url,
)
from tcmkb_ingest import artifacts as art
from tcmkb_ingest.knowledge.chunk import hms
from tcmkb_ingest.knowledge.episode import Episode, load_episode
from tcmkb_ingest.knowledge.lexmatch import Lexicon, _norm, segment_mentions
from tcmkb_lexicon.match import Matcher


class KnowledgeBuildError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__(f"{len(errors)} knowledge build error(s):\n  " + "\n  ".join(errors[:50]))
        self.errors = errors


def load_config(root: pathlib.Path) -> dict[str, Any]:
    p = root / "configs" / "knowledge.yaml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.exists() else {}


def knowledge_dir(root: pathlib.Path, video_id: str) -> pathlib.Path:
    return root / "data" / "knowledge" / video_id


def load_annotations(kdir: pathlib.Path) -> list[Annotation]:
    out = []
    for p in sorted((kdir / "annotations").glob("*.yaml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            out.append(Annotation.model_validate(data))
        except Exception as e:  # pydantic ValidationError: name the file
            raise KnowledgeBuildError([f"{p.name}: {e}"]) from e
    return out


def citation(ep: Episode, start_s: float, end_s: float) -> KCitation:
    start_s, end_s = round(float(start_s), 2), round(float(end_s), 2)   # url from the stored value
    return KCitation(
        video_id=ep.video_id, youtube_id=ep.youtube_id,
        url=t_url(ep.video_id, start_s), youtube_t_url=youtube_t_url(ep.youtube_id, start_s),
        series=ep.series, episode=ep.episode, title=ep.title, start_s=start_s, end_s=end_s,
    )


# ------------------------------------------------------------------ entity id helpers
class EntityResolver:
    """Lexicon ids + `new.<type>.<name>` ids, with knowledge.yaml alias supplements."""

    def __init__(self, lx: Lexicon, aliases: dict[str, str] | None = None,
                 context_required: dict[str, list[str]] | None = None,
                 exclude_auto: list[str] | None = None):
        self.lx = lx
        self.exclude_auto = set(exclude_auto or [])
        self.aliases = {k: v for k, v in (aliases or {}).items() if v in lx.by_id}
        extra = [{"id": v, "term": k, "category": lx.by_id[v]["category"], "match_policy": "always"}
                 for k, v in self.aliases.items()]
        self.alias_matcher = Matcher(extra) if extra else None
        self.context_required = context_required or {}

    def validate(self, eid: str) -> str | None:
        """Error string, or None when the id is usable."""
        if eid in self.lx.by_id:
            return None
        if eid.startswith("new."):
            parts = eid.split(".", 2)
            if len(parts) == 3 and parts[1] in ENTITY_TYPES and parts[2]:
                return None
            return f"bad new-entity id {eid!r} (want new.<type>.<name>, type in {ENTITY_TYPES})"
        return f"unknown entity id {eid!r} (not in lexicon; use new.<type>.<name>)"

    def type_of(self, eid: str) -> str:
        return self.lx.type_of(eid) or "concept"

    def canonical(self, eid: str) -> str:
        return self.lx.canonical(eid) or eid

    def mentions(self, seg: dict[str, Any]) -> list[dict[str, Any]]:
        ms = segment_mentions(self.lx, seg)
        if self.alias_matcher:
            taken = {m["corrected"] for m in ms}
            for h in self.alias_matcher.find(seg["text"]):
                if h["surface"] not in taken and not any(h["surface"] in t for t in taken):
                    ms.append({"entity_id": h["ids"][0], "corrected": h["surface"], "surface": h["surface"],
                               "seq": seg["seq"], "ambiguous": []})
        out = []
        for m in ms:
            if m["entity_id"] in self.exclude_auto:
                continue
            need = self.context_required.get(self.type_of(m["entity_id"]))
            if need:
                t = seg["text"]
                i = t.find(m["corrected"])
                around = t[max(0, i - 8): i + len(m["corrected"]) + 8]
                if not any(c in around for c in need):
                    continue
            out.append(m)
        return out


# ------------------------------------------------------------------ chapters
def build_chapters(ep: Episode, anns: list[Annotation], res: EntityResolver,
                   errors: list[str]) -> tuple[list[KChapter], dict[str, str]]:
    seqs = [s["seq"] for s in ep.segments]
    first, last = seqs[0], seqs[-1]
    by_seq = ep.by_seq
    merged: dict[str, AnnChapter] = {}
    for a in anns:
        for c in a.chapters:
            if c.key in merged:
                m = merged[c.key]
                m.start_seq = min(m.start_seq, c.start_seq)
                if c.end_seq is not None:
                    m.end_seq = max(m.end_seq or c.end_seq, c.end_seq)
                m.summary = m.summary or c.summary
                m.clauses = sorted(set(m.clauses) | set(c.clauses))
                m.topics = list(dict.fromkeys([*m.topics, *c.topics]))
            else:
                merged[c.key] = c.model_copy(deep=True)
    tops = sorted([c for c in merged.values() if not c.parent], key=lambda c: c.start_seq)
    if not tops:
        errors.append("no chapters annotated")
        return [], {}
    tops[0].start_seq = min(tops[0].start_seq, first)

    def nearest(seq: int) -> int:          # snap to an existing segment seq
        if seq in by_seq:
            return seq
        return min(seqs, key=lambda s: abs(s - seq))

    out: list[KChapter] = []
    keymap: dict[str, str] = {}

    def mk(c: AnnChapter, cid: str, level: int, parent: str | None, a: int, b: int, n: int) -> KChapter:
        six = [t for t in c.topics if t.startswith("six_channel.")]
        clause_ids = []
        for no in c.clauses:
            cl = res.lx.clause_id(no)
            if cl:
                clause_ids.append(cl)
                six += [e for e in res.lx.by_id[cl]["attrs"].get("entities") or [] if e.startswith("six_channel.")]
            else:
                errors.append(f"chapter {c.key}: unknown clause number {no}")
        for t in c.topics:
            if (err := res.validate(t)):
                errors.append(f"chapter {c.key}: {err}")
        sa, sb = by_seq[a], by_seq[b]
        if level == 1 and not c.summary.strip():
            errors.append(f"chapter {c.key}: missing summary")
        return KChapter(chapter_id=cid, video_id=ep.video_id, level=level, parent_id=parent, seq=n,
                        title=c.title, summary=c.summary, start_s=sa["start_s"], end_s=sb["end_s"],
                        seg_from=a, seg_to=b, six_channel=list(dict.fromkeys(six)), clause_refs=clause_ids,
                        topics=[t for t in c.topics if not t.startswith("six_channel.")],
                        citation=citation(ep, sa["start_s"], sb["end_s"]))

    for i, c in enumerate(tops):
        a = nearest(c.start_seq)
        nxt = tops[i + 1].start_seq if i + 1 < len(tops) else None
        b = c.end_seq if c.end_seq is not None else (nxt - 1 if nxt is not None else last)
        if nxt is not None and b >= nxt:
            errors.append(f"chapter {c.key} overlaps next chapter ({b} >= {nxt})")
        b = nearest(max(b, a))
        cid = f"{ep.video_id}.c{i + 1:02d}"
        ch = mk(c, cid, 1, None, a, b, i + 1)
        out.append(ch)
        keymap[c.key] = cid
        subs = sorted([s for s in merged.values() if s.parent == c.key], key=lambda s: s.start_seq)
        for j, s in enumerate(subs):
            sa_ = nearest(max(s.start_seq, a))
            nx = subs[j + 1].start_seq if j + 1 < len(subs) else None
            sb_ = s.end_seq if s.end_seq is not None else (nx - 1 if nx is not None else b)
            sb_ = nearest(min(max(sb_, sa_), b))
            sid = f"{cid}.s{j + 1}"
            out.append(mk(s, sid, 2, cid, sa_, sb_, j + 1))
            keymap[s.key] = sid
    orphans = [c.key for c in merged.values() if c.parent and c.parent not in keymap]
    if orphans:
        errors.append(f"sections with unknown parent: {orphans}")
    return out, keymap


def chapter_for(chapters: list[KChapter], seq: int, deepest: bool = True) -> KChapter | None:
    hits = [c for c in chapters if c.seg_from <= seq <= c.seg_to]
    if not hits:
        return None
    return max(hits, key=lambda c: c.level) if deepest else min(hits, key=lambda c: c.level)


# ------------------------------------------------------------------ entities
def build_entities(ep: Episode, anns: list[Annotation], chapters: list[KChapter], res: EntityResolver,
                   kp_entities: dict[str, int], max_mentions: int, errors: list[str]) -> list[KEntity]:
    by_seq = ep.by_seq
    ments: dict[str, list[KMention]] = {}

    def add(eid: str, seq: int, surface: str, corrected: str, source: str, uncertain: bool = False,
            dosage: str | None = None) -> None:
        s = by_seq.get(seq)
        if s is None:
            errors.append(f"entity {eid}: seq {seq} not in transcript")
            return
        ch = chapter_for(chapters, seq)
        ments.setdefault(eid, []).append(KMention(
            surface=surface, corrected=corrected or surface, seq=seq, start_s=s["start_s"], end_s=s["end_s"],
            url=t_url(ep.video_id, s["start_s"]), chapter_id=ch.chapter_id if ch else None,
            source=source, asr_uncertain=uncertain, dosage=dosage))

    rejected = {(e.id, e.seq) for a in anns for e in a.entities if e.reject}
    for s in ep.segments:
        for m in res.mentions(s):
            if (m["entity_id"], s["seq"]) not in rejected:
                add(m["entity_id"], s["seq"], m["surface"], m["corrected"], "lexicon")
    notes: dict[str, str] = {}
    for a in anns:
        for e in a.entities:
            if e.reject:
                continue
            if (err := res.validate(e.id)):
                errors.append(f"{a.window} entity: {err}")
                continue
            if e.type and e.type != res.type_of(e.id):
                errors.append(f"{a.window} entity {e.id}: type {e.type} != {res.type_of(e.id)}")
            add(e.id, e.seq, e.surface, e.corrected or res.canonical(e.id), "llm_read", e.uncertain, e.dosage)
            if e.note:
                notes.setdefault(e.id, e.note)
    for eid, seq in kp_entities.items():          # entities only implied by a knowledge point
        if eid not in ments and not res.validate(eid):
            c = res.canonical(eid)
            add(eid, seq, c, c, "llm_read")

    out = []
    for eid, ms in ments.items():
        ms.sort(key=lambda m: (m.start_s, m.source != "llm_read"))
        # one mention per (seq, corrected): the reader's correction wins over the lexicon hit
        seen, uniq = set(), []
        for m in sorted(ms, key=lambda m: (m.seq, m.source != "llm_read")):
            k = (m.seq, m.corrected, m.dosage)
            if k in seen:
                continue
            seen.add(k)
            uniq.append(m)
        uniq.sort(key=lambda m: m.start_s)
        llm = [m for m in uniq if m.source == "llm_read"]
        keep = sorted({id(m): m for m in [*llm, *uniq][:max_mentions]}.values(), key=lambda m: m.start_s)
        etype = res.type_of(eid)
        out.append(KEntity(
            entity_id=eid, video_id=ep.video_id, type=etype, canonical=res.canonical(eid),
            in_lexicon=eid in res.lx.by_id, surfaces=list(dict.fromkeys(m.surface for m in uniq)),
            n_mentions=len(uniq), first_start_s=uniq[0].start_s, first_url=uniq[0].url,
            dosages=list(dict.fromkeys(m.dosage for m in uniq if m.dosage)), mentions=keep,
            asr_uncertain=bool(uniq) and all(m.asr_uncertain for m in uniq if m.source == "llm_read")
            and any(m.source == "llm_read" for m in uniq) and not any(m.source == "lexicon" for m in uniq),
            note=notes.get(eid, "")))
    out.sort(key=lambda e: (ENTITY_TYPES.index(e.type), -e.n_mentions, e.entity_id))
    return out


# ------------------------------------------------------------------ knowledge points
@dataclass
class _KP:
    ann: AnnKP
    window: str
    a: int
    b: int
    chapter: KChapter
    entity_ids: list[str] = field(default_factory=list)


def quote_ok(ep: Episode, q: str, a: int, b: int, slack: int = 1) -> bool:
    segs = [s for s in ep.segments if a - slack <= s["seq"] <= b + slack]
    return _norm(q) in _norm("".join(s["text"] for s in segs))


def dedupe(kps: list[_KP], ratio: float) -> list[_KP]:
    """Same top chapter + same type + similar statement -> one KP (higher confidence wins)."""
    out: list[_KP] = []
    for k in sorted(kps, key=lambda k: (k.a, -k.ann.conf)):
        dup = None
        for o in out:
            if o.ann.type == k.ann.type and (o.chapter.parent_id or o.chapter.chapter_id) == \
                    (k.chapter.parent_id or k.chapter.chapter_id):
                if difflib.SequenceMatcher(None, o.ann.s, k.ann.s).ratio() >= ratio:
                    dup = o
                    break
        if dup is None:
            out.append(k)
            continue
        if k.ann.conf > dup.ann.conf:
            dup.ann, dup.window = k.ann, k.window
        dup.a, dup.b = min(dup.a, k.a), max(dup.b, k.b)
        dup.entity_ids = list(dict.fromkeys([*dup.entity_ids, *k.entity_ids]))
    return out


def build_kps(ep: Episode, anns: list[Annotation], chapters: list[KChapter], keymap: dict[str, str],
              res: EntityResolver, ratio: float, errors: list[str]) -> list[KnowledgePoint]:
    by_seq, by_id = ep.by_seq, {c.chapter_id: c for c in chapters}
    raw: list[_KP] = []
    for a in anns:
        for i, k in enumerate(a.kps):
            tag = f"{a.window}.kp[{i}]"
            lo, hi = k.seq[0], k.seq[-1]
            if lo not in by_seq or hi not in by_seq:
                errors.append(f"{tag}: seq {k.seq} not in transcript")
                continue
            if not quote_ok(ep, k.q, lo, hi):
                errors.append(f"{tag}: evidence quote {k.q!r} not found in seq {lo}-{hi}")
            ents = []
            for eid in k.ents:
                if (err := res.validate(eid)):
                    errors.append(f"{tag}: {err}")
                else:
                    ents.append(eid)
            if k.ch:
                ch = by_id.get(keymap.get(k.ch, ""))
                if ch is None:
                    errors.append(f"{tag}: unknown chapter key {k.ch!r}")
                    continue
            else:
                ch = chapter_for(chapters, lo)
                if ch is None:
                    errors.append(f"{tag}: seq {lo} outside all chapters")
                    continue
            raw.append(_KP(k, a.window, lo, hi, ch, ents))
    kept = dedupe(raw, ratio)
    kept.sort(key=lambda k: (by_seq[k.a]["start_s"], k.b))
    out = []
    for n, k in enumerate(kept, 1):
        sa, sb = by_seq[k.a], by_seq[k.b]
        try:
            out.append(KnowledgePoint(
                kp_id=f"{ep.video_id}.kp{n:04d}", video_id=ep.video_id, type=k.ann.type, statement=k.ann.s,
                entity_ids=k.entity_ids, chapter_id=k.chapter.chapter_id, evidence_quote=k.ann.q,
                seg_from=k.a, seg_to=k.b, start_s=sa["start_s"], end_s=sb["end_s"],
                citation=citation(ep, sa["start_s"], sb["end_s"]), confidence=k.ann.conf, asr_note=k.ann.asr))
        except Exception as e:
            errors.append(f"{k.window} kp {k.ann.s[:20]!r}: {e}")
    return out


# ------------------------------------------------------------------ outline
def render_outline(ep: Episode, chapters: list[KChapter], kps: list[KnowledgePoint],
                   entities: list[KEntity]) -> str:
    def link(t: float) -> str:
        u = t_url(ep.video_id, t)
        return f"[{hms(t)}]({u})" if u else hms(t)

    def clauses(c: KChapter) -> str:
        nos = [str(int(x.rsplit(".", 1)[1])) for x in c.clause_refs]
        return f"（条文 {'、'.join(nos)}）" if nos else ""

    lines = [f"# {ep.title}", "",
             f"- 视频：{t_url(ep.video_id, 0) or ep.video_id}　系列 `{ep.series}` 第 {ep.episode} 集　"
             f"时长 {hms(ep.duration_s)}",
             f"- 章节 {sum(1 for c in chapters if c.level == 1)}，小节 {sum(1 for c in chapters if c.level == 2)}，"
             f"知识点 {len(kps)}，实体 {len(entities)}（schema `{SCHEMA_VERSION}`，由转写阅读生成，ASR 有误差，引用前请点链接核对）",
             "", "## 章节目录", ""]
    for c in chapters:
        ind = "  " if c.level == 2 else ""
        num = c.chapter_id.split(".", 1)[1]
        lines.append(f"{ind}- {link(c.start_s)} **{num} {c.title}**{clauses(c)} — {c.summary}")
    lines += ["", "## 知识点（按章节）", ""]
    tops = [c for c in chapters if c.level == 1]
    for t in tops:
        mine = [k for k in kps if k.chapter_id == t.chapter_id or k.chapter_id.startswith(t.chapter_id + ".")]
        if not mine:
            continue
        lines.append(f"### {t.chapter_id.split('.', 1)[1]} {t.title}")
        for k in mine:
            lines.append(f"- {link(k.start_s)} 〔{KP_TYPE_LABEL_ZH[k.type]}〕{k.statement}"
                         f"　<sub>{k.kp_id} · 「{k.evidence_quote}」 · 置信 {k.confidence:.2f}</sub>")
        lines.append("")
    lines += ["## 实体索引（前 10 个提及最多的类型内条目）", ""]
    for et in ENTITY_TYPES:
        es = [e for e in entities if e.type == et]
        if not es:
            continue
        top = sorted(es, key=lambda e: -e.n_mentions)[:10]
        items = "、".join(f"[{e.canonical}]({e.first_url})×{e.n_mentions}" if e.first_url else e.canonical
                         for e in top)
        lines.append(f"- **{TYPE_LABEL_ZH[et]}**（{len(es)}）：{items}")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ driver
def build(root: pathlib.Path, video_id: str, *, strict: bool = True) -> dict[str, Any]:
    cfg = load_config(root)
    ep = load_episode(root, video_id)
    kdir = knowledge_dir(root, video_id)
    anns = load_annotations(kdir)
    if not anns:
        raise KnowledgeBuildError([f"{video_id}: no annotations in {kdir / 'annotations'}"])
    lx = Lexicon(root)
    res = EntityResolver(lx, cfg.get("aliases") or {}, cfg.get("context_required") or {},
                         cfg.get("exclude_auto") or [])
    errors: list[str] = []
    for a in anns:
        if a.video_id != video_id:
            errors.append(f"{a.window}: video_id {a.video_id} != {video_id}")
    chapters, keymap = build_chapters(ep, anns, res, errors)
    kps = build_kps(ep, anns, chapters, keymap, res, float(cfg.get("kp_dedupe_ratio", 0.82)), errors)
    kp_ents: dict[str, int] = {}
    for k in kps:
        for e in k.entity_ids:
            kp_ents.setdefault(e, k.seg_from)
    entities = build_entities(ep, anns, chapters, res, kp_ents, int(cfg.get("max_mentions_per_entity", 30)),
                              errors)
    known = {e.entity_id for e in entities}
    for k in kps:
        missing = [e for e in k.entity_ids if e not in known]
        if missing:
            errors.append(f"{k.kp_id}: entities {missing} missing from entities.jsonl")
    if errors and strict:
        raise KnowledgeBuildError(errors)
    art.atomic_write_text(kdir / "chapters.json", json.dumps(
        [c.model_dump() for c in chapters], ensure_ascii=False, indent=1) + "\n")
    art.atomic_write_text(kdir / "entities.jsonl", "".join(
        json.dumps(e.model_dump(), ensure_ascii=False) + "\n" for e in entities))
    art.atomic_write_text(kdir / "knowledge_points.jsonl", "".join(
        json.dumps(k.model_dump(), ensure_ascii=False) + "\n" for k in kps))
    art.atomic_write_text(kdir / "outline.md", render_outline(ep, chapters, kps, entities))
    by_type: dict[str, int] = {}
    for e in entities:
        by_type[e.type] = by_type.get(e.type, 0) + 1
    kp_type: dict[str, int] = {}
    for k in kps:
        kp_type[k.type] = kp_type.get(k.type, 0) + 1
    h = hashlib.sha256()
    for p in sorted((kdir / "annotations").glob("*.yaml")):
        h.update(p.read_bytes())
    report = {"schema": SCHEMA_VERSION, "video_id": video_id, "youtube_id": ep.youtube_id,
              "windows": [a.window for a in anns], "annotations_sha256": h.hexdigest()[:16],
              "n_segments": len(ep.segments),
              "n_chapters": sum(1 for c in chapters if c.level == 1),
              "n_sections": sum(1 for c in chapters if c.level == 2),
              "n_entities": len(entities), "entities_by_type": by_type,
              "n_new_entities": sum(1 for e in entities if not e.in_lexicon),
              "n_knowledge_points": len(kps), "kp_by_type": kp_type,
              "errors": errors}
    art.atomic_write_json(kdir / "build_report.json", report)
    return report
