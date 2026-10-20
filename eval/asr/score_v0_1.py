"""Score re-check outputs vs the asr-bench baseline, using the same window references and
semi-global alignment as /workspace/asr-bench/evaluate.py (copied here to avoid its import side effects).
Run: /workspace/asr-bench/venv/bin/python score_v0_1.py"""
import sys, json, pathlib
sys.path.insert(0, "/workspace/asr-bench"); sys.path.insert(0, "/workspace/tcm-video-kb/packages/tcmkb_lexicon/src")
from evalutil import norm, cer, cc
from tcmkb_lexicon.correct import Corrector
B = pathlib.Path("/workspace/asr-bench"); KB = pathlib.Path("/workspace/tcm-video-kb")
HOT = "伤寒论 金匮要略 黄帝内经 太阳 阳明 少阳 太阴 少阴 厥阴 桂枝汤 麻黄汤 小柴胡汤 白虎汤 承气汤 附子 干姜 甘草 足三里 合谷 内关 三阴交 经络 穴位 脉象 浮脉 沉脉 证型 辨证 倪海厦 人纪 天纪".split()
EXTRA = "汤剂 散剂 丸剂 攻里 承气 白虎 五脏六腑 通关活络 阴阳 胃气 足三里 阳明 斜刺 灸 岐伯 黄帝 岐黄 上古天真论 内经 术数 张仲景 伤寒 金匮 桂枝 经方 太阳中风 发汗 发表".split()
KEY = "桂枝 桂枝汤 张仲景 伤寒 金匮 经方 五苓散 乌梅丸 足三里 梁丘 伏兔 髀关 阴市 上巨虚 下巨虚 条口 阑尾穴 斜刺 胃气 岐伯 黄帝 上古天真论 法于阴阳 和于术数".split()
def semiglobal(r, h):
    m, n = len(r), len(h); Dprev = [0] * (n + 1); Sprev = list(range(n + 1))
    for i in range(1, m + 1):
        D = [i] + [0] * n; S = [0] * (n + 1); ri = r[i - 1]
        for j in range(1, n + 1):
            a = Dprev[j - 1] + (ri != h[j - 1]); b = Dprev[j] + 1; c = D[j - 1] + 1
            if a <= b and a <= c: D[j] = a; S[j] = Sprev[j - 1]
            elif b <= c: D[j] = b; S[j] = Sprev[j]
            else: D[j] = c; S[j] = S[j - 1]
        Dprev, Sprev = D, S
    j = min(range(n + 1), key=lambda j: Dprev[j]); return Sprev[j], j
cj = json.load(open(KB / "lexicon/dist/corrections.json"))
COR = Corrector(cj["rules"], protected=set(cj["protected_surfaces"]))
def score(seg, text):
    ref = norm(open(B / f"ref/{seg}.window.ref.txt").read()); h = norm(text)
    a, b = semiglobal(ref, h); hw = h[a:b]; c = cer(ref, hw)
    hits = {}
    for lst, name in ((HOT, "hot31"), (EXTRA, "extra")):
        n = k = 0
        for t in lst:
            rc = ref.count(t)
            if rc: n += rc; k += min(rc, hw.count(t))
        hits[name] = f"{k}/{n}"
    keys = {t: h.count(t) for t in KEY if h.count(t)}
    return dict(win_cer=c["cer"], S=c["S"], D=c["D"], I=c["I"], N=c["N"], hits=hits, key_counts=keys)
R = {}
for seg in ["zj", "shl", "nj"]:
    p = KB / f"eval/asr/out/{seg}.lex01.json"
    if not p.exists(): continue
    base = json.load(open(B / f"out/{seg}.paraformer_hot.json"))["text"]
    plain = json.load(open(B / f"out/{seg}.paraformer.json"))["text"]
    new = json.load(open(p))
    variants = {"bench_nohot": cc.convert(plain), "bench_hot31": cc.convert(base), "lex01_hot400": cc.convert(new["text"])}
    p100 = KB / f"eval/asr/out/{seg}.lex01cap100.json"
    if p100.exists(): variants["lex01_hot100"] = cc.convert(json.load(open(p100))["text"])
    for k in list(variants):
        fixed, edits = COR.correct(variants[k]); variants[k + "+corr"] = fixed
        R.setdefault(seg, {})[k + "+corr_edits"] = [f"{e['from']}→{e['to']}" for e in edits]
    for k, v in variants.items():
        R[seg][k] = score(seg, v); print(seg, k, R[seg][k], flush=True)
    R[seg]["lex01_meta"] = {x: new[x] for x in ("n_hotwords", "proc_sec", "rtf")}
    if p100.exists(): R[seg]["lex01cap100_meta"] = {x: json.load(open(p100))[x] for x in ("n_hotwords", "proc_sec", "rtf")}
    for k, v in variants.items():
        if k.endswith("+corr"): open(KB / f"eval/asr/out/{seg}.{k}.txt", "w").write(v)
json.dump(R, open(KB / "eval/asr/out/score_v0_1.json", "w"), ensure_ascii=False, indent=1)
