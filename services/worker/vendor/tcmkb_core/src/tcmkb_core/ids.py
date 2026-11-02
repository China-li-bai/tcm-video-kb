"""ID and version_key helpers."""
from __future__ import annotations
import hashlib, json
from typing import Any

def video_id(series_id: str, episode: int) -> str:
    return f"{series_id}-{episode:03d}"

def chapter_id(vid: str, seq: int) -> str:
    return f"{vid}:c{seq:02d}"

def version_key(
    step_name: str,
    step_code_version: str,
    config_fragment: Any = None,
    upstream_hash: str = "",
    lexicon_hash: str = "",
) -> str:
    """Stable 12-char sha1 of step identity + config + upstream + lexicon."""
    payload = {
        "step": step_name,
        "code": step_code_version,
        "config": config_fragment if config_fragment is not None else {},
        "upstream": upstream_hash or "",
        "lexicon": lexicon_hash or "",
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:12]

def sha256_file(path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
