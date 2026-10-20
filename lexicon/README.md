# lexicon/ — 共享中医词典（v0.1，全部 status: draft）

唯一事实来源；驱动 ASR 热词、ASR 后纠错、实体抽取与检索分词。规范见 docs/ARCHITECTURE.md §7；热词上限与 ASF 依据见 docs/SEACO_HOTWORD_RESEARCH.md（推荐每系列约 50 词）。

```
entries/{category}.yaml     词条（人工维护）       schema/lexicon_entry.schema.json
classics/shanghanlun.yaml   伤寒论 398 条（宋本）   schema/classic_clauses.schema.json
corrections/general.yaml    非实体纠错规则          schema/correction_rule.schema.json
tests/cases.yaml            must_fix / must_not_fix / match 回归用例
candidates/                 自动挖掘的新词（待审核，不参与构建）
sources/                    原始下载 + SOURCES.md + seed_report.json
build.yaml                  构建参数（min_status、热词上限、系列列表）
dist/                       构建产物（gitignore）
```

命令（仓库根目录，.venv 已安装 packages/tcmkb_lexicon）：
```
.venv/bin/python -m tcmkb_lexicon validate --root lexicon
.venv/bin/python -m tcmkb_lexicon build    --root lexicon      # -> lexicon/dist/
.venv/bin/python -m tcmkb_lexicon test     --root lexicon      # 跑 cases.yaml
.venv/bin/python -m tcmkb_lexicon correct  --root lexicon "张仲锦从仓寒到金贵"
.venv/bin/python -m tcmkb_lexicon match    --root lexicon "太阳中风，桂枝汤主之"
.venv/bin/python -m pytest tests/unit/test_lexicon.py
```

编辑规范：
- 规范名用简体，`id` = `{category}.{拼音或 WHO 代码}`，一经发布不改（下游 entity_id 依赖）。
- 新增 `asr_errors` 必须附实际转写中出现的证据（note），并在 cases.yaml 加 must_fix + 至少一个 must_not_fix。
- 普通词（如 悲观、经济、上海、皇帝）作为误识来源时必须加 left/right/near_any 守卫；无守卫地改写合法词典词会被 validate 拒绝。
- 审核后把 `status` 改为 `reviewed`，并把 build.yaml 的 `min_status` 改为 reviewed。
- 种子脚本 scripts/lexicon/seed_v0_1.py 仅用于 v0.1 初始化，重跑会覆盖人工修改（需 --force）。
