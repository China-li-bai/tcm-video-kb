# Runbook：批量真实 ASR（s00–s08，FunASR SeACo-Paraformer）

时区：Asia/Shanghai（UTC+8）。实测日期 2026-10-20，本 box：8 vCPU、无 GPU、15 GB RAM（共享）。

## 1. 安装（workspace `.venv`，不再依赖 asr-bench venv）

```bash
cd /workspace/tcm-video-kb
uv sync --extra asr        # funasr 1.4.16 + modelscope + torch/torchaudio CPU（download.pytorch.org/whl/cpu）
.venv/bin/python -c "import funasr, torch; print(funasr.__version__, torch.__version__)"
```

- `tcmkb-ingest[asr]` = `funasr>=1.4, modelscope>=1.20, torch>=2.4, torchaudio>=2.4, psutil`。funasr 本身不声明 torch 依赖，旧 extra 只有 `funasr`，装完也跑不了；现在 torch 从根 `pyproject.toml` 的 `pytorch-cpu` index（explicit）取 `+cpu` 轮子，避免拉 CUDA 版。
- 模型复用 `~/.cache/modelscope/models/iic--*`（asr-bench 已下载：SeACo-Paraformer、fsmn-vad、ct-punc large，约 3 GB），无需重新下载；`disable_update=True`。
- 没装 FunASR 时 s04 live 会报 `run uv sync --extra asr`；Demo 仍可 `--from-cache`。

## 2. 批量命令

```bash
# 清单（CSV：file,series[,video_id,episode,title]；# 开头为注释；相对路径相对清单所在目录）
.venv/bin/python -m tcmkb_ingest batch --manifest configs/batches/asr_bench_samples.csv

# 或目录 + 系列（递归找媒体文件；video_id 默认 {series}-{文件名中第一个数字:03d}，不唯一时退回 stem/哈希）
.venv/bin/python -m tcmkb_ingest batch --dir /data/incoming/shl --series shl
.venv/bin/python -m tcmkb_ingest batch --dir /data/incoming/shl --series shl --dry-run   # 先看 ID 映射

# YAML 清单也可：{series: nj, videos: [{file: ..., video_id: ..., title: ...}]}
```

常用选项：`--to s08`、`--from s06`、`--force`、`--fail-fast`、`--limit N`、`--run-id NAME`、`--from-cache`（不加载模型）。

行为：

| 需求 | 实现 |
|---|---|
| 一次加载模型 | `asr_engine.get_engine()` 进程级缓存，`batch` 把同一个 engine 传给每个视频；**懒加载**，全部已完成时不加载（实测重跑 0.26 s） |
| 续跑 | 每步 `version_key` 已 done 即跳过；s04 另按音频分片写 `s04_asr/<vk>/parts/part_NNN.json`，中途失败重跑时已完成分片直接复用 |
| 单视频失败不中断 | 抛错的步骤 `step_run.status=failed`（保留 error），报告记 `failed_step/error`，继续下一个；有失败时退出码 2 |
| 进度 / RTF | 日志 `[batch i/N] … wall= audio= rtf= edits= chapters= elapsed= eta= rss=`；报告 `data/batch/<run_id>.json|.csv`（每视频 RTF、纠错数、章节数；进程峰值内存） |
| 长音频 | s03 抽 16k 单声道 wav，>20 min 时在每个 20 min 边界前 2 min 内找最长静音（ffmpeg silencedetect −35 dB / 0.4 s）切分，找不到则硬切；s04 逐片识别并加回 offset |
| R2 | 仍是 `LocalStorage`（`data/r2-mirror/`），不上传云端 |

## 3. 内存

- 模型常驻约 3.0 GB（SeACo 943 MB + ct-punc large 1073 MB 参数 + 运行时）。权重用 `torch.load(mmap=True)` 加载：加载期匿名内存峰值从约 5.5 GB 降到约 3.8 GB（`VmHWM` 仍显示约 5.0 GB，多出的是可回收的 mmap 文件页）。
- CPU 上 FunASR 对 VAD 段逐个解码（`batch_size=0`），每段 ≤60 s（`vad_max_single_segment_ms`），每个分片 ≤20 min，所以峰值与视频长度无关：实测 30 min 两分片的匿名峰值是 3.79 GB，10 min 单分片是 3.68 GB。
- **只跑一个 ASR 进程**。实测平均只用了约 2.8 核（user+sys / wall），两个 worker 理论上能提高吞吐，但需要额外约 3–4 GB，共享 box 只剩约 3 GB 空闲时不要开。

## 4. 实测结果（2026-10-20，三个 10 min 样本，真实 FunASR，非 cache）

`batch --manifest configs/batches/asr_bench_samples.csv --run-id live-samples-1`。原始数据：`eval/asr/out/batch_live-samples-1.json`、`eval/asr/out/score_live_v0_2.json`。

| 样本 | ASR proc (s) | RTF（ASR） | 视频 wall (s) | 窗口 CER live raw / +corr | cached bench31 raw / +corr | 关键词命中 extra live+corr / bench+corr | s06 纠错 | 章节 |
|---|---|---|---|---|---|---|---|---|
| zj | 28.45 | 0.0474 | 64.1（含模型加载 30.9） | 6.37% / 5.93% | 5.93% / 5.27% | 12/15 / 13/15 | 12 | 3 |
| shl | 27.86 | 0.0464 | 30.8 | 9.89% / 9.89% | 10.20% / 10.20% | 16/21 / 15/21 | 19 | 2 |
| nj | 27.50 | 0.0458 | 33.6 | 9.79% / 9.15% | 10.64% / 9.15% | 14/14 / 12/14 | 5 | 2 |

- 整批 wall 128.5 s（`time`：real 2:10，user 6:00，sys 0:07.6），音频 1800 s；ASR 合计 83.8 s，平均 RTF 0.0466；模型加载 30.9 s（只加载一次）。
- 峰值内存：RSS 5039 MB（VmHWM，含 mmap 文件页），匿名 RSS 3677 MB；视频间稳态约 3.2 GB。
- live 用的是系列热词文件（每系列 50 词，带 pins），cached bench 用的是 31 个手选词。差异都在约 2 pt 的噪声带内（见 asr-bench/results.md）。
- 时间戳：逐 token 时间戳来自 SeACo `timestamp` 和 `raw_text` 的一一对应，三个样本都没有逆序或 e<s；有少量多字 token（英文，如 `ok`）。
- 长音频验证：三段拼成 30 min 后在 1180.8 s 处切成 2 片，RTF 0.0449 / 0.0453，第二片 token 已加 offset，单调；匿名峰值 3794 MB，视频 wall 132.7 s。

## 5. 200 GB 估算（**估计值**，只有 RTF 和 CPU 秒是实测）

假设：音频时长 = 200 GB × 8 / 总码率。讲座视频典型 1.1 Mbps → **≈404 h**；0.7 Mbps → 635 h；2.2 Mbps → 202 h。

| 项 | 实测系数 | 202 h | **404 h** | 635 h |
|---|---|---|---|---|
| s04 ASR wall（本 box，单进程） | RTF 0.0466 | 9.4 h | **18.8 h** | 29.6 h |
| s00–s08 wall（wav 输入，不含模型加载） | ≈0.056 × 音频 | 11.3 h | **22.6 h** | 35.6 h |
| CPU 核时（user+sys） | 0.20 CPU·s / 音频 s | 41 | **82** | 130 |

- 未计入：网盘下载（大概率是总瓶颈）；视频输入时 s02 的 faststart remux 和 AAC 编码，以及 s03 从视频解码音轨（未实测，ARCHITECTURE 估 1–3 h）。
- 磁盘：`LocalStorage` 会把源文件复制到 `data/r2-mirror/source/`，s02 再写一份 mp4 副本，s03 的 wav 也会镜像（约 115 MB/h）。本盘约 107 GB 空闲，必须按 30–50 GB 一批处理，跑完清理。
- GPU（**未实测，假设**）：SeACo-Paraformer 单卡 RTF 约 0.005–0.01，404 h 约 2–4 h。GPU 上 FunASR 会按 `batch_size_s=300` 动态拼批，不再逐段解码，显存约几 GB。到那时瓶颈会变成 ffmpeg 抽音频和下载。CPU 侧代码不用改，只需 `device=cuda`（目前未暴露到 asr.yaml）。

## 6. 已知限制

- `nfilter`（ASF k）和 `seaco_weight`：funasr 1.4.16 的 `inference()` 写死了 `nfilter=50, seaco_weight=1.0`，generate kwargs 不会透传；`asr.yaml` 里的这两个键只做记录。
- 热词默认 pin（`hotword_set_pin: true`）：重建词典不会触发重跑 ASR。需要时用 `--from s04 --force`。
- s05（SenseVoice 第二遍）仍默认跳过。
