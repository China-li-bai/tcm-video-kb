# 质量抽查回流 · batch001（jgy-021）

- 复核人：人纪质量核对
- 日期：2026-10-25（Asia/Shanghai）
- 来源：eval/kp/batch001_kp_review.csv

以下条目 verdict 为「部分对」或「错」，建议修正注释后视情况重跑 knowledge-build。

## jgy-021.kp0025 · 部分对
- type: `acupoint_usage`
- t: 2811.852–2824.247s
- statement: 跌仆伤胎、腰以下重、小便不通属胎位不正；针至阴与隐白（两井穴）安胎转胎，优于刺关元（孕妇忌）。
- evidence_quote: 「至阴」
- 问题与建议: 伤胎胎位不正针至阴+隐白井穴、优于关元（孕妇忌）内容正确，但关元/孕妇忌在约2890s，远超标注 end_s=2824；时间窗过短，建议扩至~2910s 并换更长证据。
- 建议重跑 knowledge-build: 是

## 汇总
本视频至少一条需修正时间窗或转述后再 **重跑 knowledge-build** 以刷新 KP/索引。
