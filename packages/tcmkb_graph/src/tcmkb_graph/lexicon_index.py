"""id → term / category / lexicon relations.

Full schema validation stays in ``tcmkb_lexicon``. This index only reads the fields the
graph needs (including draft entries: v0.1 formulas are status draft and still supply
``composed_of``).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Ent:
    id: str
    term: str
    category: str
    relations: tuple[tuple[str, str], ...] = ()


def load_lexicon_index(lexicon_root: Path) -> dict[str, Ent]:
    entries = lexicon_root / "entries"
    if not entries.is_dir():
        return {}
    out: dict[str, Ent] = {}
    for path in sorted(entries.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
        if not isinstance(data, list):
            raise ValueError(f"{path} is not a list of entries")
        for raw in data:
            if not isinstance(raw, dict) or not raw.get("id"):
                continue
            eid = str(raw["id"])
            if eid in out:
                raise ValueError(f"duplicate lexicon id {eid}")
            rels: list[tuple[str, str]] = []
            for rel in raw.get("relations") or []:
                if isinstance(rel, dict) and rel.get("pred") and rel.get("obj"):
                    rels.append((str(rel["pred"]), str(rel["obj"])))
            out[eid] = Ent(
                id=eid,
                term=str(raw.get("term") or eid),
                category=str(raw.get("category") or ""),
                relations=tuple(rels),
            )
    return out
