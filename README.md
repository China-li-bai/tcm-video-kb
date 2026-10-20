# tcm-video-kb

倪海厦中医讲座视频知识库（monorepo）。把讲座视频转成带时间戳的结构化文本：ASR → 清洗 → 章节 →（后续）切块/实体/检索。

设计见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。本地 Demo 见 [`docs/runbooks/local_demo.md`](docs/runbooks/local_demo.md)。

## 结构

| 路径 | 说明 |
|---|---|
| `packages/tcmkb_core` | 模型、配置、LocalStorage、`version_key` |
| `packages/tcmkb_lexicon` | 词典校验/构建/纠错/匹配 |
| `packages/tcmkb_ingest` | 流水线 s00–s08 + CLI |
| `lexicon/` | 共享中医词典（YAML）与 `dist/` 产物 |
| `configs/` | `pipeline.yaml` / `asr.yaml` / `series.yaml` / prompts |
| `data/` | 本地状态库与产物（gitignore） |

## 环境

```bash
cd /workspace/tcm-video-kb
uv sync
# 词典构建（热词 pins + 频次排序）
.venv/bin/python -m tcmkb_lexicon build
```

真实 ASR（FunASR SeACo-Paraformer + torch CPU，装进本仓库 `.venv`；模型复用 `~/.cache/modelscope`）：

```bash
uv sync --extra asr
```

## 批量转写（真实 ASR）

```bash
# 清单 CSV：file,series[,video_id,episode,title]
.venv/bin/python -m tcmkb_ingest batch --manifest configs/batches/asr_bench_samples.csv
# 或目录 + 系列
.venv/bin/python -m tcmkb_ingest batch --dir /path/to/shl --series shl [--dry-run]
```

一个进程只加载一次模型（懒加载）；按 version_key 续跑（s04 按 20 min 分片做检查点）；单个视频失败会记入 `step_run` 和报告，然后继续下一个；报告写到 `data/batch/<run_id>.json|csv`（每视频 RTF、纠错数、章节数、峰值内存）。实测 RTF ≈0.047（8 vCPU），常驻内存约 3 GB。详见 [`docs/runbooks/batch_asr.md`](docs/runbooks/batch_asr.md)。

## 快速 Demo（推荐 `--from-cache`）

用 asr-bench 已有的 SeACo 结果，不加载 FunASR：

```bash
.venv/bin/python -m tcmkb_ingest register \
  --video zj-demo \
  --file /workspace/asr-bench/wav/zj.wav \
  --series zj --title "针灸大成·足三里演示"

.venv/bin/python -m tcmkb_ingest run \
  --video zj-demo --to s08 --from-cache --skip-alt
```

产物（稳定指针 + 版本目录）：

- `data/artifacts/zj-demo/asr_raw.json`
- `data/artifacts/zj-demo/segments.jsonl`
- `data/artifacts/zj-demo/chapters.json`
- `data/artifacts/zj-demo/lecture.md`

## CLI

```bash
.venv/bin/python -m tcmkb_ingest steps
.venv/bin/python -m tcmkb_ingest status --video zj-demo
.venv/bin/python -m tcmkb_ingest run --video zj-demo --to s08 --from-cache
# 生产 ASR（需 uv sync --extra asr）：
.venv/bin/python -m tcmkb_ingest run --video zj-demo --to s08
.venv/bin/python -m tcmkb_ingest batch --manifest configs/batches/asr_bench_samples.csv
# 等价入口：
.venv/bin/tcmkb run --video zj-demo --to s08 --from-cache
```

`--skip-alt` 为默认（跳过 s05 SenseVoice）。改词典纠错后从 s06 续跑即可；热词默认 pin，不自动重跑 ASR（需 `--force`）。

## 测试

```bash
.venv/bin/pytest -q
```

## 免责

系统输出用于学习倪师讲授内容，不作为诊疗建议。素材使用权需在公开/商用前确认。
