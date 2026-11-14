# 当前运行架构与发布契约

公网审查基线：`main@cc4c7f6`（2026-11-09，Asia/Shanghai）。本文件同时记录 PR-1–7 开发栈；下表为当前分支资产，**不是公网已生效**。新增行为须审阅合并并另行授权部署后才影响公网。`ARCHITECTURE.md` 是目标设计稿，不是运行现状。

## 运行与数据流

- 一个 Cloudflare Worker `tcm-fangzheng`：Vite/React 静态听课台 + FastAPI `/health`、`/graph/subgraph`、`/graph/paths`。图读已打包快照，不在请求里扫描知识库。
- 浏览器从同源静态 JSON 读取句稿、知识点、实体。问这句只取附近 ±45 秒内最多 3 条已导出知识点；查出处仍是浏览器子串匹配，无生成模型。
- 播放是 YouTube iframe；点句用 `start=` 跳秒。尚无连续播放跟读；旧 main 的 28% 装饰进度、lastWatch 语义在本开发栈 PR-3 修正（详见末节），不是公网已上线。
- 收获匣和上次点到的位置留在浏览器 localStorage，没有账号、上传或自动跨设备同步。PR-10开发栈支持用户自持JSON下载/预览/确认合并，未部署，详见下节及LEARNING_STATE.md。
- 请求路径没有 Postgres、向量、LLM 或自有 R2 音频；Python 构建流水线是离线工具。`web/stub_server.py` 与 HMAC 播放 stub 不是线上媒体服务。

## 覆盖不等于目录

| 层 | 当前入库数量 | 边界 |
|---|---:|---|
| 听课目录 | 145 | 五系列，均有 YouTube id；针灸 id 不连续 |
| 知识目录 | 145 | 已入库知识点和章节等，不等于公开句稿 |
| 公开句稿 / KP / 实体 / 打包章节 | 各 24 | 伤寒 001–008、金匮 001–015、本草 001；PR-6 新增金匮 013–015，运行选择仍只读生成清单 |
| 句稿 | 33,823 句 | PR-6 新增 4,123 句；shl-001 仍为 3604 句；句稿共 4,563,201 字节（原 21 集为 4,018,536 字节，逐字节未改） |
| 自有发布音频 | 0 | 不把 runbook 中的媒体规划视作已上线 |

知识点与章节的来源/审校状态不变，不能把本 PR 的格式校验称为医学正确性验证。历史知识 citation 仍有 YouTube `url`、缺 `t_url`；本 PR 不用新 KCitation 模型拒收历史产物，也不重写原始 JSON。

## 单一发布清单（本 PR 新增）

`web/src/data/publish-manifest.json` 由 `web/scripts/publish_manifest.py` 生成：

```sh
python3 web/scripts/publish_manifest.py          # 从已入库文件生成
python3 web/scripts/publish_manifest.py --check  # 只读重算，逐字比较；CI 门禁
python3 -m unittest discover -s tests/publish -v
```

输入为 `lectures.json`、`data/knowledge` 的实际文件及四个发布目录，不依赖本机 artifacts。清单不是第二份手工名单：前端 `TRANSCRIPT_VIDEO_IDS` 和三份导出脚本的默认 id 都由清单派生，原来的重复名单已移除。新增切片应先显式 `--ids` 导出/准备四层，再生成清单。

每条讲次记录目录/知识/公开层的布尔覆盖、知识点/章节/句子计数、播放来源；公开资产带相对路径、字节数、SHA-256 与条数。清单无生成时间、绝对路径或自引用 git SHA，生成可重复。`content_sha256` 是去掉该字段后的清单对象按 UTF-8、排序 key、紧凑 JSON 编码的 SHA-256；未来发布标识可组合 `git SHA + content_sha256`。main 审查时 `/health` 仍只有 status；本开发栈 PR-7 已增加下述构建修订号，未部署。

失败规则：

- 目录 id 重复、发布资产不在目录、文件内 id 不符、句序号/知识点/章节 id 重复、坏 JSON、非法/逆向时间、空句稿、空原句等均失败非零。
- 仅已公开的切片要求四层文件齐全且章节与句稿至少有一个时间交集；不是强迫其余 121 集产生尚未公开的资产（PR-1 当时为 124 集）。
- 知识点与实体允许空数组（真实无主张/所有实体被既有筛选器排除），但文件必须存在。未入库的知识目录可不存在，存在则检查核心产物与身份/计数，不做新 citation 格式迁移。
- 四层增删或任何资产字节变化使旧清单过期；`--check` 失败，必须审阅后重生成。生成先完整校验，成功后原子替换清单，失败不覆盖旧清单。

## 导出：不再 SKIP 后成功

```sh
python3 web/scripts/export_transcripts.py --artifacts /实际路径
python3 web/scripts/export_knowledge_points.py
python3 web/scripts/export_entities.py
# 新批次显式 --ids <目录中实际id> ...；--out 可写到临时目录检查
```

不传 `--ids` 时从清单相应公开层取 id。传空名单、重复 id、目录外 id 或缺失输入均非零。句稿默认 artifacts 为本仓库 `data/artifacts`，不再猜别的 checkout 路径。没有本地 artifacts 时，导出失败是正常而诚实的；生成/检查现有清单仍可运行，不去下载或运行 knowledge-build。

一个批次先写同文件系统临时目录，全部成功且通过公开形状校验才移动到目标；输入/校验错误不留下半批公开文件。最终移动时若磁盘/权限错误仍非零，但不保证多文件操作的 OS 级事务；不要部署失败的批次，恢复 git 版本后再重试。实体仍按既有类型、lexicon、非 new.*、非 uncertain 规则过滤和去重；不是强迫所有原始实体进入公开层。

## 前端失败语义与未解决项

三个加载器要求成功 HTTP 状态、JSON content-type、相同 video_id、合法数组/行/时间/身份；不会把 200 HTML 当句稿，也不再把坏时间变成 0。校验失败/网络错误返回 null，成功及失败均会话内缓存并保留请求去重。

学一段对已发布但无法打开的句稿/词条提示白话说明；摘要仍明确标记为章节摘要，不冒充逐句原文。问这句把「知识点暂时没能打开」与合法文件中「附近没有主张」分开显示。刷新可重新请求。

**本 PR 不改 Worker 入口或 wrangler 配置，未修复服务端真实 404。** 当前 SPA fallback 下缺失 JSON 仍可能返回 200 text/html；前端现在明确拒绝它。平台路由配置、缓存头/旧 HTML 缓存审计待独立验证，不能据本地测试声称线上已修复。搜索仍可在某些切片加载失败时只返回其余有效结果，未新增搜索覆盖故障汇总。

## 发布与回滚

CI 增加清单检查、独立 Python 发布契约测试与 `npm test`，保留现有两份图测试与 `npm run build`。本 PR 为验证加载边界提前引入 Vitest；PR-4 仍负责其余听课纯函数测试，不重复装运行器。完整 Python 单测 CI 扩围已由后续 PR-2 在开发栈实现，尚未合 main/部署；全量定义、离线保护与验证记录见 [TESTING.md](TESTING.md)。

本开发栈只提供分支/审阅 PR，不自动合 main、不部署生产。PR-1 不扩句稿；PR-6 只读导出下述三集。均不改定高内滚布局/CSS、不跑模型或 knowledge-build。回滚本 PR 用普通 revert；无数据库迁移。如日后部署，回滚为检出上一个已知 SHA，按现有 cloudflare_workers runbook 重建部署。

## PR-1 本地验证记录

2026-11-09（Asia/Shanghai），box 现有 checkout；未使用云端编码代理、未触碰用户机器。

| 检查 | 实际结果 |
|---|---|
| 测试先行 RED：`python3 -m unittest discover -s tests/publish -v` | 初始 11 测试，15 个失败断言/子测试，退出 1；直接暴露原导出缺输入仍 `done: 0/1`、退出 0 与半批输出 |
| 测试先行 RED：`cd web && npm test` | 初始 31 测试，13 失败，退出 1；包括 HTML 类型伪装 JSON、错误 video_id/时间/结构、尚未生成清单 |
| UI RED：同 `npm test` | 新增 SSR 提示测试先失败 1 项；原界面把文件不可用当成附近没有主张 |
| 发布契约 GREEN：`python3 -m unittest discover -s tests/publish -v` | 最终 14/14；包括临时目录中全部 21 集句稿往返、21 集 KP/实体导出逐字节不变 |
| `python3 web/scripts/publish_manifest.py --check` | 通过；重复生成相同、缺伴随文件不覆盖旧清单、变动/重复/错误身份/无时间交集均被测试拒绝 |
| 前端 GREEN：`cd web && npm test` | 最终 40/40，2 个测试文件；含 63 个真实公开 HTTP JSON 形状、并发请求去重/失败缓存、有效空层与重复行、SSR 提示 |
| `cd web && npm ci && npm audit` | 安装成功；audit 0 漏洞。Vitest 采用兼容 Vite 6 的已修补 4.1.12，而非有审计告警的旧 3.x |
| `cd web && npm run build` | TypeScript + Vite 通过；有现有大 bundle 提示，未在本 PR 夹带拆包 |
| Node 22 兼容检查 | 临时 Node v22.23.4 跑测试/构建通过（当时 34 项测试；最后追加的 6 项回归在 box Node 24 下通过） |
| `uv run pytest -q -rs tests/unit` | 84 passed，2 skipped（lexicon dist 未构建的 corrections 测试），1 条既有 FastAPI/httpx 弃用警告 |

未覆盖：真实浏览器/YouTube 播放、手机/PC 视觉复验、Cloudflare 路由/缓存行为、线上故障与生产部署；CSS/布局未改。未构建 lexicon dist 来消除那两项跳过，避免越过内容流水线边界。CI 远端结果以 PR 检查为准，本地绿不冒称远端已绿。

## PR-3：播放与接着听说实话（开发栈，未合并 / 未部署）

依赖 PR-2 #16，base `ci/full-offline-python@96b015c`。本节描述开发分支行为；上文 28% 为旧 main/公网基线，不再是此分支行为。

- 移除固定 28% 条、假 play/pause、自动完成暗示。显示的是「请求定位 mm:ss」和目录时长，不是媒体播放头或已播放比例。没有新增 IFrame API、轮询或播放遥测；跟读仍留 PR-9。
- 单位：URL `t` / iframe `start` / lastWatch.t 都是请求的**秒**，有限且非负后向下取整，无效值归 0；不是百分数、毫秒或播放器返回值。不擅自按未经媒体复核的目录时长截断。URL 请求 125 秒不会在句稿异步到达后被悄悄改记为句首。
- `selected` / CSS `.active` 只指手工导航的章/句：URL 按请求整秒选覆盖/最近前一章句，早于首条用首条；点句优先保留该句与章的身份，避免小数句首取整选到上一句。换视频/换目标后旧行选择失效。它们不代表正在播放、已听过或完成；「回到所选句」只滚文稿，不跳播放器。
- `requested` 只代表用户已请求挂载静态 iframe：初开页面仍先显示原有海报；点海报、句/章、听原讲才请求 iframe，保留原有 `autoplay=1` 与出处返回路径。换视频清除旧挂载意图，重试/新目标换 key 发起新请求。`pending` 是尚未收到页面 load/error；`responded` 仅收到 iframe load；`failed` 仅收到可见 error，下一次请求才清除，均不等于媒体 ready/playing/ended/跳秒成功。
- 浏览器经常不会把跨源 iframe 失败交给 onError，load 也可能只是错误页；不设置假超时成功，不承诺能检测所有失败。始终给请求状态白话说明、已请求时的重试，以及带同一目标秒数的 YouTube 备份链接；无片源只提示，不做假播放按钮。
- localStorage v1 保持兼容；「上次打开的位置」保存打开/点选请求秒，不是最后听到或播放结束位置。旧记录也不能追认成真实播放头。收下所选句/回首页是手工动作，不记完成；存储失败提示/迁移不在本 PR。
- 问这句改为「从本集知识点里摘出的主张」，不把 llm_read 说成人工核对。知识/句稿/实体 JSON 未改，21 集范围不变。
- 保持原定高 shell、固定播放器/底栏和文稿内滚结构；CSS 仅删假进度样式、重命名返回所选句选择器、定位标签允许换行。无视觉验证结果，不能据此宣称窄屏已手验。

测试先行、复现命令与边界见 [TESTING.md 的 PR-3 记录](TESTING.md#pr-3-播放诚实化验证记录)。本 PR 不改服务端 JSON 404，不合 main、不部署；普通 revert 即回滚本项代码/文案，无内容或存储迁移。


### PR-3 同 PR DOM 补测与合并前门槛

同分支追加最小 jsdom/React Testing Library 11 项交互测试，真实组件 effects/router/storage 与事件链通过；此前仅有 SSR 的记录不追认成 DOM 已测。测试先 RED 3 失败，发现并修复原生非冒泡 iframe error 的 capture 接线、子按钮键盘冒泡导致意外 seek 两类问题；前端现 76 项。详见 TESTING.md 末节。

真实浏览器/手机PC视觉仍未验证：浏览器 localhost 连接拒绝，网络地址浏览器 403（Shell 200 不代表可用）。本次未重试或改代理/隧道/网络控制，不使用浏览器自动化。jsdom 不运行 YouTube、不验证布局、真实滚动几何、焦点遍历或播放成功；外部 JSON 与浏览器缺失 API 使用受限 fixture/替身，业务组件逻辑不被替换。合并前必须在获准可访问的浏览器环境补完定高/固定区/文稿内滚、实际跳秒/播放限制/备份路径检查。自动测试绿不解除该未完成门槛；PR-4 暂不开始。

## PR-4：其余听课函数 / 数据边界（开发栈，未合并 / 未部署）

依赖 PR-3 #17 的 `fe3a904`。在原76项之上补19项（含7项真实组件DOM），覆盖方案的附近KP、芯片去重、搜索空态/新旧查询/跨讲次与摘要插值；不重复引入测试运行器/依赖，不扩数据或API。

仅修复测试证实的边界：两类picker的max按整项上限处理（floor，非有限或≤0返回空）；摘要位置按真实章时长插值，仍是近似而非逐句时间；选中主张后的遗留「核对过」改成「已导出」。默认45秒/6秒窗口、最多3项与排序不变，不实现PR-5出处派生或PR-9跟读。

测试命令、4项真实RED与15项新增直接绿、95项完整前端回归见TESTING.md末节。用户已单独授权串行接续本项，不表示真实浏览器403门槛已解除：手机/PC视觉与YouTube实际播放仍未验，保留合并前独立门槛，不访问预览或绕过网络控制；未合main/部署。普通revert回滚本项，不拆先前测试门槛。

## PR-5：出处派生（开发栈，未合并 / 未部署）

基于PR-4 #18 / `adf4165`，分支 `feat/derived-citation-links`。只读适配历史 citation，不回写原始知识、CSV、现行21集公开JSON、章节/catalog/manifest或图快照；无真实 knowledge-build/backfill。详细字段/时间优先级见 [KNOWLEDGE.md](KNOWLEDGE.md) 新节。

- 站内链接由 `video_id + start_s` 生成，统一 floor/负数夹0/0省略t；未知讲次、非法或非有限秒不制造精确跳转。旧 `?t=0` 可打开。前端不相信外传 `t_url`，所有现行带秒的听课跳转共用生成函数；原平台链接只由安全YouTube id/allowlisted URL重建，已知讲次以catalog为准。
- 图/路径出处使用共同组件说明已有/尚未公开句稿；打开后的真实加载失败仍如实提示。Watch不请求manifest未公开的句稿，保留原嵌入定位/原平台备份，不增加iframe API、遥测、跟读或假进度。布局/CSS/播放器策略没有改变。
- Python真实KP/章节model读取、CSV导出和既有API读边界接入投影。CSV新导出url是站内起点，末尾新增source_url/youtube_t_url；历史CSV未重刷。end_s仍是证据元数据，不代表播放器会自动停止。重复相同API引用边去重，保持不同主语/讲次与candidate状态；Worker四个源码副本同步但未部署。

先写测试真实RED后实现；全量本地144 Python、15发布契约、125前端、manifest/TS/Vite均通过。1575 KP + 624章全量模型读取，临时CSV两次一致，21份实际slim导出与现行公开文件字节相同；依赖/工作流不变。完整证据、直接绿的新增回归及未覆盖范围见TESTING.md末节，远端CI以PR checks/job日志记录为准。

真实浏览器/手机/YouTube仍因403未验，保持合并前独立门槛，未尝试预览/网络绕过。PR-5 当时只检查本 checkout：默认 data/artifacts 不存在、segments.jsonl 为 0，没有扩展句稿；该观察不能外推为整个 box 无输入。随后 PR-6 的有限核查更正与交付见下节。普通revert回滚本PR，无数据/数据库迁移，不合main/生产部署。


## PR-6：下一小批已有句稿（开发栈，未合并 / 未部署）

依赖 PR-5 #19 / `bb33958`，head `feat/listen-jgy-013-015`。按完整方案原编号做 PR-6，**没有跳做 PR-7**。方案未指定数值批次；选择当前金匮 001–012 后的 013–015 三集，保持一小段连续 id，而非批量扩完 124 集。

有限只读核查了 `/workspace` 顶层、已授权本 bot store 的项目目录及已知 TCM 位置：`/workspace/tcm-video-kb`、`/workspace/tcm-video-kb-pr3`、本 checkout `/workspace/tcm-video-kb-pr4`。后两处没有 artifacts；原流水线 `/workspace/tcm-video-kb/data/artifacts` 内找到 497 个递归 `segments.jsonl` 路径，其中 **145 个目录内直达的目录讲次输入**覆盖现行 catalog（另有三个 demo，未选）。只对选中三集读内容/验证；不把其余 142 份“存在”冒称验证通过。没有扫描整个 home、其它 bot 私有 store、用户机器，也没有读媒体、凭据或新 clone。

本批原始输入 4,123 行，2,710,079 字节；每行 video_id、catalog YouTube 身份、非空文字、有限非负有序秒窗、唯一连续 seq 均核对。全部 33 KP + 9 章的 seg_from/seg_to 存在，对应 start_s/end_s 与分句精确一致（最大差 0 秒）；三个源目录的 KP/章/实体文件与本分支知识输入也逐字节相同。这里只验证身份/结构/时间，不声明 ASR 文本或医学主张已经人工审校。

- 四层新增 12 份资产，共 **731,688 字节**（句稿 544,665 字节）；最大新文件 254,889 字节。实体保持既有 lexicon/类型/uncertain/new.* 过滤，三集分别 509/281/732 条；KP 为 10/15/8 条，章各 3 条。
- 三个实际导出器各向两处临时目录输出，逐文件比较相同；先在包含旧资产的临时发布树准备四层、两次生成相同清单且 `--check` 通过，再只复制新文件、生成当前清单。不修改原 artifacts 或原始知识，不重刷 CSV/图快照/嵌入文本，不运行 knowledge-build。
- `publish-manifest.json` 仍为默认导出、搜索和句稿覆盖的唯一运行来源，content_sha256 为 `129c0907a299f5018912f46de8de7f4482dca69cf1c84035b0a2e17a918e3d8e`。`docs/releases/pr6-jgy-013-015.audit.json` 是固定历史审计/测试收据，不被运行代码或默认导出读取，不是第二份可变发布名单。它绑定源文件 hash、规范投影 hash、原 21 集 84 份资产及 917 份原始知识文件的基线树 hash。
- 新测试还发现源 row 的 video_id 以前会被按目录名重贴，允许缺失或跨讲次来源假成功；现在进入 staging 时严格拒绝并非零、不发布目标。真实 canonical artifacts 有该字段；公开 slim 的往返 fixture 显式补外层 id，不把重建 fixture 冒充原始 ASR 输入。

完整本地严格离线 Python **148**、发布契约 **16**、前端 **128**（11 文件）、manifest 与 TS/Vite 均通过；命令/RED/重现见 TESTING.md。原 21 集 84 资产、原始知识 917 文件、catalog 逐字节保护通过。真实浏览器/手机PC视觉/YouTube 仍因先前 403 未验，不重试、不改成 pass；外部 iframe 无遥测，本次只是请求 URL 秒数。服务端真实404、缓存头/旧 bundle 行为未验证。保留合并前获准浏览器检查门槛；上线需另行授权。

回滚为普通 revert 整个 PR-6（12 新文件、清单、源身份 guard 与配套测试/文档一起回滚）；无数据库或存储迁移。PR-6 交付时 PR-7 仍待办；随后新任务的 PR-7 结果见下节，不追认成 PR-6 已实现。


## PR-7：构建身份与 health（开发栈，未合并 / 未部署）

依赖 #20 / `90845dc`，head `feat/health-build-revision`；只改既有 Python Worker 的构建元信息和 health，不做 PR-8 或新资源。`services/worker/build_metadata.py` 是唯一生产者，读取实际生成清单并重算验证原资产/清单一致性；`build.sh` 完成原 vendor、graph snapshot/embed、npm ci、TS/Vite 后，验证 `web/dist` 三层公开JSON的字节hash，再生成 **忽略提交的 `services/worker/src/build_info.py`**。该模块只有 `BUILD_INFO` 固定primitive字典，随既有Python模块打包方式由entry导入，传入create_app一次校验/复制；请求时不查git、不读环境、不扫知识库。不写硬编码commit，不以时间戳代替hash，不改wrangler/生产配置。

| health字段 | 含义与边界 |
|---|---|
| status | 保留 `ok`；只表示该health handler响应，不证明内容全可用、图/YouTube/网络/整站健康或部署成功 |
| git_sha | 构建最终注入时该checkout的完整小写Git HEAD（40或64 hex）；无git、非本root仓库、检测失败、未注入或非法值为 `unknown`。不是最终部署回执；CI合并ref可能不同于PR head |
| git_dirty | 标准git status含tracked改动/删除/未忽略untracked；true不是精确干净提交，false仅该次检测为干净，null为未知。无有效git_sha不宣称clean。保留eval删除/.superdesign，因此本box的真实采集会是true，绝不忽略它们造clean |
| content_revision | 已校验 `publish-manifest.json.content_sha256`，同输入重复一致，公开资产变化须重生成清单并改变hash；缺失/非法运行注入为unknown。只覆盖该清单定义的发布层/覆盖/计数，不是全部源文件、JS/CSS、图快照或媒体的总hash |

缺schema/形状错误按unknown；合法schema内仅允许上述字段、严格hash和bool，额外status/token/path全部丢弃，捕获后不受外部dict修改影响。构建清单缺失/过期、dist缺资产/字节不一致则非零，不注入假版本。脚本在虚拟环境检查之前清除旧生成模块，早期失败/前端失败不遗留上次“成功”身份；任何构建失败都不得部署。standalone生成CLI不代替完整构建；不承诺工作区并发修改时的事务快照，构建期间应冻结输入。

无注入的本地API/Worker入口返回 `status=ok, git_sha=unknown, git_dirty=null, content_revision=unknown`。下例是**临时无git源码副本离线构建的测试契约输出，不是生产观测**：

```json
{"status":"ok","git_sha":"unknown","git_dirty":null,"content_revision":"129c0907a299f5018912f46de8de7f4482dca69cf1c84035b0a2e17a918e3d8e"}
```

本地173严格离线Python（148+25）/16发布/128前端/manifest/TS-Vite通过。临时源码树实际完整运行build.sh（npm离线缓存），重复生成身份一致；实际非editable API wheel包含新module/app相同源码。构建原有graph命令仅写临时副本，**本checkout的原知识、24集资产、清单、图快照/嵌入文本不改**。API vendor两源码同步，已有一致性测试通过。详细RED/fixture与CI边界见TESTING.md；远端以PR检查/实际job日志为准。

本轮没有运行pywrangler部署、云端Python/Pyodide或真实浏览器；entry测试只替身workers.asgi包装，不冒称云端SDK实测。手机/PC视觉、YouTube与403门槛保持未验。回滚整个PR-7的构建/入口/API/vendor/测试文档，health回原status；旧生成模块应移除或从旧版本重新构建，无数据库/数据迁移。

### PR-8仅评估测量前提，未实现

本次只读清单测得24集句稿4,563,201字节，最大shl-003为602,420字节；未达原方案约15MB总量条件。未核验官方单文件限额；不能把旧runbook的25MiB当新查实事实。没有目标手机/网络/下载/渲染等待测量，也没有确认“只传40条、不传整集”的新产品需求，所以不能预设静态索引应做，更不能据总量小就证明手机体验良好。

后续须在获准可访问环境记录目标手机/浏览器、真实网络、冷/热缓存：搜索提交→各请求/最后句稿→首次及完整结果时间，HTTP次数/传输与解压字节、TTFB/下载、JSON解析/匹配/渲染CPU与长任务/内存；分离首搜、复搜、不同关键词与最大40命中等场景，保存可复核测量，再按原条件决策是否生成静态索引。不绕过当前403，不加采集服务/索引/数据库；由后续任务安排。


## PR-10：用户自持本机学习记录（开发栈，未部署）

原方案编号PR-10，直接依赖PR-7 #21 / dc83928；PR-8因原体量/实测条件未触发暂缓，PR-9无代码且合规前置仍待补，不在此PR扩大范围。入口在`/stash`收获匣底部「备份与导入学习记录」。

- `listen-state/1`文件只带现有`renji.listen.stash.v1`与`renji.listen.lastWatch.v1`；2 MiB UTF-8、200条，严格字段/版本/目录身份/秒数/日期校验。不导出未知storage、cookies、凭据或一般浏览历史，无网络调用/账号/云同步。文件未加密，需用户自己保管。
- 选择本地JSON只读预览计数/原句节选/请求位置，单独点击「确认合并导入」才写。既有记录及顺序优先，按videoId+text与id冲突去重，空余容量才追加；既有lastWatch不覆盖，仍是请求位置，不是已播放或完成。
- 写入前核对预览快照，先保存本机`renji.listen.importRecovery.v1`原始前后状态。失败尽力逐字节回滚；若恢复/清理失败保留原始journal，收获匣提供下载原记录、重试恢复或明确保留当前并清理。损坏/拒读/空间不足不静默导出空数据或清空原记录。
- localStorage跨key不是原子事务，无跨标签CAS保证；关闭并行写入并先下载备份。浏览器清除/驱逐、设备故障、持久拒绝或并发更新仍可能妨碍恢复，不能承诺总能恢复。普通旧收下/提示行为不在本项重做。
- 完整格式/合并/隐私/恢复/回滚合同见[LEARNING_STATE.md](LEARNING_STATE.md)，RED→GREEN与真实DOM边界见[TESTING.md](TESTING.md)。真实浏览器文件选择/下载、手机PC视觉与YouTube仍未验证；403不重试或绕过。未合main或部署，未开始PR-11。
