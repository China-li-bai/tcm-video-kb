# Runbook：本地 Demo（zj.wav → s08）

目标：在不安装 FunASR 的情况下，用 `/workspace/asr-bench` 缓存跑通 s00–s08，产出 `asr_raw.json`、`segments.jsonl`、`chapters.json`、`lecture.md`。

时区：Asia/Shanghai（UTC+8）。

## 前置

```bash
cd /workspace/tcm-video-kb
uv sync
.venv/bin/python -m tcmkb_lexicon build
# 确认 zj 热词 pins：足三里 应在前 15
head -15 lexicon/dist/hotwords/zj.txt
```

确认缓存存在：

```bash
ls /workspace/asr-bench/wav/zj.wav
ls /workspace/asr-bench/out/zj.paraformer_hot.json
```

## 注册并跑到 s08

```bash
.venv/bin/python -m tcmkb_ingest register \
  --video zj-demo \
  --file /workspace/asr-bench/wav/zj.wav \
  --series zj --title "针灸大成·足三里演示"

.venv/bin/python -m tcmkb_ingest run \
  --video zj-demo --to s08 --from-cache --skip-alt
```

一步到位（未注册时带 `--file`）：

```bash
.venv/bin/python -m tcmkb_ingest run \
  --video zj-demo --to s08 --from-cache --skip-alt \
  --file /workspace/asr-bench/wav/zj.wav --series zj \
  --title "针灸大成·足三里演示"
```

## 查看产物

```bash
.venv/bin/python -m tcmkb_ingest status --video zj-demo
wc -l data/artifacts/zj-demo/segments.jsonl
python -c "import json; print(len(json.load(open('data/artifacts/zj-demo/chapters.json'))))"
head -40 data/artifacts/zj-demo/lecture.md
```

版本化产物在 `data/artifacts/zj-demo/{step}/{version_key}/`；根下四个文件是演示用指针副本。

## 续跑 / 强制重跑

- 改 `lexicon/` 纠错后：`python -m tcmkb_lexicon build`，再 `--from s06 --to s08`
- 改章节参数：`--from s08 --force`
- 热词变更**默认不重跑 ASR**（`hotword_set_pin`）；需要时 `--from s04 --force`

## 生产 ASR（非 cache）

```bash
uv sync --extra asr      # funasr + torch CPU 进本仓库 .venv；模型复用 ~/.cache/modelscope
.venv/bin/python -m tcmkb_ingest run --video zj-demo --to s08
# 多个视频（共享一次模型加载、可续跑、失败不中断）：
.venv/bin/python -m tcmkb_ingest batch --manifest configs/batches/asr_bench_samples.csv
```

`s04` 会读 `lexicon/dist/hotwords/{series}.txt`（每行一个词，最多取 `hotword_max`），调用 SeACo-Paraformer + fsmn-vad + ct-punc，并保存逐 token 时间戳。批量用法、内存和实测 RTF 见 [`batch_asr.md`](batch_asr.md)。

## 步骤一览

| 步骤 | 作用 | Demo 行为 |
|---|---|---|
| s00_register | sha256 / ffprobe / meta | 必跑 |
| s01_upload | LocalStorage=`data/r2-mirror` | 拷贝源文件 |
| s02_media | 播放副本 | wav→m4a（失败则拷贝） |
| s03_audio | 16k mono wav 分片 | ≤20 min 单 part；更长的在静音处切 |
| s04_asr | SeACo ASR | `--from-cache` 读 asr-bench JSON |
| s05_asr_alt | SenseVoice | 默认 skip |
| s06_clean | 句子重建 + t2s + 纠错 | 写 segments.jsonl |
| s07_flag | 双路一致率 | 无 alt 则透传 |
| s08_chapter | 启发式章节 + lecture.md | 有 LLM key 可选用 |

## 故障排查

- `funasr not installed`：加 `--from-cache`，或 `uv sync --extra asr`。
- `no ASR cache`：检查 `--cache-dir`（默认 `/workspace/asr-bench/out`）与 series slug（`zj-demo` → `zj`）。
- 热词无足三里：确认 `lexicon/pins/zj.txt` 存在后重新 `python -m tcmkb_lexicon build`。
