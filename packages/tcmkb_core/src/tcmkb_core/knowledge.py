"""Knowledge layer schema (s09_knowledge): chapters, entities, knowledge points.

Outputs per episode (data/knowledge/<video_id>/):
  chapters.json            list[KChapter]            episode > chapter (level 1) > section (level 2)
  entities.jsonl           one KEntity per line      normalized to lexicon ids, with mentions
  knowledge_points.jsonl   one KnowledgePoint/line   atomic, citable claims as taught
  outline.md               chapter list with site /watch/{id}?t= timestamp links
Aggregated: data/knowledge/_index/{entities.csv, knowledge_points.csv}.

The semantic parts (chapter boundaries/titles/summaries, KP statements, ASR-corrected
entity guesses) are written by a reader (human or LLM) as *annotation* files
(`Annotation*` models below, data/knowledge/<id>/annotations/w*.yaml) that reference
transcript segments by `seq`; deterministic code resolves seq -> timestamps, builds
citations, merges windows, dedupes and validates. `python -m tcmkb_core.knowledge`
prints the JSON Schemas.
"""
from __future__ import annotations
import json
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "knowledge/1"
MAX_QUOTE = 40

# Entity types requested for the knowledge layer; lexicon categories map onto them.
EntityType = Literal[
    "formula",      # 方剂
    "herb",         # 中药 (dosage on mentions)
    "symptom",      # 症状
    "pattern",      # 证候 (lexicon: syndrome)
    "disease",      # 病名
    "six_channel",  # 六经
    "meridian",     # 经络
    "acupoint",     # 穴位
    "pulse",        # 脉象
    "tongue",       # 舌象
    "clause",       # 条文 (伤寒论第N条 ...)
    "method",       # 治法
    "person",       # 人物
    "book",         # 典籍 (lexicon: classic)
    "zangfu",       # 脏腑
    "concept",      # 其他中医概念
]
ENTITY_TYPES: tuple[str, ...] = EntityType.__args__  # type: ignore[attr-defined]
LEXICON_CATEGORY_TO_TYPE = {
    "formula": "formula", "herb": "herb", "symptom": "symptom", "syndrome": "pattern",
    "disease": "disease", "six_channel": "six_channel", "meridian": "meridian",
    "acupoint": "acupoint", "pulse": "pulse", "tongue": "tongue", "clause": "clause",
    "method": "method", "person": "person", "classic": "book", "zangfu": "zangfu",
    "concept": "concept",
}
TYPE_LABEL_ZH = {
    "formula": "方剂", "herb": "中药", "symptom": "症状", "pattern": "证候", "disease": "病名",
    "six_channel": "六经", "meridian": "经络", "acupoint": "穴位", "pulse": "脉象", "tongue": "舌象",
    "clause": "条文", "method": "治法", "person": "人物", "book": "典籍", "zangfu": "脏腑",
    "concept": "概念",
}

KPType = Literal[
    "formula_composition",    # 方剂组成/剂量/煎服法
    "formula_indication",     # 方剂主治/方证
    "contraindication",       # 禁忌/误治后果
    "clause_interpretation",  # 条文解读
    "diagnostic_rule",        # 辨证/诊断要点 (脉/舌/症 -> 证)
    "pathomechanism",         # 病机/传变/生理
    "treatment_principle",    # 治则治法
    "herb_property",          # 药性/药效/用药心得
    "acupoint_usage",         # 针灸取穴
    "prognosis",              # 预后/死证/愈期
    "clinical_tip",           # 临床经验/医案要点
    "concept_definition",     # 概念定义
    "study_method",           # 学习方法/课程说明
]
KP_TYPES: tuple[str, ...] = KPType.__args__  # type: ignore[attr-defined]
KP_TYPE_LABEL_ZH = {
    "formula_composition": "方剂组成", "formula_indication": "方证主治", "contraindication": "禁忌误治",
    "clause_interpretation": "条文解读", "diagnostic_rule": "辨证要点", "pathomechanism": "病机传变",
    "treatment_principle": "治则治法", "herb_property": "药性用药", "acupoint_usage": "针灸取穴",
    "prognosis": "预后", "clinical_tip": "临床经验", "concept_definition": "概念定义",
    "study_method": "学习方法",
}


def t_url(video_id: str | None, t: float, *, end: float | None = None, base: str = "") -> str | None:
    """Primary cite: /watch/{video_id}?t=<floor sec> (site deep link)."""
    from tcmkb_core.play import site_watch_url
    return site_watch_url(video_id, t, end=end, base=base)


def youtube_t_url(youtube_id: str | None, t: float) -> str | None:
    """YouTube backup deep link with &t=<floor sec>s."""
    from tcmkb_core.play import youtube_t_url as _yt
    return _yt(youtube_id, t)


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class KCitation(_M):
    video_id: str
    youtube_id: Optional[str] = None
    url: Optional[str] = Field(description="site watch URL /watch/{video_id}?t=<sec>")
    youtube_t_url: Optional[str] = Field(default=None, description="YouTube backup &t= link")
    series: str
    episode: int
    title: str
    start_s: float
    end_s: float

    @model_validator(mode="after")
    def _url_matches(self) -> "KCitation":
        want = t_url(self.video_id, self.start_s)
        if self.url != want:
            raise ValueError(f"citation url {self.url!r} != {want!r}")
        if self.youtube_id and self.youtube_t_url:
            ywant = youtube_t_url(self.youtube_id, self.start_s)
            if self.youtube_t_url != ywant:
                raise ValueError(f"youtube_t_url {self.youtube_t_url!r} != {ywant!r}")
        return self


class KChapter(_M):
    chapter_id: str = Field(description="<video_id>.c<NN> or <video_id>.c<NN>.s<N> for sections")
    video_id: str
    level: Literal[1, 2] = 1
    parent_id: Optional[str] = None
    seq: int
    title: str
    summary: str = Field(description="1-2 sentences, own words")
    start_s: float
    end_s: float
    seg_from: int
    seg_to: int
    six_channel: list[str] = Field(default_factory=list, description="lexicon six_channel ids")
    clause_refs: list[str] = Field(default_factory=list, description="lexicon clause ids, e.g. clause.shl.012")
    topics: list[str] = Field(default_factory=list, description="other entity ids central to the chapter")
    citation: KCitation
    review_status: Literal["auto", "llm_read", "reviewed"] = "llm_read"

    @model_validator(mode="after")
    def _times(self) -> "KChapter":
        if self.end_s < self.start_s or self.seg_to < self.seg_from:
            raise ValueError(f"{self.chapter_id}: end before start")
        if self.level == 2 and not self.parent_id:
            raise ValueError(f"{self.chapter_id}: section without parent_id")
        return self


class KMention(_M):
    surface: str = Field(description="text as it appears in the transcript (ASR)")
    corrected: str = Field(description="ASR-corrected form (== canonical spelling when known)")
    seq: int
    start_s: float
    end_s: float
    url: Optional[str] = None
    chapter_id: Optional[str] = None
    source: Literal["lexicon", "llm_read"] = "lexicon"
    asr_uncertain: bool = False
    dosage: Optional[str] = None


class KEntity(_M):
    entity_id: str = Field(description="lexicon id (e.g. formula.gui_zhi_tang) or new.<type>.<name>")
    video_id: str
    type: EntityType
    canonical: str
    in_lexicon: bool
    surfaces: list[str] = Field(default_factory=list, description="distinct surface forms seen")
    n_mentions: int
    first_start_s: float
    first_url: Optional[str] = None
    dosages: list[str] = Field(default_factory=list, description="herb dosages as stated (e.g. 三两)")
    mentions: list[KMention] = Field(default_factory=list, description="capped list, earliest first")
    asr_uncertain: bool = False
    note: str = ""


class KnowledgePoint(_M):
    kp_id: str = Field(description="<video_id>.kp<NNNN>")
    video_id: str
    type: KPType
    statement: str = Field(description="concise Chinese paraphrase, not verbatim transcript")
    entity_ids: list[str] = Field(default_factory=list)
    chapter_id: str
    evidence_quote: str = Field(description=f"short transcript quote, <= {MAX_QUOTE} chars")
    seg_from: int
    seg_to: int
    start_s: float
    end_s: float
    citation: KCitation
    confidence: float = Field(ge=0.0, le=1.0)
    asr_note: str = ""
    source: Literal["llm_read", "reviewed"] = "llm_read"

    @field_validator("evidence_quote")
    @classmethod
    def _short_quote(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("empty evidence_quote")
        if len(v) > MAX_QUOTE:
            raise ValueError(f"evidence_quote longer than {MAX_QUOTE} chars")
        return v

    @field_validator("statement")
    @classmethod
    def _statement(cls, v: str) -> str:
        if len(v.strip()) < 4:
            raise ValueError("statement too short")
        if len(v) > 160:
            raise ValueError("statement longer than 160 chars: paraphrase, don't paste transcript")
        return v


# ---------------------------------------------------------------- annotation (reader input)
class AnnChapter(_M):
    """A chapter as read from a window. Same `key` in adjacent windows = continuation (merged)."""
    key: str = Field(description="stable slug within the episode, e.g. c03 or c03.s2")
    parent: Optional[str] = Field(default=None, description="parent chapter key for a section")
    title: str
    start_seq: int
    end_seq: Optional[int] = Field(default=None, description="omit: runs until the next chapter")
    summary: str = ""
    clauses: list[int] = Field(default_factory=list, description="伤寒论 clause numbers")
    topics: list[str] = Field(default_factory=list, description="entity ids (six_channel.* go to six_channel)")


class AnnEntity(_M):
    """Entity mention the lexicon pass cannot find by itself: ASR mis-hearing, dosage, new term."""
    id: str = Field(description="lexicon id, or new.<type>.<name> for terms missing from the lexicon")
    seq: int
    surface: str
    corrected: str = ""
    type: Optional[EntityType] = None
    uncertain: bool = False
    dosage: Optional[str] = None
    note: str = ""
    reject: bool = Field(False, description="the lexicon hit of this id at this seq is a false positive "
                                            "(e.g. ASR turned 大青龙 into 大陷胸); drop it")


class AnnKP(_M):
    type: KPType
    s: str = Field(description="statement")
    seq: list[int] = Field(description="[seg_from] or [seg_from, seg_to]")
    q: str = Field(description="evidence quote, substring of the cited segments (ASR text)")
    ents: list[str] = Field(default_factory=list)
    conf: float = Field(default=0.8, ge=0.0, le=1.0)
    asr: str = Field(default="", description="note on ASR corrections used in the statement")
    ch: Optional[str] = Field(default=None, description="chapter key override (default: by seq)")

    @field_validator("seq")
    @classmethod
    def _seq(cls, v: list[int]) -> list[int]:
        if not 1 <= len(v) <= 2 or (len(v) == 2 and v[1] < v[0]):
            raise ValueError(f"bad seq range {v}")
        return v


class Annotation(_M):
    video_id: str
    window: str
    seg_from: int
    seg_to: int
    annotator: str = "llm_read"
    chapters: list[AnnChapter] = Field(default_factory=list)
    entities: list[AnnEntity] = Field(default_factory=list)
    kps: list[AnnKP] = Field(default_factory=list)


def json_schemas() -> dict[str, Any]:
    return {m.__name__: m.model_json_schema() for m in
            (KChapter, KEntity, KnowledgePoint, KCitation, Annotation)}


if __name__ == "__main__":  # pragma: no cover
    print(json.dumps(json_schemas(), ensure_ascii=False, indent=1))
