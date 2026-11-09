# 当前运行架构与发布契约

基线：`main@cc4c7f6`（2026-11-09，Asia/Shanghai）的听课台 + 本 PR 的发布边界改进。本 PR 未合并、未部署；下述新增行为须合并并另行授权部署后才影响公网。`ARCHITECTURE.md` 是目标设计稿，不是运行现状。

## 运行与数据流

- 一个 Cloudflare Worker `tcm-fangzheng`：Vite/React 静态听课台 + FastAPI `/health`、`/graph/subgraph`、`/graph/paths`。图读已打包快照，不在请求里扫描知识库。
- 浏览器从同源静态 JSON 读取句稿、知识点、实体。问这句只取附近 ±45 秒内最多 3 条已导出知识点；查出处仍是浏览器子串匹配，无生成模型。
- 播放是 YouTube iframe；点句用 `start=` 跳秒。尚无连续播放跟读；旧 main 的 28% 装饰进度、lastWatch 语义在本开发栈 PR-3 修正（详见末节），不是公网已上线。
- 收获匣和上次点到的位置留在浏览器 localStorage，没有账号、上传或跨设备同步。
- 请求路径没有 Postgres、向量、LLM 或自有 R2 音频；Python 构建流水线是离线工具。`web/stub_server.py` 与 HMAC 播放 stub 不是线上媒体服务。

## 覆盖不等于目录

| 层 | 当前入库数量 | 边界 |
|---|---:|---|
| 听课目录 | 145 | 五系列，均有 YouTube id；针灸 id 不连续 |
| 知识目录 | 145 | 已入库知识点和章节等，不等于公开句稿 |
| 公开句稿 / KP / 实体 / 打包章节 | 各 21 | 伤寒 001–008、金匮 001–012、本草 001；这只是说明，不作选择名单 |
| 句稿 | 29,700 句 | shl-001 为 3604 句，公开文件总计 4,018,536 字节 |
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

每条讲次记录目录/知识/公开层的布尔覆盖、知识点/章节/句子计数、播放来源；公开资产带相对路径、字节数、SHA-256 与条数。清单无生成时间、绝对路径或自引用 git SHA，生成可重复。`content_sha256` 是去掉该字段后的清单对象按 UTF-8、排序 key、紧凑 JSON 编码的 SHA-256；未来发布标识可组合 `git SHA + content_sha256`。`/health` 本 PR 仍只返回 status，修订号待 PR-7。

失败规则：

- 目录 id 重复、发布资产不在目录、文件内 id 不符、句序号/知识点/章节 id 重复、坏 JSON、非法/逆向时间、空句稿、空原句等均失败非零。
- 仅已公开的切片要求四层文件齐全且章节与句稿至少有一个时间交集；不是强迫其余 124 集产生不存在的资产。
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

本 PR 只提供开发分支/审阅 PR，不自动合 main、不部署生产。不改定高内滚布局/CSS、不扩句稿、不跑模型或 knowledge-build。回滚本 PR 用普通 revert；无数据库迁移。如日后部署，回滚为检出上一个已知 SHA，按现有 cloudflare_workers runbook 重建部署。

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
