"""Sentence rebuild from char timestamps."""
from tcmkb_ingest.clean import rebuild_sentences, synthesize_tokens_from_sentences, align_text_to_tokens

def _toks(pairs):
    """pairs: list of (char, start, end)"""
    return [{"t": c, "s": s, "e": e} for c, s, e in pairs]

def test_break_on_period():
    text = "你好。世界！"
    tokens = _toks([
        ("你", 0.0, 0.2), ("好", 0.2, 0.4),
        ("世", 1.0, 1.2), ("界", 1.2, 1.4),
    ])
    sents = rebuild_sentences(text, tokens)
    assert len(sents) == 2
    assert sents[0]["text"] == "你好。"
    assert sents[1]["text"] == "世界！"
    assert sents[0]["start_s"] == 0.0
    assert sents[1]["start_s"] == 1.0

def test_gap_break():
    text = "甲乙丙丁"
    tokens = _toks([
        ("甲", 0.0, 0.2), ("乙", 0.2, 0.4),
        ("丙", 3.0, 3.2), ("丁", 3.2, 3.4),  # gap 2.6s > 1.2
    ])
    sents = rebuild_sentences(text, tokens, gap_break_s=1.2)
    assert len(sents) >= 2
    assert sents[0]["end_s"] <= 0.5
    assert sents[1]["start_s"] >= 2.9

def test_synthesize_from_sentences():
    sents = [
        {"start_ms": 0, "end_ms": 1000, "text": "足三里，"},
        {"start_ms": 1200, "end_ms": 2000, "text": "补泻。"},
    ]
    text, tokens = synthesize_tokens_from_sentences(sents)
    assert "足三里" in text
    assert len(tokens) == len("足三里补泻")
    assert tokens[0]["s"] == 0.0
    assert tokens[-1]["e"] <= 2.0 + 1e-6

def test_align_handles_punct():
    text = "你好，世界。"
    tokens = _toks([("你", 0, 0.1), ("好", 0.1, 0.2), ("世", 0.3, 0.4), ("界", 0.4, 0.5)])
    aligned = align_text_to_tokens(text, tokens)
    punct = [ch for ti, ch in aligned if ti < 0]
    assert "，" in punct and "。" in punct
