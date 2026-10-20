# SeACo-Paraformer 热词机制调研与本项目策略

> 日期：2026-10-19（Asia/Shanghai）  
> 关联：`docs/ARCHITECTURE.md` §7、`lexicon/build.yaml`、`eval/asr/out/score_v0_1.json`  
> 目的：解释为何「400 词热词表不如 31 词」，并给出 v0.1 之后的热词上限与排序策略。

## 1. 论文要点（Shi et al., ICASSP 2024）

- **论文**：Xian Shi et al., *SeACo-Paraformer: A Non-Autoregressive ASR System with Flexible and Effective Hotword Customization Ability*，arXiv:2308.03266（ICASSP 2024）。  
  - PDF/摘要：<https://arxiv.org/abs/2308.03266>  
  - HTML：<https://arxiv.org/html/2308.03266v4>
- **骨干**：在 Paraformer（NAR + CIF）之上冻结 ASR，另训 bias encoder / bias decoder / bias out；热词与声学嵌入、解码隐状态做交叉注意力，输出带 **no-bias** 标记的偏置概率。
- **概率合并**（文中式 (5)）：某步若 `argmax(P_b) = ⟨no-bias⟩`，则直接用基础 ASR 概率；否则  
  `P_m = λ P_b + (1−λ) P_ASR`。论文推理默认 **λ = 1.0**。
- **训练采样长度**：`l_min = 2`，`l_max = 8`（2–8 字）。与本项目 `build.yaml` 的 `min_len/max_len` 对齐。
- **ASF（Attention Score Filtering）**：先对**全部**热词做一遍注意力，把注意力分数在输出长度 `L` 上求和，取 **top-k** 活跃热词再真正解码。论文用 **k = 50**。动机：热词变多后，交叉注意力难以在稀疏大列表上对准，召回与 CER 都会变差。
- **热词列表变长会退化**（Fig. 2）：在 Test-Entity（原 231 词）上掺入无关热词扩到 **400 / 800 / 1200 / 2000 / 4000**，三类模型（CLAS、SeACo、SeACo+ASF）性能均随列表变长下降；仅 SeACo+ASF 在扩到 4000 时仍能压住 CER。
- **相对 CLAS**：内部测试 R1 热词召回约 **SeACo+ASF 65% vs CLAS 51%**；开源 NE 集约 **87% vs 69%**（文中 Table 2 与叙述）。
- **相关工作**：CLAS [13]（Pundak et al., SLT 2018）；CIF ColDec [14]（Han et al., ICASSP 2021）；细粒度上下文知识选择 [19]（Han et al., ICASSP 2022）——ASF 与 [19] 同属「先筛再偏置」，但 SeACo 用多层 bias decoder 最后一层分数做过滤。

## 2. FunASR 实现与 SDK 约定

### 2.1 源码：`_seaco_decode_with_ASF`

FunASR 中 SeACo 推理入口：

- 仓库：<https://github.com/modelscope/FunASR>  
- 文件：`funasr/models/seaco_paraformer/model.py`  
  （例：<https://github.com/modelscope/FunASR/blob/main/funasr/models/seaco_paraformer/model.py>）

关键签名（摘要）：

```text
_seaco_decode_with_ASF(..., hw_list, nfilter=50, seaco_weight=1.0)
```

- **`nfilter=50`**：对应论文 ASF 的 **k**。当 `0 < nfilter < num_hot_word` 时：用 `seaco_decoder.forward_asf6` 得到分数 → 按热词维求和 → `topk(nfilter)` → 只保留这些热词（外加 SOS/空槽）再跑完整 SeACo。
- **`seaco_weight`**：对应论文 **λ**，默认 1.0；与 no-bias mask 合并基础解码与偏置解码的 log-softmax。
- **重要推论**：即便 `.txt` 里写了 400 或 1000 个词，**真正参与偏置解码的大约只有 top-50 个「当前 utterance 注意力最高」的词**。列表越长，ASF 前置注意力越难、越噪，且与真正需要的中医术语抢分数——这直接解释了本项目 v0.1 评测结果。

`inference()` 里调用 ASF 时**未从 kwargs 传入 nfilter**（写死默认 50），见同文件 `decoder_out = self._seaco_decode_with_ASF(..., hw_list=self.hotword_list)`。AutoModel 是否透传 `nfilter` / `seaco_weight` 仍属开放问题（见 §5）。

### 2.2 热词输入格式

- **空格串**：`hotword="桂枝汤 足三里 张仲景"`（Discussion [#2550](https://github.com/modelscope/FunASR/discussions/2550)）。
- **`.txt` 文件**：一行一词；SDK/文档常见格式为 **`词 权重`**（空格分隔权重）。SeACo 路径的 `generate_hotwords_list` 对每行 `hw.split()` 后整行当 token 序列——**权重是否真正进入 SeACo 偏置路径仍不明确**（见 §5）。
- **官方量级建议**（SDK / 阿里云说明，口头上限）：词长 **≤10**、条数 **≤1000**。训练有效区间仍是 **2–8 字**；本项目构建侧按 2–8 截断更稳妥。  
  参考文章：<https://developer.aliyun.com/article/1587443>（FunASR 第三代热词 / SeACo 介绍）。

### 2.3 已知 Issues / Discussions

| 编号 | 要点 | 链接 |
|---|---|---|
| #1616 | **英文热词无效**：BPE 单元会改变 token 数，而 CIF 在开头就定长，难以在 Paraformer 骨架上做英热词纠偏 | <https://github.com/modelscope/FunASR/issues/1616> |
| #2443 | `generate_hotwords_list` **分词/tokenization bug**（热词切分异常） | <https://github.com/modelscope/FunASR/issues/2443> |
| #2550 | 多热词用法：空格串 **或** `.txt` 一行一词 | <https://github.com/modelscope/FunASR/discussions/2550> |

本项目语料为中文经方/针灸术语，英文热词问题可忽略；但 tokenization bug 意味着构建产物应尽量「一行一个纯中文词、无多余空格/权重」，避免踩分词路径。

## 3. 本项目基准实测（v0.1）

数据：`eval/asr/` 上 10 分钟窗口（zj 针灸 / shl 伤寒 / nj 内经），SeACo-Paraformer + fsmn-vad + ct-punc；窗口 CER 相对自制 ref。差异约 **<2 pt 视为噪声**（与 `asr-bench/results.md` 一致）。纠错规则来自同一批转写，**+corr 行偏乐观（in-sample）**。

| 片段 | bench 31 词 | lex 400 | lex 100 | bench31+corr | 备注 |
|---|---|---|---|---|---|
| zj | **5.93%** | 6.81% | 6.37% | **5.27%** | 400 词反而变差；100 词列表截断掉「足三里」（排在第 113） |
| shl | 10.20% | **9.74%** | 9.89% | 10.20% | 400 略好，仍在噪声带；+corr 对 CER 几乎不动，但「金匮」「乌梅丸」等命中上升 |
| nj | 10.64% | 10.43% | 10.64% | **9.15%** | 热词帮助有限；纠错（皇帝→黄帝、和于术数等）更明显 |

- **RTF**：约 0.048（无/少热词）→ **0.055（100 词）→ 0.066–0.071（400 词）**；热词越多越慢。
- **结论**：与论文 Fig. 2 / ASF k=50 **一致**——盲目堆到 400 不会优于精选 ~30 词；真正稳赚的是 **`corrections.json` 后处理** + **短而准的热词表**。

原始数字：`eval/asr/out/score_v0_1.json`。

## 4. 对本项目的策略变更（已写入 ARCHITECTURE / build.yaml）

| 项 | 旧（v0.1 构建默认） | 新推荐 |
|---|---|---|
| 每系列热词上限 `max_per_series` | 400 | **50–100，默认倾向 50**（对齐 ASF `nfilter=50`） |
| 排序 | `2×priority + (系列专属优先于 global)`，再按类、按名 | 同上，并叠加：**讲座频次** + **难召回（R1 类）中医术语** 优先；频次需来自讲义/已有转写统计，待接 s10/candidates |
| 单字 / 六经 | 已排除进热词 | **继续排除**：1 字词、`six_channel`（及易误插的歧义词）只留在 lexicon / `corrections.json` |
| 纠错 | `asr_errors` → corrections | **主路径不变**：已知 ASR 混淆以 `corrections.json` 为主；热词只负责「难听清的专名」提升一过性召回 |
| ASR 配置 | 未暴露 | 建议在 `configs/asr.yaml` **可选暴露** `nfilter`（ASF k）与 `seaco_weight`（λ），默认 50 / 1.0；需先确认 AutoModel 能否传入（见 §5） |


**构建侧现状（本提交已把 `max_per_series` 改为 50 并重跑 build）**：当前排序尚未接讲座频次，zj 的 50 词被大量「系列专属 × priority1 穴位」按类名字母序占满，**未包含「足三里 / 梁丘 / 伏兔 / 髀关」等基准命中词**（它们多在 global 或排序靠后）。因此 **50 的帽必须与频次/白名单 pin 一起上线**，否则短列表会比 31 词基准更差。临时缓解：维护 `lexicon/hotword_pins/{series}.txt`（或 entries 上 `hotword_priority: 1` + 仅核心穴位 `hotword_scope: [zj]`），build 时强制置顶后再按 cap 截断——实现留待下一小版本。

**实操建议（下一版热词表）**：

1. 每系列维护 **~50** 个词：该系列核心方剂/穴位/书名/人名（如 shl：桂枝汤、五苓散、乌梅丸、伤寒论、张仲景…；zj：足三里、梁丘、伏兔、髀关…）。
2. 全局再叠一层极短 `global.txt`（倪海厦、经方、伤寒、金匮等跨系列词），合并进系列文件时仍受 50–100 总帽约束。
3. 热词文件格式：**一行一词、无权重**（规避 tokenization/权重是否生效的不确定性）；长度 2–8。
4. 评测门禁：改热词上限或排序后，必须在 `eval/asr` 上对比 bench31 / 新表 / +corr 的窗口 CER 与关键术语命中。

## 5. 开放问题

1. **FunASR `AutoModel.generate` 是否暴露 `nfilter` / `seaco_weight`？**  
   源码 `inference()` 调用 `_seaco_decode_with_ASF` 时未把 kwargs 里的 nfilter 传下去；若上层也不传，则用户无法在不改库的前提下调 k。  
   **2026-10-20 已确认（funasr 1.4.16，本仓库 `.venv`）：不透传**，`inference()` 只传 `hw_list`，`nfilter=50`、`seaco_weight=1.0` 为默认值；`configs/asr.yaml` 中两键仅作记录。
2. **`.txt` 中 `词 权重` 是否影响 SeACo 路径？**  
   CLAS/部分文档强调权重；SeACo 的 `generate_hotwords_list` 对整行 `split()` 后送 tokenizer——第二段数字可能被当成异常 token。在确认前，本项目**不写权重**。
3. **长讲座是否应按 chunk（如 20 分钟）重跑 ASF？**  
   ASF 的分数是**当前解码片段**上的注意力总和。整集 1–2 小时若一次灌入同一张 50 词表，通常够用；若未来改为「每 chunk 动态热词」（按章节方剂表），才可能需要每 chunk 重新 filter。是否在 20 分钟切片边界重滤，待用长音频对比实验。

## 6. 参考文献与链接（速查）

1. Shi et al., SeACo-Paraformer, arXiv:2308.03266 — <https://arxiv.org/abs/2308.03266> / <https://arxiv.org/html/2308.03266v4>
2. FunASR SeACo `model.py`（`nfilter=50`）— <https://github.com/modelscope/FunASR/blob/main/funasr/models/seaco_paraformer/model.py>
3. 阿里云介绍文 — <https://developer.aliyun.com/article/1587443>
4. FunASR #1616 英文热词 — <https://github.com/modelscope/FunASR/issues/1616>
5. FunASR #2443 tokenization — <https://github.com/modelscope/FunASR/issues/2443>
6. FunASR Discussion #2550 多热词格式 — <https://github.com/modelscope/FunASR/discussions/2550>
7. CLAS [13]；CIF ColDec [14]；fine-grained contextual knowledge selection [19]（均见论文参考文献列表）
8. 本仓库评测：`eval/asr/out/score_v0_1.json`、`/workspace/asr-bench/results.md`
