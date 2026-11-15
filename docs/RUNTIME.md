# 当前运行架构

`main` 在 `f298b9d578755ac801bc929bfe995fc872f430a2`（2026-11-14 09:51 +0800）。2026-11-15 22:32（Asia/Shanghai）抽查 `https://tcm-fangzheng.1272679088.workers.dev/health`，返回的 `git_sha` 是该提交，`git_dirty` 为 `false`，`content_revision` 与仓库里的 `web/src/data/publish-manifest.json` 相同：`129c0907a299f5018912f46de8de7f4482dca69cf1c84035b0a2e17a918e3d8e`。这次抽查只说明该次构建身份已经出现在这个 Worker 上，不证明之后没有再部署，也不证明每个页面像素或 YouTube 播放成功。

[ARCHITECTURE.md](ARCHITECTURE.md) 仍是目标设计稿。Postgres、向量检索、生成式问答和自有音频不在当前请求路径上。PR 编写时的日记在 [releases/runtime-development-log.md](releases/runtime-development-log.md)，里面的「未部署」不要当成现状。

## 数据层

请求只读下面的发布层和图快照。转写产物和知识 JSONL 不在请求里打开。

| 层 | 位置 | 现在 |
|---|---|---|
| 目录 | `web/src/data/lectures.json` | 145 集，均有 YouTube id。针灸 id 不连续。界面上 `nj` 显示为黄帝内经，目录原文字段不改写 |
| 词典 | `lexicon/` | 离线热词、纠错、规范 id，以及图上的方药组成 |
| 转写 | `data/artifacts`、`data/state.sqlite` | 不入库。`version_key` 只决定离线步骤要不要重跑 |
| 知识 | `data/knowledge/` | 145 集已入库。知识点 1,575 条，章节对象 624 个，来源仍是 `llm_read` |
| 图快照 | `services/worker/src/graph_snapshot.json` | 打进 Worker。讲课边只有 `candidate`，当前 2 条 |
| 发布切片 | `listen-publish/1` 清单和四个公开目录 | 24 集四层齐全：伤寒 001–008、金匮 001–015、本草 001。句稿 33,823 句 |
| 学习记录 | 浏览器 `localStorage` | 不上传。格式见 [LEARNING_STATE.md](LEARNING_STATE.md) |

自有发布音频是 0。`playback` 全部是 `youtube`。`scripts/build_media_manifest.py` 只描述本机媒体目录，不是这份网站契约。

## 请求路径

- 一个 Worker `tcm-fangzheng`：Vite 静态听课台，加上 FastAPI `/health`、`/graph/subgraph`、`/graph/paths`。图读快照，不扫描知识库。
- 浏览器从同源静态 JSON 读句稿、知识点和实体。问这句只取请求秒前后 45 秒内最多 3 条已导出知识点。查出处是浏览器子串，只扫清单里有句稿的集。没有生成模型。
- 播放是 YouTube iframe。点句用 `start=` 跳到请求秒。没有播放头，连续播放不带动文稿。界面不能把 iframe 的 load 当成播放成功。
- 收获匣和上次打开的位置留在本机。可以导出 `listen-state/1`，预览后再确认合并。没有账号。
- `web/stub_server.py` 和 HMAC 播放 stub 不是线上媒体服务。

三种秒不要混用：句和知识点上的证据时间、URL 里向下取整的请求秒、以及目前不存在的播放头。站内链接只由 `video_id` 加起点秒现算。文件里旧的 `t_url` 或任意 URL 不直接当成可点链接。历史知识文件还没有回写，读法见 [KNOWLEDGE.md](KNOWLEDGE.md)。

## 发布清单

```sh
python3 web/scripts/publish_manifest.py          # 从已入库文件生成
python3 web/scripts/publish_manifest.py --check  # 只读重算，逐字比较；CI 门禁
python3 -m unittest discover -s tests/publish -v
```

输入是 `lectures.json`、`data/knowledge` 的实际文件和四个发布目录，不依赖本机 artifacts。前端句稿白名单和三份导出脚本的默认 id 都由清单派生。新的一批要先显式 `--ids` 准备四层，再生成清单。

`content_sha256` 是去掉该字段后的清单，按 UTF-8、排序键、紧凑 JSON 做的 SHA-256。它覆盖清单里的发布层、覆盖标记和计数，不是 JS、图快照或媒体的总摘要。`/health` 的 `content_revision` 就是这个值。`git_sha` 是构建时采集的 HEAD；没有注入时为 `unknown`。`status: ok` 只表示这个处理函数有响应。

失败时命令非零：目录 id 重复、发布资产不在目录、文件内 id 不符、句或知识点或章节 id 重复、坏 JSON、非法时间、空句稿、公开切片缺任何一层、章节与句稿没有时间交集。知识点或实体可以是空数组，但文件必须在。其余 121 集不因此被要求补公开资产。生成先校验，成功后才替换清单。

```sh
python3 web/scripts/export_transcripts.py --artifacts /实际路径
python3 web/scripts/export_knowledge_points.py
python3 web/scripts/export_entities.py
```

不传 `--ids` 时从清单取已公开 id。缺输入、空名单、重复或未知 id 都非零退出，不留下半批公开文件。没有本地 artifacts 时，句稿导出失败是正常结果，不要为此去下载或运行 `knowledge-build`。

三个前端加载器要求成功的 HTTP 状态、JSON 的 content-type、相同的 `video_id` 和合法时间。200 的 HTML 不算句稿。缺文件时 Worker 仍可能因单页回退返回 HTML；前端拒绝它，服务端还不是 404。2026-11-15 的抽查里，`/transcripts/zj-002.json` 仍是 `text/html`。

## 还没有做完的事

- 缺失静态 JSON 的真实 HTTP 404，以及旧 HTML 缓存是否会挡住后补的文件。
- 播放跟读。要先确认嵌入条款，再决定要不要读播放头。
- 把历史知识 JSON 回写成带 `t_url` 的新产物。那需要另一次授权的 `knowledge-build`，这次文档合并没有改那些文件。
- 发布检查只要求章节和句稿在时间上有交集，不把每条证据短句再送回句稿比对。
- 质量抽检没有完成。题集校验见 [QA_VALIDATION.md](QA_VALIDATION.md)，通过不是检索分数，也不是医学正确。

回滚网站仍是检出已知提交，按 [runbooks/cloudflare_workers.md](runbooks/cloudflare_workers.md) 重新构建部署。没有数据库迁移。
