"""YAML config loaders."""
from __future__ import annotations
import os, pathlib
from typing import Any
import yaml

def repo_root(start: str | pathlib.Path | None = None) -> pathlib.Path:
    """Walk up from start (or this file) to find the monorepo root (has lexicon/ + packages/)."""
    if start is None:
        p = pathlib.Path(__file__).resolve()
    else:
        p = pathlib.Path(start).resolve()
    if p.is_file():
        p = p.parent
    for cur in [p, *p.parents]:
        if (cur / "lexicon").is_dir() and (cur / "packages").is_dir():
            return cur
    env = os.environ.get("TCMKB_ROOT")
    if env:
        return pathlib.Path(env).resolve()
    return pathlib.Path.cwd()

def _load_yaml(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}

def load_pipeline_config(root: pathlib.Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    return _load_yaml(root / "configs" / "pipeline.yaml")

def load_series_config(root: pathlib.Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    return _load_yaml(root / "configs" / "series.yaml")

def load_asr_config(root: pathlib.Path | None = None) -> dict[str, Any]:
    root = root or repo_root()
    return _load_yaml(root / "configs" / "asr.yaml")

def data_dir(root: pathlib.Path | None = None) -> pathlib.Path:
    root = root or repo_root()
    d = root / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d
