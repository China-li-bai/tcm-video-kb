"""Parsers for the downloaded public-domain sources in lexicon/sources/ (seed import only)."""
import re, json, pathlib
from opencc import OpenCC
SRC = pathlib.Path(__file__).resolve().parents[2] / "lexicon" / "sources"
t2s = OpenCC("t2s").convert
# OpenCC-reimplemented misses / variant chars seen in these sources
FIX = str.maketrans({"朮": "术", "麪": "面", "蔕": "蒂", "栝": "栝", "箇": "个", "谿": "溪", "濇": "涩", "鞕": "硬", "蚘": "蛔", "㕮": "㕮"})
def s(x): return t2s(x).translate(FIX)
def strip_wiki(t):
    t = re.sub(r"-\{(.*?)\}-", r"\1", t)
    t = re.sub(r"\{\{\*\|.*?\}\}", "", t)
    t = re.sub(r"<ref[^>]*?/>|<ref.*?</ref>", "", t, flags=re.S)
    return t
UNITS = "两兩枚个箇個升斤铢銖合分钱錢斗尺寸片握把茎莖粒具只隻条條"
NUM = "一二三四五六七八九十百半～~"
DOSE = re.compile(rf"(各)?[{NUM}]+[{UNITS}]|[{NUM}]*[{UNITS}](?=$)|如[^\s]+大|\d")
def split_ingredients(line):
    line = re.sub(r"（[^）]*）|\([^)]*\)", " ", line)
    out = []
    for tok in re.split(r"[\s\u3000、，,]+", line):
        tok = tok.strip()
        if not tok or tok.startswith(("上", "右")) and "味" in tok: continue
        m = DOSE.search(tok)
        name = tok[: m.start()] if m else tok
        name = re.sub(r"各$", "", name)
        if name: out.append(name)
    return out
def shl_formulas():
    t = strip_wiki((SRC / "shl_wikisource.wikitext").read_text())
    i = t.find("辨太陽病脈證並治（上）第五"); j = t.find("辨不可發汗病脈證並治第十五")
    res = []
    for m in re.finditer(r"^:;\s*(.+?)\s*$\n::(.+)$", t[i:j], re.M):
        res.append((m.group(1), m.group(2)))
    return res
def jgy_formulas():
    t = strip_wiki((SRC / "jgy_wikisource_simp.wikitext").read_text())
    secs = list(re.finditer(r"^===\s*(.*?)\s*===\s*$", t, re.M))
    res = []
    for k, sm in enumerate(secs):
        name = sm.group(1)
        if re.search(r"第二十[三四五]", name): continue
        body = t[sm.end(): secs[k + 1].start() if k + 1 < len(secs) else len(t)]
        lines = [l.strip() for l in body.split("\n")]
        for n, l in enumerate(lines):
            m = re.fullmatch(r"'''(.+?)'''", l)
            if m:
                ing = next((x for x in lines[n + 1:] if x), "")
                res.append((m.group(1), ing, name))
    return res
def bencao():
    t = strip_wiki((SRC / "bencao_wikisource.wikitext").read_text())
    secs = list(re.finditer(r"^===\s*(.*?)\s*===\s*$", t, re.M))
    res = []
    for k, sm in enumerate(secs):
        sec = sm.group(1)
        body = t[sm.end(): secs[k + 1].start() if k + 1 < len(secs) else len(t)]
        for m in re.finditer(r"'''(.+?)'''\s*(.*)", body):
            res.append(dict(name=m.group(1).strip(), section=sec, text=m.group(2).strip()))
    return res
