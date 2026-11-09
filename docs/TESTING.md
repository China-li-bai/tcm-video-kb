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

## PR-4：其余听课函数 / 数据边界（依赖 #17）

2026-11-09（Asia/Shanghai），基于 `fe3a904` 接栈，分支 `test/listen-function-boundaries`；只做方案 PR-4。先前真实浏览器 localhost 连接拒绝/网络地址 403 仍是**合并前独立门槛**，不等同 pass，本轮没有再次访问、启动预览或修改代理/隧道/网络控制。

### 先核对覆盖，不重建测试栈

原有 **76 项 / 5 文件**：发布加载器 38、CheckSheet SSR 2、静态播放逻辑/播放器 SSR 15、Watch/Home/文案 SSR 10、PR-3 DOM 交互 11。原有覆盖已包括 HTTP/结构与63份真实资产、请求秒/iframe事件、播放诚实语义、存储 effects；本 PR 不重复安装 Vitest/jsdom，也不复制这些测试凑数。

方案 PR-4 尚缺的四条链路是 **pickClaimsNear、pickChipsNear、搜索空态、摘要插值**。新增 **19 项 / 3 文件**：

| 文件 / 数量 | 实际契约 |
|---|---|
| `listenFunctions.test.ts` / 9 | KP 按区间距离 ≤45秒（不是仅句首距离）、重叠/置信度/起点排序、去重/上限/不改输入；芯片按句窗距离 ≤6秒、半秒最小窗/默认4秒窗、类型排序、同实体跨时间去重；空数组/NaN查询时间、max整项上限；摘要分句/空摘要/短章插值 |
| `searchBoundaries.test.ts` / 3 | 空白不下载/未命中为空；目录 trim/大小写/章节优先且不重复讲次；真实加载器消费小 HTTP fixture，乱序响应仍按目录/时间排，限量及未匹配为空，部分404不混入假结果，仅清单公开范围被请求 |
| `listenDataFlow.test.tsx` / 7 DOM | 真实 SearchPage 输入/空态/重搜；共享延迟请求时新查询不被旧查询覆盖；搜索命中→真实 WatchPage→既有秒定位；真实加载器→芯片去重/附近KP→点击证据/听主张；空或>45秒KP不造选项；跨讲次换源不保留上一集主张/证据 |

新增用小 fixture，不再读一遍4MB句稿；目录/章元数据仍由实际模块提供。原有63份资产回归不删。DOM 直接挂载组件、Router、加载器/缓存、状态/effects/localStorage，未 mock 搜索、picker 或被验收的业务逻辑。

### 真实 RED / 直接 GREEN / 最小修复

- 新测试编写时先暴露了测试自身的错误（chips opts 误传为第三参 endS、DOM 错把 role=listitem 当 button、全局 listitem 查询不够窄），**先纠正测试**，不把这些误报称为产品缺陷。
- 实现前，以修正后的 `cd web && npm test -- --reporter=verbose` 为证据：**4 failed / 91 passed（95项），exit 1**。原76项全绿；新增19项中 **15项直接绿、4项真实RED**，没有破坏正确实现造RED。
- 真实缺陷①②：两个 picker 的 max=0/负数本来会泄漏第1项；max 为小数或非有限值也不符合整项上限。现在先 floor，非有限或≤0返回空；默认3/正常排序和去重不变。此选项虽非当前UI默认调用，也是导出函数的有效边界，不宣称线上已发生用户事故。
- 真实缺陷③：摘要最少套30秒插值，合法的短章多片段会越过源章末尾。现在只用真实非负章跨度插值再 floor；首点可因取整早于小数章首不足1秒，不把近似定位称为逐句时间。公开数据本身未改，不声称发现了全库摘要错误。
- 真实缺陷④：选择KP后的二级说明仍写「核对过」，原SSR只覆盖未选择态。DOM 点击选项后抓到它；改为「本集已导出的知识点」，不修改数据审校状态或生成主张。
- 最终 `npm ci && npm test && npm run build`：**95 passed / 8文件 / 0 skipped**，TypeScript/Vite通过，audit 0；没有新增依赖或脚本/工作流改动。现有大 bundle/弃用提示保留。
- `uv run --no-sync pytest -q -ra --strict-offline --disable-socket --allow-unix-socket tests/unit tests/ci`：**94 passed / 0 skipped**。`python3 web/scripts/publish_manifest.py --check`通过；`python3 -m unittest discover -s tests/publish -v`：**14/14 OK**。

远端 CI 只以本次提交的 checks/job日志为准；本地绿不冒称远端绿。回滚用普通 revert PR-4，不移除 PR-1 的运行器/发布测试或 PR-3 的 DOM依赖。

### 没有扩大到哪些能力

没有做 PR-5 公共出处派生函数、历史 citation 回写、PR-9 iframe跟读、收藏导入导出/账号/数据库；未改21集JSON/原始知识/发布清单/媒体/样式或运行架构，不跑真实 knowledge-build/付费调用。搜索的部分切片加载失败仍只能返回其余有效结果，没有新增失败覆盖汇总，不把空态测试说成网络故障报告已完善。fixture模拟404不是线上路由已修复。

fetch只返回预期相对资产路径的fixture，无live fallback；jsdom不加载外部iframe资源、不访问YouTube。scrollIntoView/IntersectionObserver为缺失API替身，只验接线，不验几何/视觉/焦点遍历/真机/实际播放。手机PC定高、固定区与文稿内滚、YouTube实际跳秒/自动播放/备份路径仍需获准可访问的真实浏览器在合并前独立验收；不绕过403，不合 main、不部署，本轮不开始 PR-5。

## PR-5：出处只读派生（依赖 #18，未合并 / 未部署）

2026-11-09（Asia/Shanghai），基于 `adf41657521bf5c19cbb942da8ca1ca7e88b0f33` 接栈，head `feat/derived-citation-links`，base `test/listen-function-boundaries`。只完成本项；PR-6 仅检查输入文件清单，没有执行扩展。

### 真实 RED → GREEN，而非修改数据迎合测试

1. 在实现前写共享 Python/TS URL 契约、实际 model-read/CSV/API/真实组件 DOM 测试：
   - `uv run --no-sync pytest -q -ra --strict-offline --disable-socket --allow-unix-socket tests/unit/test_citation_projection.py tests/unit/test_api_graph.py`：初次 **29 failed / 9 passed**；补 model/时间边界后 **41 failed / 9 passed**，均 exit 1。失败包括旧 `?t=0`、危险 id、NaN 抛异常、缺少历史适配、API 原样透传危险链接/弱 host 检查。新增中直接通过的基础行为诚实保留。
   - `npm test --prefix web -- --reporter=verbose`：实现前 **24 failed / 95 passed / 10 文件**，exit 1，原95项全绿；失败真实暴露优先信任 `t_url`、非法秒/讲次可生成链接、来源缺覆盖说明、路径卡/对比表绕过安全组件等。
2. 后续实际调查发现：相同引用重复出现在 paths、旧嵌套时间 round 与外层秒存在4处 floor 跨界，分别补测再实现。重复 paths 边用例先 **1项真实 RED**（3卡而非2），时间优先级先 **1 failed / 39 deselected**（尚无实际 from_record 读取适配）。身份冲突测试首跑遗漏 `loads_snapshot` 的 origin 参数，随后修正并直接绿；此测试错误不计为产品 RED。
3. 逐一替换尚未接入的调用方前再次跑回归：修正测试自身的 recall 参数名/Watch CSS selector 后，**4 failed / 118 passed**：Stash 0 秒仍拼 `?t=0`、Recall 负数拼 `?t=-2`、resume 非法身份仍有链接，以及 Watch 仍请求未公开句稿。实现单一生成函数接线与 manifest 门槛。真实图详情父组件后来又测出时间标签显示 NaN/Infinity：**1 failed / 124 passed**，修复共享时间展示后全绿。测试不是只验复制出来的纯函数。随后补真实snapshot/API读边界的held身份冲突与危险slug，两项均先因未拒绝而RED，再补同一citation模型/held身份校验；不更改candidate审核状态。
4. 额外新回归直接 GREEN，未虚构 RED：全目录已知 id、发布实际404与200HTML边界、真实 slim CLI 21资产逐字节比对、实际 `knowledge-index` CLI 对坏时间/跨讲次引用非零且保留旧输出。原95项都保留；原「未覆盖集实际404」DOM用例因现在不再请求未公开文件而改为验证不请求，同时新增已发布集真实404，保留失败语义覆盖。
5. 原有零秒规范断言随明确合同变更更新（不删除旧测试、不减数量）：`test_play_and_cites` / `test_knowledge` 的 `?t=0` 改为省略；budget流水线将前缀断言强化为按实际起点完整匹配 canonical URL/Markdown链接。旧URL仍兼容打开；没有扩大 skip/xfail 或 continue-on-error。

### 完整本地复现（均 exit 0）

```sh
uv run --no-sync pytest -q -ra --strict-offline --disable-socket --allow-unix-socket tests/unit tests/ci
# 144 passed / 0 skipped（原94 + 50新增）
python3 -m unittest discover -s tests/publish -v
# 15 tests OK（原14 + 真实21份slim导出字节回归）
python3 web/scripts/publish_manifest.py --check
# publish manifest checked
cd web && npm ci && npm test -- --reporter=verbose && npm run build
# npm ci / audit 0；125 passed / 10文件 / 0 skipped（原95 + 30新增）；tsc --noEmit + Vite通过
```

未改依赖/锁文件/工作流。保留 FastAPI/httpx 弃用提示、npm esbuild install-scripts 提示及 Vite 大 bundle 提示，不隐藏警告。CI 使用原锁定 clean checkout + uv sync --locked / npm ci；远端状态与实际数量以本PR checks/job日志为准，不把本地绿冒称远端绿。

### 真实数据 / 分层边界

- 实际读取145集：**1575 个 KnowledgePoint + 624 个 KChapter** 都通过包含嵌套 citation 的真实 Pydantic 模型，原始1575条citation仍缺 t_url。上下文身份与外层时间用于只读投影，原始 source URL保留；精确引用缺失/非法时间或身份冲突明确失败。
- 真实 CSV 索引全量导出到两个 pytest 临时目录，所有1575 KP/624章均有规范站内链接与YouTube备份，四个导出文件两次字节一致；哈希检查确认调用前后所有原知识文件/CSV与公开/bundled JSON未改。独立发布CLI将21份slim知识JSON导出到临时目录，与公开文件逐字节一致。未往真实 `_index` 或 `public` 写入投影。
- `git diff adf4165 --quiet -- data/knowledge data/graph web/public web/src/data services/worker/src/graph_snapshot.json services/worker/src/graph_data.py` 通过；21集63资产、21章、catalog、manifest和图快照未变。37份既有eval删除与 `.superdesign`不恢复/提交。
- API 用进程内 FastAPI TestClient + 真实 snapshot reader/materialization；没有新增API。四个 Worker vendor 源文件按现有 build.sh copy步骤同步，现有源码/副本一致与图快照/实时读取等价测试均执行；不运行完整 Worker build/snapshot 刷新或云部署。
- DOM 覆盖真实 CiteLinks→router→Watch effects→iframe请求秒、已/未公开句稿、坏数据白话提示、YouTube-only历史来源、重复引用不突变、PathsPage卡/对比切换、Stash/Recall/Home接线及真实图详情元数据。只mock外部HTTP/缺失DOM API；不mock所验链接/读取/定位业务逻辑。jsdom默认不加载外部资源，无YouTube或live网络fallback。
- Python socket保护仍非OS级沙箱；已有完整测试中的临时lexicon构建、MockEngine/短合成音频/ffmpeg不访问真实模型。没有运行真实库knowledge-build、媒体下载、在线LLM或付费/云产品操作。

**真实浏览器 / 手机PC视觉 / YouTube仍未验，是合并前独立门槛。** 之前连接拒绝/浏览器403没有改成pass；本轮没有启动或访问预览，没有改host/proxy/隧道或绕过网络控制。jsdom/SSR/CI不证明定高/内滚几何、移动布局、真实跨源自动播放/跳秒/失败检测；iframe load仍不等于播放成功。合main/部署须另行批准。普通revert本PR即可回滚代码/导出新列，无原始数据/存储/数据库迁移。

### PR-6 输入只读核对（不执行）

`configs/pipeline.yaml` 和 `web/scripts/export_transcripts.py` 都要求 `data/artifacts/<video_id>/segments.jsonl`。本checkout的 `data/artifacts` **目录不存在**，匹配文件0；catalog145、现有公开句稿21、未公开124，未公开且具备输入的讲次为0。仅列文件/检查存在性，没有读取/扩展媒体、执行ASR或新导出。**PR-6当前不具备输入**；须先由后续任务提供获准的、待扩连续讲次的 segments.jsonl（保持时间/seq/身份契约），再决定该批。原21集公开JSON不能替代新讲次的原始segments输入，不擅自开始PR-6。

## PR-6：只读导出下一连续小批句稿

2026-11-09（Asia/Shanghai），基于 `bb33958` 接栈，base `feat/derived-citation-links`（依赖 #19），head `feat/listen-jgy-013-015`。只完成方案 PR-6；找到真实输入，故不实施条件备选 PR-7。

### 输入核查与范围更正

PR-5 的“缺 artifacts”仅适用于 `/workspace/tcm-video-kb-pr4`，不代表 box 全无。本次仅列 `/workspace` 顶层、授权 store 项目目录、已知三个 TCM 位置。原流水线 `/workspace/tcm-video-kb/data/artifacts` 有497个递归 segments 路径，其中145个 canonical catalog 讲次（另有demo/中间产物），覆盖原先未公开124集的文件存在性；PR3/PR4 checkout无 artifacts。未无边界扫描 home/其它 bot store、未触用户电脑、未新clone。仅 jgy-013..015 的内容经过验证，其余文件不能外推为可发布。

选当前金匮001..012后的连续三集；原计划只要求小连续批次，未指定数量。完整源行 video_id/cite.youtube_id 对 catalog、有限有序时间、非空文本与唯一连续 seq；33 KP/9章的 seq 起止均存在且秒数最大差为0。KP/章/实体来源与原流水线相同文件逐字节比较相同。不是 ASR 质量或医学正确性结论。

| 讲次 | 源句数 | seq | 秒范围 | 源 segments.jsonl SHA-256 |
|---|---:|---|---|---|
| jgy-013 | 1289 | 0..1288 | 1.84..7419.95 | `20f0a3933e799838c1b53bb0760ccce6602fb3d1b543f1159845d246b2a45b79` |
| jgy-014 | 903 | 0..902 | 0.05..4953.272 | `a5b13e93f6d6d57c85a289eaac8a85b838033386b8cfd5d245f866e4fee2d5ad` |
| jgy-015 | 1931 | 0..1930 | 2.07..11334.257 | `945afefc06d2d184af1058c770c0c235592086dbe686fcb77b540e5eacf44dc3` |

### 真实 RED → GREEN

- `uv run --no-sync pytest -q -ra --strict-offline --disable-socket --allow-unix-socket tests/unit/test_listen_release_batch.py`：数据发布前 **3 failed / 1 passed**。真实缺新三集资产/清单；原21资产与917原知识的固定基线保护直接绿，如实记录、不故意破坏。
- `python3 -m unittest discover -s tests/publish -k source_identity -v`：新增1方法，**3失败子测试**；缺 video_id、跨讲次、路径样式错误身份都被原 exporter 重贴为 shl-001 并退出0。最小修复为解析后严格验证源行对象及 video_id；不是硬编码三集特殊放行。
- `cd web && npm test -- --reporter=verbose src/listen/releaseBatch.test.tsx`：初次 jsdom file-URL 测试接线报错，**不计产品 RED**。修正为测试 JSON import + 受限 cwd/public 文件读取后，**3 failed**：实际 SearchPage 无法找到新三集的真实源样句。未 mock 搜索、组件、路由、播放器请求逻辑。
- 只读导出真实既有原输入，临时树中四层完整校验、真实三导出器各重复两次且字节一致、manifest重复两次一致后，新增12份公开/打包文件并生成清单。focused release **4 passed**、发布 **16 OK**；之后完整前端 **128 passed**。未增加测试 skip/xfail、continue-on-error 或减少既有用例。

### 本地完整回归

```sh
uv sync --locked
uv run --no-sync pytest -q -ra --strict-offline --disable-socket --allow-unix-socket tests/unit tests/ci
python3 -m unittest discover -s tests/publish -v
python3 web/scripts/publish_manifest.py --check
cd web
npm ci
npm test -- --reporter=verbose
npm run build
```

实测 Python **148 passed / 0 skipped**（144+4）、发布 **16 OK**（15+1）、前端 **128 passed / 0 skipped / 11文件**（125+3），manifest、`tsc --noEmit`、Vite通过。`uv sync --locked` 检查35包；npm ci安装234包/audit0、无依赖/lock/workflow改动。保留 FastAPI/httpx 弃用、esbuild allowScripts 及大 bundle 提示。远端干净runner安装和实际 job 日志以本PR checks / 主线Page记录为准；本地绿不冒称远端已绿。

新DOM每集抽1条真实样句：原public字节作为唯一受限HTTP响应，SearchPage→实际检索命中→Link/Router→WatchPage句稿→显式点听→catalog YouTube iframe请求 floor(start_s) 秒；不显示未公开/假进度/假实时播放。`fetch` 不允许任何外站URL，jsdom默认不加载iframe子资源；缺失Observer/scroll API只替身接线。不覆盖视觉、真实滚动几何、焦点遍历、手机、YouTube播放/自动播放限制或跨源故障探测。先前浏览器403仍是合并前独立门槛，本次没有重试/启动预览/更改代理或隧道。

### 离线重现与审计边界

默认导出id及运行覆盖仅来自生成manifest；历史审计收据 `docs/releases/pr6-jgy-013-015.audit.json` 只用于测试/复核，不进入运行选择。CI不需要原始artifacts：验证收据绑定的规范投影/public字节、所有新KP/章seq时间、原21集84资产及全部917原始知识/catalog基线。**CI没有再次验证box原始segments文件**；这些原始哈希/源身份核对属于上述本地只读取证，收据保留重现依据。

在获准且有原输入的box上，可只写临时目录重现，不执行任何重建/ASR/下载：

```sh
# repo根目录；不是假设每台机器都存在此原工作目录
ARTIFACTS=/workspace/tcm-video-kb/data/artifacts
TMP=$(mktemp -d)
# 这里只指定本次历史批次；默认运行/导出不读取这份命令或审计收据
python3 web/scripts/export_transcripts.py --artifacts "$ARTIFACTS" --out "$TMP/transcripts" --ids jgy-013 jgy-014 jgy-015
python3 web/scripts/export_knowledge_points.py --out "$TMP/knowledge" --ids jgy-013 jgy-014 jgy-015
python3 web/scripts/export_entities.py --out "$TMP/entities" --ids jgy-013 jgy-014 jgy-015
python3 - "$TMP" <<'PY'
import hashlib, json, sys
from pathlib import Path
out = Path(sys.argv[1])
r = json.loads(Path('docs/releases/pr6-jgy-013-015.audit.json').read_text())
for item in r['episodes']:
    vid = item['video_id']
    for layer in ['transcripts', 'knowledge', 'entities']:
        assert (out/layer/f'{vid}.json').read_bytes() == Path(f'web/public/{layer}/{vid}.json').read_bytes()
    assert hashlib.sha256((out/'transcripts'/f'{vid}.json').read_bytes()).hexdigest() == item['projected_transcript_sha256']
print('All three actual exporters reproduce the committed batch byte-for-byte.')
PY
```

本批4,123句/33KP/1,522实体提及/9章，四层新增731,688字节，最大文件254,889字节；无对象存储迁移必要。总覆盖24/145，33,823句/4,563,201句稿字节；老21集84资产保持字节不变。知识1575KP/624章、CSV、catalog、图快照/嵌入文本未重写。37份既有eval删除与.superdesign保持未提交。没有knowledge-build/媒体/付费调用/云资源/新API/播放器策略/布局改变，不合main、不部署。普通revert整个PR连同清单与新增文件回滚，无数据库或存储迁移；PR-7仅为后续待办。

## PR-7：health构建修订号 / 内容版本

2026-11-09（Asia/Shanghai），base `feat/listen-jgy-013-015@90845dc`，依赖#20，head `feat/health-build-revision`。只做原方案PR-7；未实现PR-8、未合main/生产部署。

### RED → GREEN（不混淆测试接线与产品边界）

```sh
uv run --no-sync pytest -q -ra --strict-offline --disable-socket --allow-unix-socket tests/unit/test_health_revision.py
```

初次 **22 failed / 1 passed**：真实默认health只有status，缺unknown语义/注入参数/生成CLI/构建接线。失败包含尚未实现接口或模块，不称为22个线上缺陷；缺manifest负例因CLI尚不存在先直接绿，实现后再真正执行验证仍绿。补实现后23通过。追加真实built文件验证合同，`--dist`尚未支持先失败1项；shell集成首次因fixture的venv解释器接线报错，修正wrapper后直接绿，不计产品RED。新增早期缺venv故障用例确实 **1 failed**：旧身份尚留在磁盘；把清理提前到venv检查前，最终 **25 passed**。

25项覆盖：默认status兼容和unknown；缺/非法shape/schema、非法git/hash/时间戳/dirty类型、额外字段/环境不泄漏与输入不可变；真实临时Git仓库HEAD/clean/修改/删除/untracked、无Git/无git可执行文件；清单可重复/变化/缺失/过期、built字节变化/缺文件；生成模块→实际Worker entry→真实FastAPI/TestClient一致及缺注入；真实build.sh失败不留旧身份、成功仅最终注入。

Entry仅替身`workers.asgi.entrypoint`平台包装，graph_data/业务API/normalizer/实际生成模块不替换。shell故障集成真实执行现有graph生成和元信息CLI，npm仅故障/顺序替身；**不以它冒称实际TS/Vite通过**。另有下述独立真实完整构建。所有发布fixture/Git repo/故障修改都在临时目录，没有下载媒体、模型或请求云资源。

### 完整本地回归与实际离线打包

```sh
uv run --no-sync pytest -q -ra --strict-offline --disable-socket --allow-unix-socket tests/unit tests/ci
python3 -m unittest discover -s tests/publish -v
python3 web/scripts/publish_manifest.py --check
cd web && npm ci && npm test -- --reporter=dot && npm run build
```

**173 Python passed/0 skipped**（148+25）；**16发布OK**；**128前端/11文件/0 skipped**；manifest、tsc/Vite、npm ci audit0通过。既有4处health精确断言更新为附加字段的完整unknown响应，status仍ok；旧功能测试保留。API vendor新增normalizer与app逐字节相同，既有vendor比较通过；无依赖/lock/生产配置改变。

额外在临时源码树真实运行完整 `bash services/worker/build.sh`，拷贝仅所需已跟踪源码/知识/public/config/lexicon及本PR新module，排除eval/.superdesign、node_modules、python_modules、真实.git；复用本checkout已安装Python解释器，用PYTHONPATH指向临时源码。设置npm_config_offline=true/npm_config_audit=false仅让临时npm ci用已存在缓存，未改脚本生产策略或依赖。原命令真实完成vendor同步→graph snapshot/embed→npm ci→tsc/Vite→built JSON hash复核→新身份模块，重复生成字节一致。初次临时副本漏掉TS测试所import的tests/fixtures和docs/releases而失败；补齐后完整构建通过，**不算产品RED**。真实根目录TS/Vite始终通过。

随后 `uv build <临时副本>/services/worker/vendor/tcmkb_api --wheel --offline --out-dir <临时输出>` 成功，wheel内tcmkb_api/app.py与build_info.py同源码，验证非editable安装包含新增模块。没有运行pywrangler/云端Pyodide/部署；这不是完整平台集成验证。临时graph生成未写回本checkout；原知识、24集public/chapters、manifest、图快照/graph_data与base的git diff为空，保留原37份eval删除/.superdesign。

实际无git临时副本生成内容（**测试输出，不是生产观测**）：schema=tcm-build/1，git_sha=unknown，git_dirty=null，content_revision=`129c0907a299f5018912f46de8de7f4482dca69cf1c84035b0a2e17a918e3d8e`。真实checkout向临时out采集则是当时HEAD `90845dc...` 与dirty=true（包括既有删除/untracked），不是宣称该HEAD最终已部署；生成物不提交，最终构建必须重新采集。

保持FastAPI/httpx弃用、esbuild allowScripts、大bundle警告；不减测试/skip/continue-on-error。远端CI实际job结果另记PR正文与主线Page，不把本地通过冒称远端已绿。CI完整跑此25新增合同与全部旧Python，以及独立实际前端build；临时完整Worker/npm离线构建及API wheel属于上述本地额外验证，未声称CI执行pywrangler。

### PR-8测量前提（非实现或触发结论）

当前清单24句稿共4,563,201字节、最大602,420字节，仅为资产盘点，未达到原方案约15MB总量条件；官方单文件上限本轮没查。目标手机冷/热缓存下的端到端等待、请求数与传输/解压字节、TTFB/下载/解析/子串匹配/结果渲染CPU及长任务/内存均未测，不能断言体验已失败或良好。后续须在获准可访问环境指定目标设备/网络/缓存/代表关键词，分开首搜/复搜与完整结果延迟、记录是否确有只传最多40条而不下整集的产品需求，再按原5.2触发条件决定是否做静态索引。未启动预览/重试403或加测量服务，不实现PR-8。

真实浏览器/手机PC定高、固定播放器/底栏、内滚、YouTube实际跳秒/播放/失败备份仍因先前403未验，是独立合并前门槛。health不是全功能可用证明。普通revert整个PR7并移除或重新生成版本模块回滚，无数据/数据库迁移。

## PR-10: local learning backup/import (original plan number)

Base `feat/health-build-revision@dc83928` (#21); PR-8 deferred, PR-9 research
blocked without code. This feature does not start PR-11 or bypass the browser403.
Contract, merge policy and non-atomic recovery limits: [LEARNING_STATE.md](LEARNING_STATE.md).

RED evidence (before feature implementation):

- `cd web && npm test -- --reporter=verbose src/listen/learningBackup.dom.test.tsx`:
  **7 failed / 0 passed**, exit1 against real pre-feature StashPage. Missing
  download/file/confirm controls; damaged object storage actually crashed
  `items.map`. Log: development scratch `/workspace/pr10-dom-red.log` (not a CI
  dependency). An earlier wrong working-directory/no-test-files invocation is
  a harness error and **not** counted as RED.
- Initial schema suite collection failed because `learningBackup.ts` did not yet
  exist: **one failed suite, no executed tests**, not 43 discovered product bugs.
  After implementation its first 43 contracts passed directly.
- Additional contract-first review: **4 failed / 51 passed**, exit1: missing
  actual quote/request preview, stale success message after blocked download,
  and two invalid Date.parse rollover cases. All fixed minimally. Two later
  FileReader tests initially used Element-only `fireEvent.load` on EventTarget;
  corrected to native ProgressEvent dispatch inside `act`, not product RED.

GREEN: **193 frontend tests / 13 files / 0 skipped** = previous128 + **65 new**
(**50 schema/merge/storage/recovery + 15 real DOM**). No old tests removed/skipped.
Actual StashPage, native FileReader, real router/storage/effects; only browser
I/O failures, Blob URL/download click and intentionally controlled read completion
are substituted. No mock of parser/merge/commit/recovery/components. New fixture
quotes are synthetic; fetch is a throwing spy with zero calls in every DOM test.
Covers allowlists/version/UTF-8 and record limits/calendar validity/legacy optional
fields/zero/fractional time/prototype/path/URL rejection, existing-first/ID/content
conflicts/capacity/no-op, denied read/journal/first/second writes, exact rollback,
failed rollback/cleanup/reload/restore or keep-current, stale preview, genuine file
selection/preview/no-write/confirm/cancel/download, read errors/races/unmount.

Full local regression commands (no models or external services):

```sh
uv sync --locked
uv run --no-sync pytest -q -ra --strict-offline --disable-socket --allow-unix-socket tests/unit tests/ci
python3 -m unittest discover -s tests/publish -v
python3 web/scripts/publish_manifest.py --check
cd web && npm ci && npm test -- --reporter=verbose && npm run build
```

Local full regression passed: **173 Python / 0 skipped**, **16 publication
contracts**, manifest check, clean `npm ci` (234 packages, audit0), and
**193 frontend / 13 files / 0 skipped** plus full TypeScript/Vite build.
These gates remain required in remote CI; PR body records its actual result. Existing FastAPI/httpx, Vite large-bundle and npm esbuild script warnings
are not skipped or represented as new failures. No new dependency/lockfile edits.
These offline/jsdom tests do not prove visual/mobile layout, real File picker or
download delivery, cross-process atomicity, browser eviction or actual YouTube
playback. Those remain separate premerge checks in an authorized reachable browser.

## PR-11: tracked QA schema/reference validation, NOT retrieval scoring

Base `feat/local-learning-backup@566c0ed` (#22). Actual unchanged input is
`eval/retrieval/qa.jsonl`:50 records/18429 bytes, SHA256
`dc83fcc9cbf97c9ffd8d8bfb67e0480e2420dcdbad3684492d5b51515edf3097`.
Contract, CLI/report/modes and limits: [QA_VALIDATION.md](QA_VALIDATION.md).

Genuine pre-implementation RED:

- `uv run --no-sync pytest -q tests/unit/test_qa_validation.py tests/ci/test_ci_contract.py`:
  **4 failed /5 passed**, exit1. Existing CLI actually returned0 and printed OK
  for empty, NaN and bool-second fixtures; CI had no QA gate. No code was broken
  to manufacture these failures.
- Later contract suite also failed primarily because the new `validate_qa`
  report interface was absent; those are interface RED, not dozens of observed
  baseline data defects. One reversed-interval fixture initially expected the
  start field instead of the diagnosed end field; corrected as a test assertion,
  not product RED. Missing lecture field diagnostics were completed.
- Source review tests before fixes: **1 failed** self-consistent but wrong
  YouTube ID/URL; then **2 failed** wrong/ambiguous URL seconds. Added catalog
  comparison and source-second checks; real50 still pass with historical
  0.05s rounding allowance. No original data rewritten to pass. One further genuine diagnostic RED exposed
  CSV parse errors reported at line0; now reports the physical CSV parser line.
  A final shared-source cache regression was genuinely RED (1 failed): a later
  question could be counted valid after a malformed native file was cached.
  Per-file integrity now invalidates every reference to that corrupt source.
  Final focused suite: **70 passed** (64 QA cases +6 CI contract cases).

Actual strict CLI ran twice, output byte-identical:
`python3 scripts/eval/validate_qa.py --strict-kp --json` → exit0, **50/50 valid,
0 errors,50 KP/50 unique KP/37 lectures/0 video-only**,40 hashed inputs. Series
shl15/jgy13/zj12/nj5/bc5. This is declared schema/reference consistency ONLY;
`answer_quality=not_evaluated`, `retrieval_metrics=null`.

Full regression uses the unchanged offline gate and all old tests:

```sh
uv sync --locked
uv run --no-sync pytest -q -ra --strict-offline --disable-socket --allow-unix-socket tests/unit tests/ci
python3 -m unittest discover -s tests/publish -v
python3 web/scripts/publish_manifest.py --check
cd web && npm ci && npm test -- --reporter=verbose && npm run build
```

Local final result: **238 Python passed /0 skipped** (173 existing +64 QA +1 CI
contract), **16 publish OK**, manifest checked, **193 frontend passed /13 files
/0 skipped**, `tsc --noEmit` +Vite build passed. `uv sync --locked` checked35
packages; clean `npm ci` installed234/audited235 packages, zero vulnerabilities.
Warnings retained: FastAPI/httpx deprecations and existing Vite large-bundle warning.
Remote CI evidence is recorded in the PR/Page after the actual jobs complete;
local success alone is not a remote CI claim.

No original knowledge/questions/public assets/graph or dependencies changed,
no model/retrieval scoring/knowledge-build, no skipped tests/continue-on-error.
Real browser/mobile/download/YouTube remain independent unverified gates.
