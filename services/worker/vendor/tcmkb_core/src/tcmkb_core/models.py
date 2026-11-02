"""Pydantic models matching ARCHITECTURE.md §6 (MVP subset)."""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field

class VideoManifest(BaseModel):
    video_id: str
    series_id: str
    episode: int = 0
    title: str = ""
    source_path: str
    source_sha256: str
    source_bytes: int = 0
    duration_s: float = 0.0
    r2_source_key: Optional[str] = None
    r2_play_key: Optional[str] = None
    r2_audio_key: Optional[str] = None
    active_versions: dict[str, str] = Field(default_factory=dict)
    ext: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)

class StepRun(BaseModel):
    video_id: str
    step: str
    version_key: str
    status: str = "pending"  # pending|running|done|failed|skipped
    attempt: int = 0
    worker_id: Optional[str] = None
    lease_until: Optional[str] = None
    input_hash: Optional[str] = None
    output_uri: Optional[str] = None
    output_hash: Optional[str] = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

class TokenSpan(BaseModel):
    t: str
    s: float  # start seconds
    e: float  # end seconds

class Segment(BaseModel):
    video_id: str
    seq: int
    start_s: float
    end_s: float
    text: str
    text_raw: str
    edits: list[dict[str, Any]] = Field(default_factory=list)
    alt_text: Optional[str] = None
    agreement: Optional[float] = None
    review_flag: bool = False

class Chapter(BaseModel):
    seq: int
    title: str
    start_s: float
    end_s: float
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    clause_refs: list[str] = Field(default_factory=list)
    node_id: Optional[str] = None
    review_status: str = "auto"
