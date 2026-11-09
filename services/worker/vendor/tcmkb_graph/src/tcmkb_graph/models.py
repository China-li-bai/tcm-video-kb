"""Relation records aligned with ARCHITECTURE entity_relation, plus cite fields.

Lecture rows can only be ``review_status='candidate'``. ``approved`` is rejected by the model
so a draft run cannot write the retrieval path.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PREDICATES_LECTURE = ("treats", "indicates")
CONF_MIN = 0.90
EVIDENCE_MIN = 12
WINDOW_MIN_S = 15.0


class LectureCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_id: str
    start_s: float
    end_s: float
    quote: str = ""
    title: Optional[str] = None
    t_url: Optional[str] = None
    youtube_t_url: Optional[str] = None
    youtube_id: Optional[str] = None


class CandidateEdge(BaseModel):
    """One lecture edge that passed the hard gate. Never approved."""

    model_config = ConfigDict(extra="forbid")

    subj_id: str
    pred: Literal["treats", "indicates"]
    obj_id: str
    source: Literal["lecture"] = "lecture"
    kp_id: str
    citation: LectureCitation
    confidence: float = Field(ge=CONF_MIN, le=1.0)
    review_status: Literal["candidate"] = "candidate"
    evidence_quote: str
    video_id: str
    statement: str = ""

    @field_validator("evidence_quote")
    @classmethod
    def _evidence(cls, v: str) -> str:
        text = v.strip()
        if len(text) < EVIDENCE_MIN:
            raise ValueError(f"evidence_quote shorter than {EVIDENCE_MIN}")
        return text

    @model_validator(mode="after")
    def _window(self) -> "CandidateEdge":
        span = self.citation.end_s - self.citation.start_s
        if span < WINDOW_MIN_S:
            raise ValueError(f"window {span:.1f}s < {WINDOW_MIN_S:.0f}s")
        return self


class HeldKP(BaseModel):
    """A formula_indication / diagnostic_rule KP that did not become edges."""

    model_config = ConfigDict(extra="forbid")

    kp_id: str
    video_id: str
    kp_type: str
    pred: Literal["treats", "indicates"]
    subj_ids: list[str]
    obj_ids: list[str]
    subj_labels: list[str]
    obj_labels: list[str]
    reasons: list[str]
    confidence: Optional[float] = None
    evidence_quote: str = ""
    statement: str = ""
    citation: Optional[LectureCitation] = None

    @field_validator("reasons")
    @classmethod
    def _reasons(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("held record needs reasons")
        return v
