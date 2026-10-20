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

可选 ASR（生产路径，本机 FunASR）：

```bash
uv pip install 'tcmkb-ingest[asr]'
# 或复用 /workspace/asr-bench/venv
```

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
# 生产 ASR（需 FunASR）：
.venv/bin/python -m tcmkb_ingest run --video zj-demo --to s08 --no-skip-alt=false
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
