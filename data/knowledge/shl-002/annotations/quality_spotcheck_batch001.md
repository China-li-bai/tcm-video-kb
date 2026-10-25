# 质量抽查回流 · batch001（shl-002）

- 复核人：人纪质量核对
- 日期：2026-10-25（Asia/Shanghai）
- 来源：eval/kp/batch001_kp_review.csv

以下条目 verdict 为「部分对」或「错」，建议修正注释后视情况重跑 knowledge-build。

## shl-002.kp0119 · 部分对
- type: `contraindication`
- t: 19620.297–19986.937s
- statement: 太阳表证当汗解，禁用火熏烧针强求出汗；火逆可致衄、发黄、惊狂等。
- evidence_quote: 「明言火逆哈」
- 问题与建议: 表证当汗解、禁用火灸/火熏大意对，但时间窗约6分钟涵盖多条火逆条文；「衄、发黄、惊狂」在本窗未完整对应，属过度概括。建议拆条并缩短窗、扩证据。
- 建议重跑 knowledge-build: 是

## shl-002.kp0062 · 部分对
- type: `formula_composition`
- t: 4800.035–4869.585s
- statement: 桂枝甘草汤桂枝四两、甘草二两，顿服；桂枝能降冲逆、气化心下水气。桂枝加桂汤则于桂枝汤中加肉桂，用于奔豚一类冲脉上逆。
- evidence_quote: 「桂枝四这甘草二」
- 问题与建议: 桂枝甘草汤四两:二两、降冲逆气化水气、桂枝加桂加肉桂治奔豚类均正确；「顿服」本窗未明说，属经典补入。证据 ASR「桂枝四这甘草二」宜校正。
- 建议重跑 knowledge-build: 否（可先改 annotations/证据句再决定）

## 汇总
本视频至少一条需修正时间窗或转述后再 **重跑 knowledge-build** 以刷新 KP/索引。
