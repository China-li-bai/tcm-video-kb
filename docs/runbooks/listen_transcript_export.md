# 听课台句级文稿导出

从已有 `data/artifacts/<id>/segments.jsonl` 与 `data/knowledge/<id>/` 导出听课台公开切片。
**不跑 knowledge-build，不改动 purged media。**

## 覆盖集（P5 批次）

句级文稿 + slim KP + entities + 章节（`web/src/data/chapters`）已落地：

- 伤寒全系列样例：`shl-001` … `shl-008`
- 金匮：`jgy-001` … `jgy-012`（含既有 `jgy-005`）
- 本草样例：`bc-001`

发布单一来源为生成的 `web/src/data/publish-manifest.json`。三份脚本默认 id 与前端搜原句范围均从它派生；上面的 P5 列表仅为历史说明。

## 命令

```bash
# artifacts 默认指向当前仓库 data/artifacts；按实际路径传 --artifacts
python3 web/scripts/export_transcripts.py --artifacts /workspace/tcm-video-kb/data/artifacts --ids shl-006 shl-007
python3 web/scripts/export_knowledge_points.py --ids shl-006 shl-007
python3 web/scripts/export_entities.py --ids shl-006 shl-007
cp data/knowledge/shl-006/chapters.json web/src/data/chapters/shl-006.json
```

扩下一批时：确认本机实际有 artifacts，显式 `--ids` 导出并准备对应章节，再运行：

```bash
python3 web/scripts/publish_manifest.py
python3 web/scripts/publish_manifest.py --check
python3 -m unittest discover -s tests/publish -v
```

不再维护任何 DEFAULT_IDS 或第二份前端名单。缺输入、空/重复/未知 id、坏数据的导出均非零退出；同批输入/校验失败不发布半批。不要部署失败的导出。知识点或筛选后的实体可为有效空数组；公开切片四层必须存在，其他目录讲次不强制补资产。完整边界见 [RUNTIME.md](../RUNTIME.md)。
