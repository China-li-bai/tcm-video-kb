# 质量抽查回流 · batch001（jgy-033）

- 复核人：人纪质量核对
- 日期：2026-10-25（Asia/Shanghai）
- 来源：eval/kp/batch001_kp_review.csv

以下条目 verdict 为「部分对」或「错」，建议修正注释后视情况重跑 knowledge-build。

## jgy-033.kp0004 · 部分对
- type: `clinical_tip`
- t: 413.22–423.315s
- statement: 一周后咳大减、血块少、胸痛减；原夜不需盖被之燥热可转为需盖被。
- evidence_quote: 「咳嗽好很多了」
- 问题与建议: 一周后咳减、血块少、胸痛减在窗内；「原不盖被之燥热转需盖被」在约452s，略超 end_s=423，时间略偏，建议扩窗。
- 建议重跑 knowledge-build: 是

## 汇总
本视频至少一条需修正时间窗或转述后再 **重跑 knowledge-build** 以刷新 KP/索引。
