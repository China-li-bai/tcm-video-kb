"""Atomic artifact writes under data/artifacts/{video_id}/{step}/{version_key}/."""
from __future__ import annotations
import json, hashlib, pathlib, os, tempfile
from typing import Any

def artifact_dir(base: pathlib.Path, video_id: str, step: str, version_key: str) -> pathlib.Path:
    d = base / video_id / step / version_key
    d.mkdir(parents=True, exist_ok=True)
    return d

def atomic_write_bytes(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=path.suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

def atomic_write_text(path: pathlib.Path, text: str, encoding: str = "utf-8") -> None:
    atomic_write_bytes(path, text.encode(encoding))

def atomic_write_json(path: pathlib.Path, obj: Any, indent: int | None = 1) -> None:
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=indent) + "\n")

def write_success(outdir: pathlib.Path, metrics: dict[str, Any], output_hash: str) -> pathlib.Path:
    payload = {"ok": True, "output_hash": output_hash, "metrics": metrics}
    p = outdir / "_SUCCESS.json"
    atomic_write_json(p, payload)
    return p

def hash_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]

def hash_dir_files(outdir: pathlib.Path, names: list[str]) -> str:
    h = hashlib.sha256()
    for n in names:
        p = outdir / n
        if p.exists():
            h.update(n.encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]
