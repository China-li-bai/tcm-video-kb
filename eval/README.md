# 评测与抽检（eval）

质量门槛与填分步骤见 **[docs/runbooks/quality_spotcheck.md](../docs/runbooks/quality_spotcheck.md)**（中文操作手册，对齐 `ARCHITECTURE.md` §9）。

| 子目录 | 用途 |
|---|---|
| `asr/` | 既有 CER 脚本；`windows/` 为人工听写抽检窗 |
| `kp/` | 知识点分层复核表 |
| `retrieval/` | `qa.jsonl` 检索/回答金标 |
| `templates/` | 空白打分模板 |

生成样本：

```bash
uv run python scripts/eval/sample_asr_windows.py
uv run python scripts/eval/sample_kp_review.py
```

```bash
uv run python scripts/eval/validate_qa.py --strict-kp
```
