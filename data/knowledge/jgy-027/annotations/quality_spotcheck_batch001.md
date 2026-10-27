# 质量抽查回流 · batch001（jgy-027）

- 复核人：人纪质量核对
- 日期：2026-10-25（Asia/Shanghai）
- 来源：eval/kp/batch001_kp_review.csv

以下条目 verdict 为「部分对」或「错」，建议修正注释后视情况重跑 knowledge-build。

## jgy-027.kp0001 · 部分对
- type: `concept_definition`
- t: 475.0–477.815s
- statement: 胆为出阳之所、中正之官；子时阳生与胆相关，重病夜半胃气来复欲食，示胆阳回复。
- evidence_quote: 「胆是出阳」
- 问题与建议: 胆为出阳、中正之官、子时与胆相关及重病夜半胃气来复欲食均正确，但标注窗仅约3秒；关键句在498–522s，须扩 end_s。
- 建议重跑 knowledge-build: 否（可先改 annotations/证据句再决定）
