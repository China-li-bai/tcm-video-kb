# 磁盘预算批处理 + 清理 + YouTube 引用 (disk budget)

磁盘只有 ~100 GB，整套人纪约 170 h 音频。每个条目只在跑的时候占"重"空间，
转写验证通过后立刻删除重文件，只留轻量输出 + 来源 YouTube URL。

## 每个条目写哪些副本

| 副本 | 旧 (≤ dc168ba) | 现在 |
|---|---|---|
| 源音频 `data/media/{s}/{s}-NNN.m4a` (~45 MB/h, 96 kbps) | 保留 | 验证后删除 |
| s01 `r2-mirror/source/<vid>.m4a` | 完整拷贝 1× 源 | 不拷贝 (`copy_source: false`)，只记路径 + URL |
| s02 播放用 64k m4a (artifacts + r2-mirror) | 2 × ~29 MB/h | YouTube 源不生成 (`play_copy: false`)，播放 = YouTube URL |
| s03 `full.wav` (16k 单声道) | 115 MB/h（临时） | 不再生成：静音检测和切片都直接从源解码 |
| s03 `audio/part_NNN.wav` | 115 MB/h | 115 MB/h，**验证后删除** |
| s03 r2-mirror 分片拷贝 | 115 MB/h | 不拷贝 (`mirror_parts: false`) |
| s04 `parts/part_NNN.json` 检查点 | 保留 | 验证后删除（`asr_raw.json` 里已有全部内容） |
| 轻量输出 asr_raw.json / segments.jsonl / chapters.json / lecture.md | ~1 MB/h ×2 | 保留 |

旧方式：每小时音频约 2×45 + 2×29 + 3×115 ≈ **490 MB/h**（峰值），其中 ~375 MB/h 会一直留着。
现在：峰值 = 源 + wav ≈ **160 MB/h**，清理后约 **2–3 MB/h**。shl（28.6 h）：旧 ≈ 11 GB 留存 / 14 GB 峰值；现在 ≈ 4.5 GB 峰值、清理后 < 0.1 GB。

## 命令

```bash
# 状态：purged | done | pending | downloading | missing（每个系列计数 + 剩余磁盘）
.venv/bin/python -m tcmkb_ingest media-status [--series shl --json]

# 计划（不跑）：
.venv/bin/python -m tcmkb_ingest batch --media zj --budget-gb 40 --dry-run

# 跑（后台）：一个 ASR 模型，6 个 torch 线程（给下载器留余量）
setsid nohup .venv/bin/python -m tcmkb_ingest batch --media zj --media nj \
  --budget-gb 40 --min-free-gb 15 --asr-threads 6 --run-id zj-nj-$(date +%Y%m%d) \
  > data/logs/zj-nj.log 2>&1 < /dev/null &

# 重新下载一条已清理的（从 YouTube URL），然后再跑 batch
.venv/bin/python -m tcmkb_ingest refetch --video shl-003 [--print-only]
```

参数：`--budget-gb`（默认 40，`configs/pipeline.yaml: budget`），`--min-free-gb`（默认 15），
`--no-purge`，`--keep-source`（只删 wav/中间文件），`--max-batches N`，`--only <video_id>`，`--limit N`。

## 设计

1. **目录**：`sources.load_catalog()` 把 `data/media/{s}/_playlist.txt`（idx, YouTube id, 时长, 标题）
   + `configs/sources/youtube_renji.yaml`（系列名、播放列表、频道）+ `_manifest.json`（ffprobe 时长）
   拼成 `video_id = {s}-{idx}` → `youtube_id / url / title / series / episode`。
   `scripts/build_media_manifest.py` 也把这些字段写进 `_manifest.json`（纯 python3，可选 PyYAML）。
2. **状态**：`purged`（`media_purge` 表有 active 行）> `done`（s04/s06/s08 done 且验证通过）>
   `downloading`（文件 120 s 内被改过 / 有 `.sections` 目录 / 时长 < 播放列表 97%）> `pending`；没文件 = `missing`。
3. **计划**（`planner.plan_batch`，纯函数）：按目录顺序贪心；工作集 = 源 + 时长×32000 B + 50 MB；
   满足 Σ工作集 ≤ budget 且 free − Σ新增字节 ≥ margin；单个超预算的条目单独成批；
   free < margin 直接拒绝（`DiskSpaceError`，退出码 2）。
4. **跑**：`run_batch`（共享 ASR 模型，按 version_key 续跑，失败继续）。每个条目成功后：
   `verify_outputs`（asr_raw.json tokens/text 非空，音频覆盖 ≥ 95% 时长，segments + chapters 非空，
   每条都有 `cite.t_url`）→ 通过才 `purge_item`。没通过的条目不删任何东西，下次重试。
   开跑前还会先清理"已验证但没清理"的条目（例如上次进程在清理前被杀）。
5. **记录**：SQLite `media_purge`（URL、sha256、字节数、删除的文件列表、验证信息、batch_id）+
   `video.meta.media_purged` + `data/media/{s}/_purged.json` + `_purged_ids.txt`
   （`download_one_audio.sh` 看到这个 id 就跳过，`FORCE_REFETCH=1` 例外）。
6. **续跑**：清理过的条目不再进入计划；调度器对它跳过 s00–s05（不需要源文件），
   s06–s08 仍可从保留的 asr_raw.json 重跑（例如词典更新）。要重跑 ASR：`refetch` → `batch`。

## 引用格式

`video.meta.source`、`asr_raw.json.source`、每条 segment / chapter 的 `cite`：

```json
{"youtube_id": "9zCCln-3KaE", "url": "https://www.youtube.com/watch?v=9zCCln-3KaE",
 "t_url": "https://www.youtube.com/watch?v=9zCCln-3KaE&t=591s",
 "title": "倪海廈《傷寒論》細分版： 6太陰症", "series_id": "shl", "series_title": "伤寒论",
 "episode": 6, "start_s": 591.84, "end_s": 592.08}
```

`lecture.md` 的章节标题时间戳也链接到 `t_url`。
