"""Score LIVE pipeline output (s04 asr_raw.json / s06 segments.jsonl) against the asr-bench
window references, with the same normalisation + semi-global window alignment as score_v0_1.py.

Compares, per sample: cached bench (31 hotwords) raw/+corr vs live s04 (series hotword file,
~50 words) raw/+corr and the actual pipeline s06 text. Also sanity-checks token timestamps.
Run (needs jiwer/cn2an from the asr-bench venv):
  /workspace/asr-bench/venv/bin/python eval/asr/score_live.py [--video-suffix -demo]
"""
import sys, json, pathlib, argparse
sys.path.insert(0, "/workspace/asr-bench"); sys.path.insert(0, "/workspace/tcm-video-kb/packages/tcmkb_lexicon/src")
from evalutil import norm, cer, cc
from tcmkb_lexicon.correct import Corrector

B = pathlib.Path("/workspace/asr-bench"); KB = pathlib.Path("/workspace/tcm-video-kb")
ap = argparse.ArgumentParser()
ap.add_argument("--video-suffix", default="-demo")
ap.add_argument("--out", default=str(KB / "eval/asr/out/score_live_v0_2.json"))
args = ap.parse_args()

# Same term lists as score_v0_1.py
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

def ts_check(asr):
    toks = asr["tokens"]; s = [t["s"] for t in toks]
    nonmono = sum(1 for x, y in zip(s, s[1:]) if y < x)
    bad = sum(1 for t in toks if t["e"] < t["s"])
    dur = sum(float(p.get("duration_s") or 0) for p in asr["parts"])
    return dict(n_tokens=len(toks), first_s=s[0] if s else None, last_e=toks[-1]["e"] if toks else None,
                audio_sec=dur, non_monotonic=nonmono, end_before_start=bad,
                multi_char_tokens=sum(1 for t in toks if len(t["t"]) > 1))

R = {}
for seg in ["zj", "shl", "nj"]:
    vid = f"{seg}{args.video_suffix}"
    art = KB / "data/artifacts" / vid
    if not (art / "asr_raw.json").exists():
        print("skip", seg); continue
    asr = json.load(open(art / "asr_raw.json"))
    if asr.get("from_cache"):
        print("skip (from_cache)", seg); continue
    segs = [json.loads(l) for l in open(art / "segments.jsonl", encoding="utf-8")]
    chapters = json.load(open(art / "chapters.json"))
    bench = json.load(open(B / f"out/{seg}.paraformer_hot.json"))
    variants = {"bench_hot31": cc.convert(bench["text"]), "live_hot50": cc.convert(asr["text"])}
    R[seg] = {}
    for k in list(variants):
        fixed, edits = COR.correct(variants[k]); variants[k + "+corr"] = fixed
        R[seg][k + "+corr_edits"] = len(edits)
    variants["live_pipeline_s06"] = "".join(s["text"] for s in segs)
    for k, v in variants.items():
        R[seg][k] = score(seg, v); print(seg, k, R[seg][k], flush=True)
    R[seg]["live_meta"] = {**asr["metrics"], "hotword_set": asr["hotword_set"], "model_rev": asr["model_rev"],
                           "s06_segments": len(segs), "s06_edits": sum(len(s["edits"]) for s in segs),
                           "s08_chapters": len(chapters), "bench_rtf": bench.get("rtf"),
                           "bench_proc_sec": bench.get("proc_sec")}
    R[seg]["timestamps"] = ts_check(asr)
    print(seg, "meta", R[seg]["live_meta"], R[seg]["timestamps"], flush=True)
json.dump(R, open(args.out, "w"), ensure_ascii=False, indent=1)
print("wrote", args.out)
