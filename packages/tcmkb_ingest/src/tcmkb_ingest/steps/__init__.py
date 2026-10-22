"""Pipeline steps s00 … s09 (s09_knowledge is opt-in: default plans stop at s08)."""
from __future__ import annotations
from typing import Callable

STEP_ORDER = [
    "s00_register",
    "s01_upload",
    "s02_media",
    "s03_audio",
    "s04_asr",
    "s05_asr_alt",
    "s06_clean",
    "s07_flag",
    "s08_chapter",
    "s09_knowledge",
]

# Short aliases accepted by CLI (--to s08, --from s04)
ALIASES = {
    "s00": "s00_register",
    "s01": "s01_upload",
    "s02": "s02_media",
    "s03": "s03_audio",
    "s04": "s04_asr",
    "s05": "s05_asr_alt",
    "s06": "s06_clean",
    "s07": "s07_flag",
    "s08": "s08_chapter",
    "s09": "s09_knowledge",
}

def normalize_step(name: str) -> str:
    name = name.strip()
    return ALIASES.get(name, name)

def steps_up_to(to_step: str) -> list[str]:
    to_step = normalize_step(to_step)
    if to_step not in STEP_ORDER:
        raise ValueError(f"unknown step {to_step}; known={STEP_ORDER}")
    return STEP_ORDER[: STEP_ORDER.index(to_step) + 1]

def get_runner(step: str) -> Callable:
    step = normalize_step(step)
    from . import (
        s00_register, s01_upload, s02_media, s03_audio,
        s04_asr, s05_asr_alt, s06_clean, s07_flag, s08_chapter, s09_knowledge,
    )
    return {
        "s00_register": s00_register.run,
        "s01_upload": s01_upload.run,
        "s02_media": s02_media.run,
        "s03_audio": s03_audio.run,
        "s04_asr": s04_asr.run,
        "s05_asr_alt": s05_asr_alt.run,
        "s06_clean": s06_clean.run,
        "s07_flag": s07_flag.run,
        "s08_chapter": s08_chapter.run,
        "s09_knowledge": s09_knowledge.run,
    }[step]
