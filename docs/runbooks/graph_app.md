# 方证图：API + 草稿边 + React/G6

学习用切片，主题是桂枝汤 / 太阳中风。输出不是诊疗结论。

关系方向：

| 谓词 | 方向 | 来源 |
|---|---|---|
| `treats` | 方 → 证 | `formula_indication` 知识点，半自动，仅 candidate |
| `indicates` | 症 / 脉 / 舌 → 证 | `diagnostic_rule` 知识点，更严，仅 candidate |
| `composed_of` | 方 → 药 | 词典 `relations`，`source=lexicon` |

硬闸（讲课边，缺一不可）：`confidence ≥ 0.90`，`evidence_quote` ≥ 12 字，时间窗 ≥ 15 秒，两端都是词典规范 id，`asr_uncertain` 的实体不能当端点。

- 方证半自动：一个方对多个证，或多个方对一个证，才写出 candidate。多方 × 多证不猜测配对。
- 辨证从严：一条知识点只保留一个证；多个证整条搁置，不交叉、不选「主证」。句里有「不是 / 并非 / 排除 / 不可 / 本无」也不写入。
- `review_status` 只有 `candidate`。检索只认 `approved`，这条流水线不会产生 approved。

当前语料里，`shl-001.kp0018`（脉浮、恶寒 → 太阳病）能过闸。`shl-001.kp0069`（桂枝汤 → 太阳中风）置信度 0.85，留在「未入图」，关系图上不画这条边，侧栏仍可点开 YouTube `t=`。

## 草稿边

```bash
# 在仓库根目录
uv sync
.venv/bin/python -m tcmkb_graph draft --video shl-001
```

写出（gitignore，可再生成）：

- `data/graph/candidates.jsonl`
- `data/graph/held.jsonl`

不带 `--video` 会扫 `data/knowledge/*/knowledge_points.jsonl`。API **不读** 这两份文件，启动后用同一函数现算，避免手改 JSONL 把 candidate 标成 approved。

## API 与页面

```bash
.venv/bin/python -m tcmkb_api
# http://127.0.0.1:8000/health
# http://127.0.0.1:8000/graph/subgraph?focus=formula.gui_zhi_tang
# http://127.0.0.1:8000/graph/paths?focus=formula.gui_zhi_tang

cd web && npm install && npm run dev
# http://127.0.0.1:5173/graph?focus=formula.gui_zhi_tang
# http://127.0.0.1:5173/paths?focus=syndrome.tai_yang_bing
```

Vite 把 `/graph` 和 `/health` 代理到 `127.0.0.1:8000`。API 没起来时，页面给出错误态，不画空图充数。

点节点或边可看到 cite。词典 `composed_of` 没有讲课时间戳；讲课边和「未入图」条目带 YouTube `t=` 与站内 `/watch/{id}?t=`。

路径页按证分轨，轨与轨、卡与卡同权（按 id 排列，不按置信度）。桂枝汤目前没有过闸的 `treats`，路径页是空轨加未入图说明。太阳病提纲可看 `shl-001.kp0018` 的两张同权卡。

## 校验

```bash
uv sync
.venv/bin/pytest -q tests/unit/test_draft_edges.py tests/unit/test_api_graph.py
cd web && npm install && npm run build
```
