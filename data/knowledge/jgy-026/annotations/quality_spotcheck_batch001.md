# 质量抽查回流 · batch001（jgy-026）

- 复核人：人纪质量核对
- 日期：2026-10-25（Asia/Shanghai）
- 来源：eval/kp/batch001_kp_review.csv

以下条目 verdict 为「部分对」或「错」，建议修正注释后视情况重跑 knowledge-build。

## jgy-026.kp0007 · 部分对
- type: `prognosis`
- t: 595.77–598.89s
- statement: ALS晚期可至轮椅、吞咽不能；辨为寒证而用生附辛热尚有转机，不知用里寒药则难阻进展。
- evidence_quote: 「他是寒症」
- 问题与建议: 辨寒证用生附辛热尚有转机正确；轮椅/吞咽不能等晚期描述在约628s，超出 end_s=599。建议扩窗；ASR「IOS默契」宜注为 ALS 末期。
- 建议重跑 knowledge-build: 是

## 汇总
本视频至少一条需修正时间窗或转述后再 **重跑 knowledge-build** 以刷新 KP/索引。
