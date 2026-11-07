# 听课台句级文稿导出

从已有 `data/artifacts/<id>/segments.jsonl` 与 `data/knowledge/<id>/` 导出听课台公开切片。
**不跑 knowledge-build，不改动 purged media。**

## 覆盖集（P5 批次）

句级文稿 + slim KP + entities + 章节（`web/src/data/chapters`）已落地：

- 伤寒全系列样例：`shl-001` … `shl-008`
- 金匮：`jgy-001` … `jgy-012`（含既有 `jgy-005`）
- 本草样例：`bc-001`

前端搜原句名单见 `web/src/listen/transcriptCoverage.ts`，须与本清单一致。

## 命令

```bash
# artifacts 默认指向本机旁路目录；按实际路径传 --artifacts
python3 web/scripts/export_transcripts.py --artifacts /workspace/tcm-video-kb/data/artifacts --ids shl-006 shl-007
python3 web/scripts/export_knowledge_points.py --ids shl-006 shl-007
python3 web/scripts/export_entities.py --ids shl-006 shl-007
cp data/knowledge/shl-006/chapters.json web/src/data/chapters/shl-006.json
```

扩下一批时：更新三脚本 `DEFAULT_IDS`、`transcriptCoverage.ts`，再导出并复制章节。
