"""s06 helpers: rebuild sentences from char timestamps, OpenCC t2s, lexicon corrections."""
from __future__ import annotations
import difflib, re
from typing import Any

# Characters that end a sentence when present in the punctuated ASR text
_SENT_END = set("。！？；!?")
# Strip these when aligning punctuated text to token sequence
_PUNCT_RE = re.compile(r"[\s\u3000，,。．\.！!？\?；;：:、·「」『』（）\(\)\[\]【】《》<>\"'…—\-–]")


def strip_punct(text: str) -> str:
    return _PUNCT_RE.sub("", text)


def _is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (
        0x4E00 <= o <= 0x9FFF
        or 0x3400 <= o <= 0x4DBF
        or 0xF900 <= o <= 0xFAFF
    )


def align_text_to_tokens(text: str, tokens: list[dict[str, Any]]) -> list[tuple[int, str]]:
    """Align punctuated `text` to token list.

    Returns list of (token_index_or_-1, char) for each character in text.
    Punctuation / whitespace get token_index=-1.
    Uses exact walk when lengths match after strip; otherwise difflib.
    """
    tok_strs = [str(t.get("t", "")) for t in tokens]
    flat = "".join(tok_strs)
    stripped = strip_punct(text)

    # Build map from flat-char index -> token index
    flat_to_tok: list[int] = []
    for i, ts in enumerate(tok_strs):
        for _ in ts:
            flat_to_tok.append(i)

    if stripped == flat and len(flat_to_tok) == len(flat):
        # Fast path: walk text, advance flat pointer on non-punct
        out: list[tuple[int, str]] = []
        fi = 0
        for ch in text:
            if _PUNCT_RE.match(ch):
                out.append((-1, ch))
            else:
                ti = flat_to_tok[fi] if fi < len(flat_to_tok) else -1
                out.append((ti, ch))
                fi += 1
        return out

    # Slow path: align stripped <-> flat with SequenceMatcher
    sm = difflib.SequenceMatcher(a=list(stripped), b=list(flat), autojunk=False)
    strip_to_flat: dict[int, int] = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for k in range(i2 - i1):
                strip_to_flat[i1 + k] = j1 + k
        elif tag == "replace":
            # best-effort: map min length pairwise
            for k in range(min(i2 - i1, j2 - j1)):
                strip_to_flat[i1 + k] = j1 + k

    out = []
    si = 0
    for ch in text:
        if _PUNCT_RE.match(ch):
            out.append((-1, ch))
        else:
            fi = strip_to_flat.get(si)
            ti = flat_to_tok[fi] if fi is not None and fi < len(flat_to_tok) else -1
            out.append((ti, ch))
            si += 1
    return out


def rebuild_sentences(
    text: str,
    tokens: list[dict[str, Any]],
    *,
    gap_break_s: float = 1.2,
    max_sentence_s: float = 40.0,
) -> list[dict[str, Any]]:
    """Rebuild sentence spans from punctuated text + char timestamps.

    Each sentence: {start_s, end_s, text, token_from, token_to}.
    Breaks on 。！？；, token gap > gap_break_s, or duration > max_sentence_s.
    """
    if not tokens:
        # Fallback: whole text as one sentence if no timing
        return [{"start_s": 0.0, "end_s": 0.0, "text": text, "token_from": 0, "token_to": 0}]

    aligned = align_text_to_tokens(text, tokens)
    sentences: list[dict[str, Any]] = []
    buf_chars: list[str] = []
    buf_tok_idxs: list[int] = []
    last_tok_end: float | None = None

    def _flush():
        nonlocal buf_chars, buf_tok_idxs, last_tok_end
        raw = "".join(buf_chars).strip()
        if not raw:
            buf_chars, buf_tok_idxs = [], []
            return
        valid = [i for i in buf_tok_idxs if 0 <= i < len(tokens)]
        if valid:
            start_s = float(tokens[valid[0]]["s"])
            end_s = float(tokens[valid[-1]]["e"])
            t_from, t_to = valid[0], valid[-1] + 1
        else:
            # punctuation-only or unaligned — inherit previous end
            start_s = last_tok_end or float(tokens[0]["s"])
            end_s = start_s
            t_from = t_to = 0
        sentences.append({
            "start_s": start_s,
            "end_s": end_s,
            "text": raw,
            "token_from": t_from,
            "token_to": t_to,
        })
        last_tok_end = end_s
        buf_chars, buf_tok_idxs = [], []

    for ti, ch in aligned:
        # Gap break before appending a new non-punct token
        if ti >= 0 and buf_tok_idxs:
            prev = buf_tok_idxs[-1]
            if prev >= 0 and ti > prev:
                gap = float(tokens[ti]["s"]) - float(tokens[prev]["e"])
                if gap > gap_break_s:
                    _flush()
            # Duration break
            if buf_tok_idxs:
                first = next((x for x in buf_tok_idxs if x >= 0), None)
                if first is not None and ti >= 0:
                    dur = float(tokens[ti]["e"]) - float(tokens[first]["s"])
                    if dur > max_sentence_s and ch in _SENT_END:
                        buf_chars.append(ch)
                        if ti >= 0:
                            buf_tok_idxs.append(ti)
                        _flush()
                        continue

        buf_chars.append(ch)
        if ti >= 0:
            buf_tok_idxs.append(ti)

        if ch in _SENT_END:
            _flush()
        elif buf_tok_idxs:
            first = next((x for x in buf_tok_idxs if x >= 0), None)
            last = next((x for x in reversed(buf_tok_idxs) if x >= 0), None)
            if first is not None and last is not None:
                if float(tokens[last]["e"]) - float(tokens[first]["s"]) > max_sentence_s:
                    _flush()

    _flush()
    return sentences


def synthesize_tokens_from_sentences(sentences: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """When cache has sentence_info but no char timestamps, synthesize even char timing."""
    tokens: list[dict[str, Any]] = []
    parts: list[str] = []
    for sent in sentences:
        t = sent.get("text") or ""
        # Prefer seconds; accept ms fields from asr-bench
        if "start_s" in sent:
            s0, e0 = float(sent["start_s"]), float(sent["end_s"])
        else:
            s0 = float(sent.get("start_ms", 0)) / 1000.0
            e0 = float(sent.get("end_ms", 0)) / 1000.0
        parts.append(t)
        chars = [c for c in t if not _PUNCT_RE.match(c)]
        if not chars:
            continue
        dur = max(e0 - s0, 0.01)
        step = dur / len(chars)
        for i, c in enumerate(chars):
            tokens.append({"t": c, "s": round(s0 + i * step, 3), "e": round(s0 + (i + 1) * step, 3)})
    return "".join(parts), tokens


def tokens_from_timestamp_pairs(text: str, timestamp_ms: list[list[int]]) -> list[dict[str, Any]]:
    """Map FunASR `timestamp` ([[start_ms,end_ms],...]) onto stripped chars of text."""
    chars = list(strip_punct(text))
    n = min(len(chars), len(timestamp_ms))
    out = []
    for i in range(n):
        a, b = timestamp_ms[i]
        out.append({"t": chars[i], "s": a / 1000.0, "e": b / 1000.0})
    # If more timestamps than chars (rare), drop extras; if fewer, extend last end
    if len(chars) > n and n > 0:
        last_e = out[-1]["e"]
        for c in chars[n:]:
            out.append({"t": c, "s": last_e, "e": last_e + 0.05})
            last_e += 0.05
    return out
