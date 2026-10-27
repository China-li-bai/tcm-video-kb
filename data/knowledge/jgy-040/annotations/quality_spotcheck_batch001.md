# 质量抽查回流 · batch001（jgy-040）

- 复核人：人纪质量核对
- 日期：2026-10-25（Asia/Shanghai）
- 来源：eval/kp/batch001_kp_review.csv

以下条目 verdict 为「部分对」或「错」，建议修正注释后视情况重跑 knowledge-build。

## jgy-040.kp0001 · 部分对
- type: `diagnostic_rule`
- t: 44.4–53.34s
- statement: 癌患夜卧生热、阳不得入阴，属阴阳分隔，为凶；与脑瘤等一致。
- evidence_quote: 「生热」
- 问题与建议: 癌患夜卧生热、与脑瘤一样在窗内；「阴阳分隔为凶」在约141s，远超 end_s=53。建议扩窗并补「阴阳分隔」证据句。
- 建议重跑 knowledge-build: 是

## 汇总
本视频至少一条需修正时间窗或转述后再 **重跑 knowledge-build** 以刷新 KP/索引。
