"""Storage protocol: LocalStorage mirrors R2 layout under data/r2-mirror/."""
from __future__ import annotations
import shutil, pathlib
from typing import Protocol, runtime_checkable

@runtime_checkable
class Storage(Protocol):
    def put_file(self, key: str, src: str | pathlib.Path) -> str: ...
    def get_file(self, key: str, dest: str | pathlib.Path) -> pathlib.Path: ...
    def exists(self, key: str) -> bool: ...
    def uri(self, key: str) -> str: ...

class LocalStorage:
    """Simulates R2 with a local mirror directory (data/r2-mirror/)."""

    def __init__(self, root: str | pathlib.Path):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> pathlib.Path:
        key = key.lstrip("/")
        return self.root / key

    def put_file(self, key: str, src: str | pathlib.Path) -> str:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        src = pathlib.Path(src)
        if dest.resolve() != src.resolve():
            shutil.copy2(src, dest)
        return self.uri(key)

    def get_file(self, key: str, dest: str | pathlib.Path) -> pathlib.Path:
        dest = pathlib.Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self._path(key), dest)
        return dest

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def uri(self, key: str) -> str:
        return f"file://{self._path(key).resolve()}"
