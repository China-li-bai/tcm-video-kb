# Python 全量离线 CI 门槛（PR-2）

依赖 PR-1 #15，基于 `5da1350` 接栈；本 PR 不合 main、不部署、不改产品功能。

## 「全量」的准确含义

CI 不再点名两份图测试。运行所有 `tests/unit/` 文件与新增 `tests/ci/` 配置/门禁测试，保留 PR-1 的独立 `tests/publish/` 和前端检查。

| 层 | 本次文件 / 测试数 | 能证明什么 |
|---|---:|---|
| `tests/unit` 全目录 | 13 / 86 | 已有全部 Python 测试，未删除断言、未用 `-k`/`-m`/ignore 筛选 |
| `tests/ci` 全目录 | 2 / 8 | workflow 锁定依赖、全目录运行、必要工具与失败传播；实际子进程验证跳过会失败、缺网络保护会失败、Python INET socket 被阻止 |
| `tests/publish` | 1 / 14 | PR-1 的清单/导出契约，独立 unittest 命令保持不变 |
| 前端 | 2 / 40 | PR-1 的 HTTP/结构校验、真实 63 份 JSON、SSR 提示；另跑 TypeScript/Vite 构建 |

数目是本次记录，不作为硬编码通过条件。CI 不会因为只剩少量测试也宣称整个产品已验证；目录定义、收集范围由配置契约测试约束。现有 Python 86 项全部进入门槛；没有将任何旧测试移出门槛。

## 安装与执行

CI 固定 uv `0.13.7`、Python `3.12` 系列，系统安装 ffmpeg（含 ffprobe），检查 git。不加 ASR extra；`uv.lock` 唯一新增的是 dev 用 `pytest-socket==0.8.1` 及其关联元数据。

```sh
# 环境准备允许包仓库/工具下载，但不是测试期外部服务调用。
# Ubuntu 需安装 ffmpeg；ffmpeg、ffprobe、git 必须可执行。
uv sync --locked
python3 web/scripts/publish_manifest.py --check
python3 -m unittest discover -s tests/publish -v
uv run --no-sync pytest -q -ra --strict-offline --disable-socket --allow-unix-socket tests/unit tests/ci
cd web && npm ci && npm test && npm run build
```

- `uv sync --locked` 在 manifest/锁文件不一致时失败，不在 CI 自动解新版本；`uv run --no-sync` 不再次修改环境。
- `pytest-socket --disable-socket` 禁止测试进程的 Python 网络 sockets；允许 Unix sockets 供 asyncio/进程内 FastAPI TestClient 使用，不允许 TCP loopback 例外。
- `--strict-offline` 是本仓库显式 CI 策略：未开启网络保护或缺 ffmpeg/ffprobe/git 则失败；发现 skip/xfail/xpass 也失败。没有 continue-on-error 或忽略 pytest 返回码。
- 这不是 OS 级网络沙箱；pytest-socket 不隔离 C 扩展、外部可执行程序或任意子进程。现有 ffmpeg 只读临时合成文件，API 是进程内 TestClient；独立发布脚本只做本地文件变换。不得把此保护宣称成全进程防火墙。
- 开发者仍可直接跑某份 pytest；严格门槛以完整命令为准。缺工具导致的既有 skipif 不被删除，但在严格门槛中不能用 skip 混过。

## 不依赖本机预构建产物

`test_corrections_pipeline.py` 之前在 `lexicon/dist/corrections.json` 不存在时跳过两项。现在从已入库 lexicon 源编译到 pytest 临时目录，再让真实 Corrector 消费生成 JSON；原断言保留，实际运行两项，不用假的 hardcoded Corrector。

不会生成/覆盖仓库 `lexicon/dist`、不会回写 eval 或知识数据。其他 lexicon 测试已有临时输出，ASR/budget 流水线测试使用临时目录、合成短 WAV、真实本地 ffmpeg 和已有 MockEngine，不加载 FunASR 模型。

## 本轮 RED → GREEN（2026-11-09，Asia/Shanghai）

1. 先新增 8 项配置/门禁契约，运行 `uv run --no-sync pytest -q tests/ci`：**6 failed、2 passed，exit 1**。失败直接指出 CI 只选择两个文件、未锁依赖、未准备媒体工具，以及严格策略尚不存在。
2. 实现 CI、严格门槛与临时词典 fixture；运行完整离线命令：**94 passed、0 skipped**，Python 3.14 本地环境通过。
3. 用全新外部 venv 和空 uv 缓存复现：

```sh
UV_PROJECT_ENVIRONMENT=/workspace/tcm-pr2-clean-venv \
UV_CACHE_DIR=/workspace/tcm-pr2-clean-cache \
uv sync --locked --python 3.12
# 后续命令使用同样两项环境变量
uv run --no-sync pytest -q -ra --strict-offline --disable-socket --allow-unix-socket tests/unit tests/ci
```

实际 Python `3.12.16` 安装 35 包；单独断言 `torch`、`funasr`、`modelscope` 均未安装。完整套件 **94 passed、0 skipped**。初始化会下载 Python/包，测试阶段不调用外部服务。安装路径只是本地复现记录，不写进 CI 或运行代码。

4. 发布回归 **14/14**、清单检查通过；前端 `npm ci && npm test && npm run build` **40/40 + tsc/Vite 通过**。
5. 既有 FastAPI/httpx 弃用警告 1 条、Vite 大 bundle 提示保留，不用 suppress 或移除测试掩盖。

GitHub CI 状态以该 PR checks 为准；本地通过不代表已合并或已部署。

## 集成验证的独立边界

没有执行真实 ASR/模型加载、媒体下载、线上 LLM、Cloudflare 部署/缓存/路由、真实 R2 账号签名或 YouTube 浏览器播放。它们不属于这 86 项离线 Python 测试，也不把 MockEngine 的成功当成真实模型质量。

这些外部集成没有被偷偷删除/skip；仓库当前没有其自动验收矩阵。要验证，需另行明确固定输入、模型/服务版本、网络/账号/费用许可与产物目录；不在这个 CI 里安装 ASR extra 或触发真实知识库重建。现有知识构建单测只在临时小 fixture 上验证代码，不等于对入库 145 集执行 knowledge-build。

## 回滚

普通 revert 本 PR 即恢复原 CI 选择与 fixture；不回滚/覆盖 PR-1 的发布清单和前端边界测试，无数据库或生产迁移。后续 PR-3 只有本 PR 测通后才安排；本轮不实施 PR-3。

## PR-3 播放诚实化验证记录

2026-11-09（Asia/Shanghai），box；依赖 #16，非部署验收。上文 PR-2 测试数为历史记录，以下为 PR-3 增量与实际回归。

| 命令 / 阶段 | 实际结果 |
|---|---|
| 实现前 `cd web && npm test -- --reporter=verbose` | 真实 WatchPage / Home / CheckSheet SSR 契约 **8 failed / 40 passed，exit 1**：旧 28%、无请求定位说明、上次听到/核对过文案均被暴露 |
| 实现前追加 `npm test` | 8 个相同断言失败，另有未实现 StaticYouTubePlayer 模块加载失败；不以缺模块代替上行真实 RED 证据 |
| 小数句首选择补测 `npm test` | **1 failed / 62 passed，exit 1**，暴露 floor 秒使点击行错选；实现保留点击行身份后通过 |
| 真实小数章节边界补测 `npm test` | **2 failed / 63 passed，exit 1**，使用已入库 shl-001 / jgy-001 第二章，暴露整秒入口退回上一章；对齐请求秒契约后通过 |
| `cd web && npm ci` | 锁定安装成功，audit 0 漏洞；没有新增依赖 |
| `cd web && npm test` | **65 passed / 4 文件，0 skipped**；原 40 项保留，新增 25 项 |
| `cd web && npm run build` | `tsc --noEmit` + Vite 通过，保留既有大 bundle 提示 |
| `uv run --no-sync pytest -q -ra --strict-offline --disable-socket --allow-unix-socket tests/unit tests/ci` | **94 passed / 0 skipped**；既有 FastAPI/httpx 弃用警告 1 条 |
| `python3 web/scripts/publish_manifest.py --check` | 通过，公开清单/知识/句稿等数据没有变更 |
| `python3 -m unittest discover -s tests/publish -v` | **14/14 OK**，全部 21 集切片往返/导出回归保持 |

### 各层能证明什么

- **单位/纯逻辑**：请求秒归一化、空/间隙句选择、小数句首显式行选择、iframe pending→responded/failed、失败不会被随后 load 冒充清除、状态文案不承诺播放或跳秒成功。
- **真实组件 SSR**：MemoryRouter 中 WatchPage 的 URL t 与初始不开 iframe/无假条；真实小数章节入口；Home 从 localStorage fixture 读请求位置/深链；CheckSheet 不是人工审校措辞；StaticYouTubePlayer 生成不同 start 与原平台跳秒链接、请求未响应说明/重试、无片源不画假按钮。原发布测试还实际读取 63 份公开资产。
- **首提交 9d23697 当时没有运行 DOM 交互测试**：SSR 不执行 effects / 点击 / iframe load-error 回调 / IntersectionObserver。当时异步句稿到达后的 lastWatch 写入、路由来回切换、键盘/重试接线、滚动与焦点仅做代码审查。后续同 PR 补测见末节；保留此历史记录，不把当时的 SSR 绿追认成 DOM 已验证。
- **没有真实浏览器/YouTube/视觉验证**：未验证第三方可访问性、跨源失败事件、自动播放限制、跳秒是否真正落地、手机/PC 高度与文稿内滚。测试不访问 YouTube，也不伪造媒体时间，不跑真实知识构建或付费调用。

历史预览命令（不是生产部署；随后真实浏览器验收因连接拒绝/403受阻，当前不再重试，也不更改 proxy/隧道/网络控制）：

```sh
cd /workspace/tcm-video-kb-pr4/web
npm run dev -- --host 0.0.0.0
# 默认 http://localhost:5173/watch/shl-001?t=125 （端口占用以终端为准）
```

手验应覆盖手机/PC 定高和固定区、初开海报、点句/章与小数章边界、滚离所选句再返回、重试/备份链接、切集与返回首页的记录语义；iframe load 不能作为播放成功断言。CI 结果以 PR checks 及 job 日志为准，未合并/未部署；本轮不开始 PR-4。


## PR-3 同 PR 补测：真实组件 DOM 事件 / effects

2026-11-09（Asia/Shanghai），仍在 `fix/listen-honest-position` / #17 追加，不开始 PR-4，不开新 PR。用户反馈：localhost 连接拒绝，另一网络地址 Shell 200、浏览器 403；这不是通过的视觉验收。本轮没有再尝试浏览器，没有启动服务或更改 Vite host/proxy、网络控制或隧道。

### RED → 修复 → GREEN

1. 先新增 `watchInteraction.test.tsx`，用现有 Vitest，新增最小 dev 依赖 `jsdom@31.0.0`、`@testing-library/react@16.3.3`、其显式 peer `@testing-library/dom@10.4.2`；只有该测试文件使用 jsdom，不改变既有 Node/SSR 环境。
2. `cd web && npm test -- --reporter=verbose`：**3 failed / 71 passed（74 项），exit 1**。真实 DOM 事件暴露两类既有缺陷：原生不冒泡 iframe error 没接到 `onError`；嵌套「⋯」按钮收到 Enter/空格冒泡到句行，意外重新请求 iframe。不是故意删实现或只靠缺模块制造 RED。
3. 最小修复：iframe 使用 `onErrorCapture` 接收可见的原生非冒泡 error；句行键盘处理仅响应 `target === currentTarget`，子按钮自主管理激活，不触发 seek。没有新增播放策略、遥测、UI 布局或跟读。
4. 额外保留两项行自身 Enter/空格跳秒回归，防止守卫禁掉正常键盘操作。最初构建另指出测试代码把不支持的 `exact` 传给 role-query，已修正为其标准 name 查询；不忽略类型错误。
5. `npm ci && npm test && npm run build`：锁定安装成功、audit 0 漏洞；**76 passed / 5 文件 / 0 skipped（原 65 + 11 DOM）**；TypeScript + Vite 通过。既有大 bundle、安装脚本提示未压制。
6. 完整严格离线 Python 命令仍 **94 passed / 0 skipped**；manifest `--check` 通过；独立发布 unittest **14/14 OK**。FastAPI/httpx 弃用警告保留。CI 结果以本次追加提交的 PR checks / job 日志为准，不拿旧提交 CI 绿替代。

### 实际自动交互覆盖

测试直接挂载 **真实 WatchPage、StaticYouTubePlayer、ListenHomePage**，使用真实 Router、加载器/校验/缓存、localStorage 写入效果及真实事件 handler；不 mock 播放/选中/重试/持久化业务逻辑。

- 点击句子 → Router URL 请求整秒、iframe start/autoplay、原平台链接、aria-pressed 与 lastWatch 更新；再点另一句真正更换目标。
- 点击章 → 真实已入库小数章边界选中/句稿切窗/iframe start，随后点章内小数句不退回前一句或上一章。
- 延迟 fetch 完成 → lastWatch 仍保留 URL 请求秒，不被句首覆盖；海报按钮仍从该请求秒打开。
- 未公开集实际模拟 HTTP 404 → 白话无句稿提示；已公开集模拟 200 HTML → 加载失败提示和明确的章节摘要标签，不冒充逐句文稿。
- iframe 原生非冒泡 error → 失败提示；其后 load 不抹掉失败；点击重试换真实 iframe DOM 节点、保留同一目标秒并回到 pending；新 load 只说页面响应，不能确认播放/跳秒成功，不推进高亮或进度。
- 嵌套按钮 Enter/空格不会重试或启动播放器；句行自身 Enter/空格仍可跳秒。
- 通过合成 IntersectionObserver 回调验证「回到所选句」调用滚动但不 seek；切换真实 Router 讲次后清空旧 iframe 意图，返回讲次不假播放；回首页读到上次请求位置。
- 操作链无假进度条、已播放/正在播放/完成等状态声明。

### 隔离与仍未验证

`fetch` 仅返回固定的本地小 fixture（带真实章边界），同源 JSON/404/HTML；所有请求记录断言只访问预期的三个相对资产目录，没有 live-network fallback。jsdom 默认不加载外部 subresources，iframe URL 仅检查属性、不下载 YouTube；未执行 iframe 内部代码。测试用例之间清空模块缓存/存储、卸载组件和恢复全局替身。

只替换了外部 HTTP、jsdom 缺失的 scrollIntoView/IntersectionObserver 浏览器能力。后者验证调用接线，不证明真实几何、可见性或布局；没有自动化焦点遍历/屏幕阅读器验证。

**合并前门槛仍未通过：** 必须在获准且可访问的真实浏览器环境完成手机/PC 定高、固定播放器/底栏、文稿内滚与所选句返回，以及实际 YouTube 自动播放限制/跳秒/失败与备份路径验收。当前仍因浏览器 403 未验证；Shell 200、jsdom 76 项和 CI 绿都不能替代它。不绕过网络控制，不自动开始 PR-4，不合 main、不部署。跨源 iframe 没有 error 时仍无法判定，load 不代表媒体成功；此次 capture 修复不消除该边界。
