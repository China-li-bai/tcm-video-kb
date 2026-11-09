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
| `knowledge_points.jsonl` | `KnowledgePoint`：`kp_id`、类型、中文转述 `statement`（≤160 字）、实体 id、章节 id、原文证据 `evidence_quote`（≤40 字，必须能在所引句中找到）、起止秒、`citation{video_id,url,t_url,youtube_id,youtube_t_url,series,episode,title}`、置信度、`asr_note` |
| `outline.md` | 人读大纲：章节目录（站内 `/watch/{id}?t=` 时间戳链接）、按章知识点、实体索引 |
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

### 引用字段（与 ingest `cite` 一致）

| 字段 | 含义 |
|---|---|
| `citation.url` | 源平台 URL；新产物通常是页面 URL，历史文件常已带时间戳，读取投影保留原值 |
| `citation.t_url` | **派生主链接**：站内 `/watch/{video_id}?t=<floor秒>`，零秒省略 `t` |
| `citation.youtube_t_url` | YouTube 备份 `&t=<秒>s` |

新构建约定中，实体的 `first_url` / `mentions[].url` 是站内跳转（等同 `t_url`）；**不能据此认定历史文件已迁移**。历史实体/CSV 仍可能是 YouTube URL。

### PR-5：只读出处投影，历史产物尚未回写

此节是开发栈实现，未合 main / 未部署。145 集原始知识中，1575 个 KP 的 citation 都缺 `video_id/t_url/youtube_t_url`，上下文在外层记录；旧 `_index/*.csv` 因而仍是此前回退 `citation.url` 的历史产物。本 PR **没有回写这些 JSON/JSONL/CSV**，也没有执行真实库 knowledge-build/backfill。公开 21 集的 63 份 JSON、21 份章节、catalog、发布清单和图快照/嵌入文本逐字节未改。

- Python `KCitation.from_record(record)` 使用外层 `video_id/start_s/end_s`，复制并适配嵌套 citation；`KnowledgePoint` / `KChapter.model_validate` 在实际读取边界接入。单独读取一个旧 citation 时用 `KCitation.from_legacy(citation, video_id=已知上下文)`，不能凭任意 `t_url` 猜讲次。直接构造新 `KCitation` 仍校验完整规范字段，不能把缺上下文当成合法新产物。
- 外层时间优先：旧 KP 中有 725 处外层秒与嵌套两位小数值不同，差值最大约 0.005 秒，其中 4 处跨越 floor 秒边界；章节有 269 处微小差异、无 floor 跨界。新读投影与前端 slim KP 使用同一外层起点，不进行二次 round；单独适配 citation 则使用它自身的秒。原值不写回。
- `site_watch_url` 与前端唯一 `watchHref` 的站内规则由同一 JSON 契约 fixture 检查：有效 slug；有限数字（拒绝 bool/数字字符串/NaN/Infinity）；负数夹到 0；小数 floor；0/缺时间打开本集且不加 `t`。旧 `?t=0` 入口仍可打开。精确知识引用缺/坏起止秒、倒序区间或上下文身份冲突则失败，不伪造 0 秒引用。
- 前端额外要求 catalog 中确有讲次，不要求已公开句稿才准听。`t_url` 从不作为跳转输入；`CiteLinks` 在图详情、路径卡/对比表共用，按发布清单说明「已有句稿（以加载结果为准）」/「暂未公开句稿，可先听原讲」，信息不全/坏时间给白话提示。Watch 不请求清单未公开的句稿，仍能使用原来的 YouTube 嵌入定位；不宣称实时播放、跟读或播放成功。
- 原平台备份由有效 source id 或精确 HTTPS YouTube/youtu.be host+id 重建，不透传任意 `url/youtube_t_url`；已知前端讲次以 catalog 的 YouTube id 为准。历史 `citation.url` 原样保留为来源元数据，不把不可信原字符串直接做可点击链接。已知 0 秒的 YouTube 备份保留合法 `t=0s`；这不是已播放进度。
- 文件型 `build_index(root, out=临时目录)` 实际接入同一投影：新导出 `url` 是站内起点，新增末尾 `source_url/youtube_t_url` 保留原始来源与安全备份。默认输出位置仍是 `_index`，但本 PR 仅向临时目录导出验证，**未重刷入库 CSV**。缺/坏引用先失败、非零退出，不替换已有索引文件；调用方若依赖 CSV 精确列数，需适配新增的两列。
- API 在现有 graph/subgraph、paths、held/mention 读取边界派生链接，拒绝非有限秒/候选边身份冲突，精确重复边去重而不合并不同症/脉主语；没有新接口或检索/审核状态变化。`end_s` 保留为证据区间，点击链接只请求起点，不承诺自动停止。Worker 的四个变更源码副本同步，原图快照未重刷。

全量历史模型兼容：1575 KP + 624 章均实际通过模型读取；临时 CSV 全量导出两次一致；21 份现行 slim KP CLI 导出与公开文件逐字节一致。完整命令和真实 RED/GREEN 见 [TESTING.md](TESTING.md)。这些是离线/DOM 合同验证，不是手机视觉或真实 YouTube 播放验收。

### 确定性部分（代码负责）

- 句序号 → 秒、引用 URL（`t = floor(round(start_s, 2))` → `citation.t_url`，与 `KCitation` 校验一致）。
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
