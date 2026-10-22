"""Time windows over transcript segments, rendered as compact reading text."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Window:
    window: str          # w00, w01, ...
    seg_from: int
    seg_to: int
    start_s: float
    end_s: float


def make_windows(segments: list[dict[str, Any]], window_s: float = 720.0,
                 min_tail_s: float = 180.0) -> list[Window]:
    """Consecutive, non-overlapping windows of ~window_s cut at segment boundaries.

    A tail shorter than min_tail_s is folded into the previous window.
    """
    if not segments:
        return []
    groups: list[list[dict[str, Any]]] = [[]]
    t0 = segments[0]["start_s"]
    for s in segments:
        if groups[-1] and s["start_s"] - t0 >= window_s:
            groups.append([])
            t0 = s["start_s"]
        groups[-1].append(s)
    if len(groups) > 1 and groups[-1][-1]["end_s"] - groups[-1][0]["start_s"] < min_tail_s:
        groups[-2].extend(groups.pop())
    return [Window(f"w{i:02d}", g[0]["seq"], g[-1]["seq"], g[0]["start_s"], g[-1]["end_s"])
            for i, g in enumerate(groups)]


def hms(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"


def render(segments: Iterable[dict[str, Any]]) -> str:
    """One line per segment: `<seq> <h:mm:ss> <text>`."""
    return "\n".join(f"{s['seq']} {hms(s['start_s'])} {s['text']}" for s in segments)
