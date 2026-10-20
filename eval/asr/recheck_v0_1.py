"""Quick re-check: SeACo-Paraformer with lexicon v0.1 hotwords (+ corrections) on asr-bench segments.
Run with the asr-bench venv (has funasr):  /workspace/asr-bench/venv/bin/python recheck_v0_1.py shl zj"""
import sys, json, time, pathlib
BENCH = pathlib.Path("/workspace/asr-bench"); KB = pathlib.Path("/workspace/tcm-video-kb")
OUT = KB / "eval/asr/out"
from funasr import AutoModel
segs = sys.argv[1:] or ["zj", "shl"]
t0 = time.time()
m = AutoModel(model="iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
              vad_model="fsmn-vad", punc_model="ct-punc", disable_update=True)
print("load", round(time.time() - t0, 1), flush=True)
for s in segs:
    HWDIR = pathlib.Path(__import__("os").environ.get("HWDIR", KB / "lexicon/dist/hotwords")); TAG = __import__("os").environ.get("TAG", "lex01")
    hw = HWDIR / f"{s}.txt"
    words = hw.read_text().split()
    t = time.time()
    r = m.generate(input=str(BENCH / f"wav/{s}.wav"), hotword=" ".join(words), batch_size_s=300)
    dt = time.time() - t
    out = {"segment": s, "hotword_file": str(hw), "n_hotwords": len(words), "proc_sec": dt, "rtf": dt / 600, "text": r[0]["text"]}
    json.dump(out, open(OUT / f"{s}.{TAG}.json", "w"), ensure_ascii=False, indent=1)
    print(s, "n_hot", len(words), "time", round(dt, 1), "RTF", round(dt / 600, 4), flush=True)
