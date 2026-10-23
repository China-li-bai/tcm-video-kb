# 知识层（s09_knowledge）

把一集讲座转写变成可学习、可引用的结构：**章节大纲 → 实体 → 知识点**，每条都带
站内跳转链接（`/watch/{video_id}?t=<秒>`；YouTube 为备份字段）。schema 版本 `knowledge/1`，模型定义在
`packages/tcmkb_core/src/tcmkb_core/knowledge.py`（pydantic v2，`extra=forbid`；
`python -m tcmkb_core.knowledge` 打印 JSON Schema）。

## 产物（`data/knowledge/<video_id>/`，纳入 git）

| 文件 | 内容 |
|---|---|
| `annotations/*.yaml` | **阅读产物**（语义部分）：按窗口组写的章节、实体修正、知识点，只引用转写句序号 `seq` |
| `chapters.json` | `KChapter[]`：集 > 章（`<vid>.cNN`）> 节（`<vid>.cNN.sN`）；标题、1–2 句自述摘要、起止秒/句、条文 `clause_refs`（宋本编号）、六经、`citation` |
| `entities.jsonl` | `KEntity`：规范 id（词典 id，或 `new.<type>.<name>`）、类型、全部表面形式（ASR 原文）与修正形、剂量、提及列表（每条带时间与链接）、`asr_uncertain` |
| `knowledge_points.jsonl` | `KnowledgePoint`：`kp_id`、类型、中文转述 `statement`（≤160 字）、实体 id、章节 id、原文证据 `evidence_quote`（≤40 字，必须能在所引句中找到）、起止秒、`citation{video_id,url,youtube_id,youtube_t_url,series,episode,title}`、置信度、`asr_note` |
| `outline.md` | 人读大纲：章节目录（时间戳链接）、按章知识点、实体索引 |
| `build_report.json` | 计数、注释哈希、错误 |
| `_work/`（不入 git） | 阅读窗口 `windows/wNN.txt`（`seq 时间 文本`，头部附词典候选、条文匹配、s08 启发式章节） |

全系列汇总：`data/knowledge/_index/{entities,knowledge_points,chapters}.csv`。

实体类型：formula 方剂、herb 中药、symptom 症状、pattern 证候、disease 病名、six_channel 六经、
meridian 经络、acupoint 穴位、pulse 脉象、tongue 舌象、clause 条文、method 治法、person 人物、
book 典籍、zangfu 脏腑、concept 概念。知识点类型：formula_composition、formula_indication、
contraindication、clause_interpretation、diagnostic_rule、pathomechanism、treatment_principle、
herb_property、acupoint_usage、prognosis、clinical_tip、concept_definition、study_method。

## 流程

```bash
python -m tcmkb_ingest knowledge-prep  --video shl-007        # 1. 生成阅读窗口（12 分钟/窗）
# 2. 逐窗阅读，写 data/knowledge/shl-007/annotations/w00-03.yaml …（每 3–4 窗一个文件）
python -m tcmkb_ingest knowledge-build --video shl-007        # 3. 校验+解析+写产物+刷新 _index
python -m tcmkb_ingest knowledge-build                        #    不带 --video：重建所有已注释集
python -m tcmkb_ingest run --video shl-007 --to s09           # 或走流水线（记录 step_run）
```

`knowledge-*` 命令只读状态库，不写，可与 ASR 批处理并行。`s09_knowledge` 不在默认 `--to s08`
计划里；没有注释时它只生成窗口并返回 `needs_annotation`（不标记完成）。版本键 =
注释内容哈希 + 上游转写版本 + `configs/knowledge.yaml`。

### 注释格式（摘要）

```yaml
video_id: shl-001
window: w08-11
seg_from: 1084
seg_to: 1592
chapters:            # key 跨文件同名即合并；节用 parent；end 缺省 = 下一章起点 - 1
- {key: c12, title: 第13–14条 …, start_seq: 1295, summary: …, clauses: [13, 14], topics: [formula.gui_zhi_tang]}
- {key: c12.s1, parent: c12, title: …, start_seq: 1295, summary: …}
entities:            # 词典扫不到的提及：ASR 误听、剂量、新术语；reject 标记词典误命中
- {id: herb.ge_gen, seq: 1320, surface: 葛根, corrected: 葛根, dosage: 四至六钱}
- {id: formula.da_xian_xiong_tang, seq: 3264, surface: 大陷胸汤, reject: true}
kps:
- {type: herb_property, s: 葛根能升津液…, seq: [1303, 1314], q: 原文片段≤40字, ents: [herb.ge_gen], conf: 0.85, asr: 可选}
```

### 确定性部分（代码负责）

- 句序号 → 秒、引用 URL（`t = floor(round(start_s, 2))`，与 `KCitation` 校验一致）。
- 实体：词典最长匹配（排除 `course_term`、单字泛词；`acupoint` 需附近有「穴/针/灸…」；
  `exclude_auto` 列出同形异义 id，如 `acupoint.ex_tai_yang`），加 `aliases` 补充，再合并注释提及；
  知识点引用但未提及的实体自动补一条提及。
- 章节：跨窗口合并、补全终点、节限制在父章内、由条文推断六经；重叠或缺摘要报错。
- 知识点：证据原文必须在所引句（±1 句）中出现；同一顶层章节内同类型且语句相似度 ≥0.82 的合并（保留高置信）。
- `strict` 模式下任何错误都不写产物。

### 阅读约定

- 摘要与 statement 用自己的话转述，不粘贴转写；证据只摘 ≤40 字原文。
- 条文按**宋本编号**归一；倪师讲义编号与宋本常有偏移（如 shl-006 讲义 = 宋本 + 14；
  shl-001 自第 6 条起逐渐错位），讲义编号写在实体 `note` 里。
- ASR 误听写 `surface`（原文）+ `corrected`；拿不准标 `uncertain: true` / 降低 `conf`。
- 与现代医学相冲突的个人观点（疫苗、抗生素、心电图等）以「倪师个人观点」表述并降低置信度，
  或不收为知识点。

## 词典回流

`configs/knowledge.yaml` 的 `aliases` 和产物里 `in_lexicon=false` 的 `new.*` 实体是词典候选；
人工审核后并入 `lexicon/entries/`。注意：改词典会改变 s06 版本键，批处理运行时不要重建 `lexicon/dist`。
