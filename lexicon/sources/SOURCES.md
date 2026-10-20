# 词典 v0.1 数据来源（2026-10-19 Asia/Shanghai 下载）

所有原始下载文件保存在本目录，便于复核。词条的 `sources[].ref` 指向下表 id。
古籍原文（伤寒论、金匮要略、神农本草经、黄帝内经）为公有领域；维基百科/维基文库页面为 CC BY-SA 4.0，此处只取术语与条文，需保留署名。

| ref | 内容 | URL | 版本 | 文件 |
|---|---|---|---|---|
| shl_wikisource | 《傷寒論》（宋本，林億校、趙開美刻）全文 | https://zh.wikisource.org/wiki/傷寒論 | revid 2607901；页面标注 Textquality 25%（"序和五到十四章的原文已校訂（方未校）"） | shl_wikisource.json/.wikitext |
| jgy_wikisource | 《金匱要略》/《金匮要略方论》 | https://zh.wikisource.org/wiki/金匱要略 ， https://zh.wikisource.org/wiki/金匱要略方論 | revid 2598887 / 2187300（后者标注"未校訂"） | jgy_wikisource_trad/_simp.* |
| bencao_wikisource | 《神農本草經》 | https://zh.wikisource.org/wiki/神農本草經 | revid 2490492（Textquality 50%；解析出 359 味，非完整 365） | bencao_wikisource.* |
| neijing_wikisource / neijing_index | 《黃帝內經》素問 24 卷、靈樞 12 卷子页面 + 目录（篇名 162） | https://zh.wikisource.org/wiki/黃帝內經 | 目录 revid 2596804（Textquality 25%） | neijing/*.wikitext, neijing_index.wikitext |
| zhwiki_shuxue | 腧穴列表：十二经 309 + 任督 52 = 361 经穴（含序号/国际代码），奇经八脉，经外奇穴，临床常用特定穴 | https://zh.wikipedia.org/wiki/腧穴列表 | revid 81976722 | zhwiki_腧穴列表.* |
| enwiki_acupoints | List of acupuncture points（代码 LU-1… 与中文名，Deadman 编号），用于交叉核对 361 穴 | https://en.wikipedia.org/wiki/List_of_acupuncture_points | revid 1363973636 | acupoints_enwiki.* |
| zhwiki_qijing | 奇经八脉 | https://zh.wikipedia.org/wiki/奇经八脉 | revid 53668675 | zhwiki_奇经八脉.* |
| zhwiki_qiezhen | 切诊（常见病脉） | https://zh.wikipedia.org/wiki/切诊 | revid 95032559 | zhwiki_切诊.* |
| zhwiki_nihaixia | 倪海廈 | https://zh.wikipedia.org/wiki/倪海廈 | revid 94641471 | zhwiki_倪海廈.* |
| zhwiki_classics | 中醫典籍列表 | https://zh.wikipedia.org/wiki/中醫典籍列表 | revid 94375500 | zhwiki_中醫典籍列表.* |
| jingfangjia_844 | 倪海厦自述《我将用一生心血来完成天纪、人纪、地纪》（转载） | https://www.jingfangjia.cn/wen/844.html | 2026-10-19 抓取 | jingfangjia_844.html/.txt |
| web:hongyuanguoxue_51 | 课程目录（仲景心法、八纲辨证），仅搜索结果摘要 | https://www.hongyuanguoxue.com/zhongyi/51.html | 未存档 | — |
| web:douban_838463327 | 人纪学习顺序（针灸聚英为参考书），仅搜索结果摘要 | https://www.douban.com/note/838463327/ | 未存档 | — |
| unverified | 未在上述来源中找到原文佐证的少数条目（见 attrs.verification） | — | — | — |

WHO 标准（Standard Acupuncture Nomenclature / WHO Standard Acupuncture Point Locations 2008）原文 PDF 未直接下载；
361 穴依据 zhwiki（引用 WHO 1993 命名）并与 enwiki 列表交叉核对：343/361 代码与中文名一致，其余 18 条为 enwiki 行解析失败或异体字
（如 偏历/偏歴、飞扬/飞阳、水沟/人中），已记为别名。GB1/GV15/GV22/LI19 采用 GB/T 12346 通行写法 瞳子髎/哑门/囟会/口禾髎，原 zhwiki 写法作别名。

ctext.org 对本机返回 HTTP 403，未使用。

## 伤寒论 398 条的取得方式
维基文库文本不带全书编号。脚本 `scripts/lexicon/seed_v0_1.py`（条文切分见 `scripts/lexicon/parse_shl_clauses.py`，输出 sources/shl_clauses_trad.json）取「辨太阳病脉证并治上第五」至「辨阴阳易差后劳复病脉证并治第十四」
的正文段落，剔除方剂组成/煎服法段落（3 段未用 :; 标记的方后注），按通行分段计数：每篇条数与通行编号区间完全吻合
（太阳上 1–30、中 31–127、下 128–178、阳明 179–262、少阳 263–272、太阴 273–280、少阴 281–325、厥阴 326–381、霍乱 382–391、阴阳易差后 392–398），
且原文中 259 处内嵌编号（如「六二、」「一四一、」）全部与推算编号一致。条文文字未与纸本逐字校对（维基文库标注部分未校订）。
