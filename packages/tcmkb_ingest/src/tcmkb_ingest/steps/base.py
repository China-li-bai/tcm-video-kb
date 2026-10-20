"""Shared step context helpers."""
from __future__ import annotations
import pathlib
from dataclasses import dataclass, field
from typing import Any
from tcmkb_core.config import repo_root, load_pipeline_config, load_asr_config, load_series_config
from tcmkb_core.storage import LocalStorage
from tcmkb_core.ids import version_key, content_hash
from tcmkb_core.logging_util import get_logger
from tcmkb_ingest.state import StateDB
from tcmkb_ingest import artifacts as art

log = get_logger("tcmkb.ingest")

@dataclass
class Ctx:
    root: pathlib.Path
    video_id: str
    pipeline: dict[str, Any]
    asr: dict[str, Any]
    series: dict[str, Any]
    state: StateDB
    storage: LocalStorage
    artifacts_base: pathlib.Path
    force: bool = False
    from_cache: bool = False
    skip_alt: bool = True
    cache_dir: pathlib.Path | None = None
    extras: dict[str, Any] = field(default_factory=dict)
    # Shared ASR engine (batch: one model load for all videos); None -> module cache
    engine: Any = None
    worker_id: str = "local"

    @classmethod
    def build(cls, video_id: str, *, force: bool = False, from_cache: bool = False,
              skip_alt: bool = True, cache_dir: str | None = None,
              root: pathlib.Path | None = None, engine: Any = None) -> "Ctx":
        root = root or repo_root()
        pipe = load_pipeline_config(root)
        data = root / pipe.get("data_dir", "data")
        data.mkdir(parents=True, exist_ok=True)
        state = StateDB(root / pipe.get("state_db", "data/state.sqlite"))
        storage = LocalStorage(root / pipe.get("r2_mirror", "data/r2-mirror"))
        abase = root / pipe.get("artifacts_dir", "data/artifacts")
        abase.mkdir(parents=True, exist_ok=True)
        cd = pathlib.Path(cache_dir) if cache_dir else pathlib.Path("/workspace/asr-bench/out")
        return cls(
            root=root, video_id=video_id, pipeline=pipe,
            asr=load_asr_config(root), series=load_series_config(root),
            state=state, storage=storage, artifacts_base=abase,
            force=force, from_cache=from_cache, skip_alt=skip_alt, cache_dir=cd,
            engine=engine,
        )

    def step_cfg(self, step: str) -> dict[str, Any]:
        return dict(self.pipeline.get("steps", {}).get(step, {}) or {})

    def code_version(self, step: str) -> str:
        return str(self.step_cfg(step).get("code_version", "1"))

    def lexicon_hash(self) -> str:
        bi = self.root / "lexicon" / "dist" / "build_info.json"
        if bi.exists():
            import json
            ver = json.loads(bi.read_text(encoding="utf-8")).get("lexicon_ver", "")
            return content_hash(ver)
        return ""

    def active_outdir(self, step: str) -> pathlib.Path | None:
        m = self.state.get_video(self.video_id)
        if not m:
            return None
        vk = m.active_versions.get(step)
        if not vk:
            return None
        d = self.artifacts_base / self.video_id / step / vk
        return d if d.is_dir() else None

    def compute_vk(self, step: str, config_fragment: Any = None, upstream_hash: str = "",
                   lexicon_hash: str = "") -> str:
        return version_key(step, self.code_version(step), config_fragment,
                           upstream_hash=upstream_hash, lexicon_hash=lexicon_hash)

    def outdir(self, step: str, vk: str) -> pathlib.Path:
        return art.artifact_dir(self.artifacts_base, self.video_id, step, vk)
