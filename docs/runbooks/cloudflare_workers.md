# 方证图：Cloudflare Workers

把已经在本地跑的 FastAPI + Vite/G6 切片部署成公开的 `*.workers.dev` 站点。本地 `python -m tcmkb_api` 和 `cd web && npm run dev` 不变。

Worker 名是 `tcm-fangzheng`。部署完成后 Wrangler 会打印账号子域，页面是：

| 用途 | 路径 |
|---|---|
| 关系图 | `https://tcm-fangzheng.<subdomain>.workers.dev/graph?focus=formula.gui_zhi_tang` |
| 路径分轨 | `https://tcm-fangzheng.<subdomain>.workers.dev/paths?focus=syndrome.tai_yang_bing` |
| 健康检查 | `https://tcm-fangzheng.<subdomain>.workers.dev/health` |
| 子图 JSON | `https://tcm-fangzheng.<subdomain>.workers.dev/graph/subgraph?focus=formula.gui_zhi_tang` |
| 路径 JSON | `https://tcm-fangzheng.<subdomain>.workers.dev/graph/paths?focus=syndrome.tai_yang_bing` |

`<subdomain>` 是该 Cloudflare 账号的 workers.dev 子域，以 `pywrangler deploy` 的输出为准。`workers.dev` 地址默认公开，没有登录墙。

边的中文显示名（组成 / 主治 / 提示）在 `web/src/graph/styleRegistry.ts` 的 `PRED_LABEL`，打进 Vite 包，不在 API JSON 里。API 仍用英文谓词 `composed_of`、`treats`、`indicates`。

生产构建不要设置 `VITE_API_BASE`。前端用相对路径请求同一来源。只有本地 `npm run dev` 才把 `/health`、`/graph/subgraph`、`/graph/paths` 代理到 `127.0.0.1:8000`。

## 知识数据怎么进 Worker

不把 `data/knowledge` 的 JSONL 打进 Worker。这批文件大约 21MB，实体行里带着每次出现的长列表，子图接口用不到。

部署用的是 `services/worker/src/graph_snapshot.json`（大约 450KB），由同一套硬闸生成：

```bash
.venv/bin/python -m tcmkb_graph snapshot \
  --out services/worker/src/graph_snapshot.json \
  --embed services/worker/src/graph_data.py
```

Worker 实际 import 的是旁边的 `services/worker/src/graph_data.py`（同一份 JSON 放进 Python 字符串）。Wrangler 会把这个模块打进脚本。`graph_snapshot.json` 是给人看、给单测对照的那一份。

`services/worker/vendor/` 是 `tcmkb_core`、`tcmkb_graph`、`tcmkb_api` 的副本。pywrangler 按非 editable 安装它们，把源码复制进 Worker，而不是留下指向仓库目录的链接。`build.sh` 会按这三处源码重刷副本；单测 `test_worker_vendor_matches_source_packages` 要求两边文件一致。

快照里有四块：

- `edges`：过闸的 candidate 讲课边。Worker 加载时再用 `CandidateEdge` 校验，`review_status` 只能是 `candidate`，改文件不能标成 `approved`。
- `held`：未入图的方证 / 辨证知识点（含 cite）。
- `index`：整份词典 id、词面、类目、`composed_of`。焦点不在词典里仍是 404，在词典里就能开子图，不限于桂枝汤。
- `mentions`：每个词典 id 的第一条讲课时间戳（优先 `shl-001`），用来给方、药节点做 cite。

词典或 `data/knowledge` 变了要重新生成这份文件。单测 `test_checked_in_worker_snapshot_matches_live_api` 会对照当场 `materialize()` 的结果，对不上就失败。

未压缩 Worker 脚本上限是 64 MiB。快照和 FastAPI 远小于这个数。Vite 的 `web/dist` 走 [Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/)，不占脚本体积。单个静态文件上限 25 MiB。

模式跟官方的 [Python Workers + FastAPI](https://developers.cloudflare.com/workers/languages/python/packages/fastapi/) 一致：`workers.asgi` 挂现有的 FastAPI，静态资源用 `assets`。`/graph` 和 `/paths` 没有对应文件时由 `not_found_handling = "single-page-application"` 返回 `index.html`。只有 `/health`、`/graph/subgraph`、`/graph/paths` 先进入 Python。

## 构建

仓库根目录：

```bash
uv sync
bash services/worker/build.sh
```

脚本会重刷 `services/worker/vendor/`、重写快照和 `graph_data.py`，并在 `web/` 里 `npm ci` 后 `npm run build`。产物在 `web/dist`。Wrangler 配置指向这个目录（`services/worker/wrangler.jsonc` 的 `assets.directory`）。

只校验、不部署：

```bash
uv sync
.venv/bin/pytest -q tests/unit/test_draft_edges.py tests/unit/test_api_graph.py
cd web && npm ci && npm run build
```

## 部署

不需要把密钥写进仓库。`compatibility_date` 为 `2026-10-30` 时，pywrangler 使用 Pyodide 3.14，所以这个目录的 `requires-python` 是 `>=3.14`（仓库其余部分仍是 `>=3.11`）。在 `services/worker`：

```bash
cd services/worker
uv sync
uv run pywrangler login
uv run pywrangler deploy
```

`wrangler.jsonc` 里没有 `account_id`，用的是登录账号。要固定账号时取消该文件里 `account_id` 那一行的注释再填。Worker 名 `tcm-fangzheng` 与账号里已有的 Worker 分开。

部署前可以看打包体积（不会上传）：

```bash
cd services/worker
uv run pywrangler deploy --dry-run --outdir ../../tmp/tcm-fangzheng-bundle
```

`Total Upload` 是未压缩脚本大小，对照 64 MiB。dry-run 不证明线上绑定可用。

日志和 traces 在配置里开着（`observability`）。流量变大后可以把 `traces.head_sampling_rate` 再调低。

## 本地对照

```bash
uv sync
.venv/bin/python -m tcmkb_api
# http://127.0.0.1:8000/health

cd web && npm install && npm run dev
# http://127.0.0.1:5173/graph?focus=formula.gui_zhi_tang
# http://127.0.0.1:5173/paths?focus=syndrome.tai_yang_bing
```

本地 API 现算 `materialize()`。`npm run dev` 下接口失败时，页面提示先启动 `127.0.0.1:8000`。生产构建的失败文案只要求刷新重试。
