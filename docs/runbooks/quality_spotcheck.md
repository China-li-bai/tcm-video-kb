# 质量抽检操作手册（ASR + 知识点）

依据 `docs/ARCHITECTURE.md` §9。本手册说明如何用 `scripts/eval/` 抽样、填分、以及门槛目标。

> 免责：抽检与知识库仅用于学习倪师讲授内容，不作为诊疗建议。

## 目标门槛

| 环节 | 指标 | 目标 |
|---|---|---|
| ASR 抽检 | 字符错误率 CER | ≤ 8% |
| ASR 抽检 | 术语召回（窗口内词典术语被正确写出的比例） | ≥ 90% |
| 知识点 | 人工判定「对」占比（「部分对」另计，见下） | 建议 MVP ≥ 85%「对」；「错」应回流修正注释 |
| 检索问答 | `eval/retrieval/qa.jsonl` Recall@8 / 引用正确率 | ≥ 85% / ≥ 90%（后续 stretch） |

## 目录

```
eval/
├── asr/
│   ├── score_*.py / recheck_*.py   # 既有 asr-bench 对齐打分（有参考稿时）
│   └── windows/                    # 人工听写抽检窗
│       ├── batch001_windows.csv
│       └── batch001_windows.jsonl
├── kp/
│   ├── batch001_kp_review.csv      # 知识点人工复核表
│   └── batch001_kp_review.jsonl
├── retrieval/
│   └── qa.jsonl                    # 检索评测题（骨架 → 扩到 ~50）
├── templates/                      # 空白填分模板
│   ├── asr_window_score.csv
│   └── kp_verdict.csv
└── README.md
scripts/eval/
├── _common.py
├── sample_asr_windows.py
└── sample_kp_review.py
```

不下载整集视频做评测：用 CSV 里的 `youtube_url_t`（或站内 `/watch/{id}?t=`）跳到时间点听。磁盘紧时不要为抽检再跑 yt-dlp。

跳过：`data/media/zj/_incomplete` 下的短目录片（`zj-001/009/018/…` 等），采样脚本已内置黑名单。

## 1. 生成抽检样本

在仓库根目录：

```bash
# ASR：约每 10 讲抽 1 个 2 分钟窗；优先中医术语密度高的片段
uv run python scripts/eval/sample_asr_windows.py
# 或: python scripts/eval/sample_asr_windows.py --seed 20261025 --per-n 10 --window-s 120

# 知识点：按 series × type 分层；短 evidence_quote 会被标记 short_evidence=1
uv run python scripts/eval/sample_kp_review.py
# 或: python scripts/eval/sample_kp_review.py --per-cell 1 --max-total 80
```

可选参数见各脚本 `--help`。重新抽样请改 `--seed` 或提高 `--per-n` / `--per-cell`，输出到新的 `batch00N_*` 文件名以免覆盖已填分结果。

## 2. ASR 窗口如何听写与打分

1. 打开 `eval/asr/windows/batch001_windows.csv`。
2. 点击 `youtube_url_t`，从 `start_s` 听到 `end_s`（约 2 分钟）。
3. **人工听写**参考文本（简体，标点可忽略），写入旁注或另存 `eval/asr/windows/refs/{window_id}.ref.txt`。
4. 对照 `asr_excerpt` / `data/artifacts/{video_id}/segments.jsonl` 同时间段文本。
5. 计算并填回 CSV：
   - `cer`：字符错误率（删/插/替）÷ 参考字数；目标 ≤ 0.08。
   - `term_recall`：窗口内应出现的词典术语中，转写正确保留的比例；目标 ≥ 0.90。可用 `matched_terms` 列作候选术语清单，再人工增删。
   - `notes` / `scorer` / `scored_at`（Asia/Shanghai 日期即可）。

既有自动化打分（需 asr-bench 参考窗）见 `eval/asr/score_v0_1.py`、`score_live.py`；全量讲座抽检以本 CSV 人工听写为准。

空白列模板：`eval/templates/asr_window_score.csv`。

## 3. 知识点如何判分

打开 `eval/kp/batch001_kp_review.csv`，对每一行：

1. 读 `statement`（转述）与 `evidence_quote`（≤40 字原文证据）。
2. 点开 `citation_url`（站内或 YouTube 时间戳），核对证据是否出现在所引时段、转述是否忠实。
3. 在 `verdict` 填：
   - **对**：证据可定位，转述无实质性错误；
   - **部分对**：大意对但有 ASR 污染、过度概括、时间略偏、缺关键限定等；
   - **错**：证据对不上、张冠李戴、或与原话明显相反。
4. `short_evidence=1` 的行优先复核（证据过短，定位弱）。
5. `notes` 写修正建议（改注释 YAML / 重跑 `knowledge-build`）。

空白模板：`eval/templates/kp_verdict.csv`（`verdict` 仅允许：对 / 部分对 / 错）。

## 4. 检索题 `qa.jsonl`

Schema（每行一个 JSON 对象；文件头用 `#` 注释，加载时请跳过）：

```json
{
  "id": "qa-001",
  "question": "……",
  "series": "shl",
  "gold_video_id": "shl-001",
  "gold_start_s": 35,
  "gold_end_s": 90,
  "tolerance_s": 30,
  "tags": ["concept_definition", "clause"],
  "notes": "草稿，可改"
}
```

命中规则（§9）：检索 top-8 中任一条落在 `[gold_start_s − tolerance_s, gold_end_s + tolerance_s]` 且 `video_id` 正确 → Recall 命中。已有约 50 题种子（`eval/retrieval/qa.jsonl`）；校验：`uv run python scripts/eval/validate_qa.py`。

## 5. 滚动任务建议顺序

1. 填完 batch001 ASR 窗 CER / 术语召回；不达标的系列加大 `--per-n` 再抽 batch002。
2. 填完 KP `verdict`；「错」「部分对」回流 `data/knowledge/<vid>/annotations/`。
3. 维护 `eval/retrieval/qa.jsonl`（已约 50；可继续增至 200）；改后跑 `validate_qa.py`。
4. 汇总报告：`eval/reports/{date}_spotcheck.md`（后续 stretch 可加汇总脚本）。

## 6. 注意

- **不要**为评测批量下载音视频；链接听即可。
- 勿改 ASR 原始 `segments.jsonl` 做“伪高分”；修正走 `segment_override` / 知识注释。
- 改词典或提示词后应重跑抽样或至少重评受影响窗口（§9 回归）。
