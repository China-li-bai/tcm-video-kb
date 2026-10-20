"""One-off seed import for lexicon v0.1 (2026-10-19).

Reads the public-domain / CC sources saved in lexicon/sources/ and writes
lexicon/entries/*.yaml, lexicon/classics/shanghanlun.yaml, lexicon/corrections/general.yaml.
After seeding, the YAML files are the source of truth (human-edited); re-running
this script overwrites them, so it refuses unless --force is given.

Rule against invented terms: every curated candidate term below is KEPT ONLY IF it
literally occurs (after t2s) in one of the downloaded source texts; the matching
source ids are written to `sources`. The few exceptions are explicit and carry
attrs.verification = "web" (verified on a web page that is cited) or "unverified".
"""
import re, sys, json, pathlib, collections
import yaml
from pypinyin import lazy_pinyin
import jieba
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from srcparse import SRC, s, strip_wiki, split_ingredients, shl_formulas, jgy_formulas, bencao

ROOT = SRC.parent
if "--force" not in sys.argv and (ROOT / "entries" / "formula.yaml").exists():
    sys.exit("entries already exist; pass --force to overwrite (this discards manual edits)")

# ---------------------------------------------------------------- corpora
def rd(p): return s(strip_wiki((SRC / p).read_text()))
CORPUS = {
    "shl_wikisource": rd("shl_wikisource.wikitext"),
    "jgy_wikisource": rd("jgy_wikisource_simp.wikitext") + rd("jgy_wikisource_trad.wikitext"),
    "bencao_wikisource": rd("bencao_wikisource.wikitext"),
    "neijing_wikisource": "".join(s(strip_wiki(p.read_text())) for p in sorted((SRC / "neijing").glob("*.wikitext"))) + rd("neijing_index.wikitext"),
    "zhwiki_shuxue": rd("zhwiki_腧穴列表.wikitext"),
    "zhwiki_qijing": rd("zhwiki_奇经八脉.wikitext"),
    "zhwiki_qiezhen": rd("zhwiki_切诊.wikitext"),
    "zhwiki_nihaixia": rd("zhwiki_倪海廈.wikitext"),
    "zhwiki_classics": rd("zhwiki_中醫典籍列表.wikitext"),
    "jingfangjia_844": (SRC / "jingfangjia_844.txt").read_text(),
}
def attested(*terms):
    return [k for k, v in CORPUS.items() if any(t and t in v for t in terms)]

def slug(term):
    return "_".join(lazy_pinyin(term)).replace("ü", "v").replace("ǖ", "v")
def py(term): return " ".join(lazy_pinyin(term))

ENTRIES = collections.defaultdict(list)
IDS = {}
def add(cat, term, *, id=None, aliases=(), hotword=True, scope=("global",), prio=2, match="always",
        ctx=(), rel=(), attrs=None, sources=None, notes="", errors=()):
    term = term.strip()
    eid = id or f"{cat}.{slug(term)}"
    if eid in IDS:
        e = IDS[eid]
        for a in aliases:
            if a not in e["aliases"] and a != e["term"]: e["aliases"].append(a)
        return e
    srcs = sources if sources is not None else [{"ref": r} for r in attested(term, *aliases)]
    e = {"id": eid, "term": term, "category": cat, "aliases": [a for a in dict.fromkeys(aliases) if a != term],
         "pinyin": py(term), "hotword": hotword, "hotword_scope": list(scope), "hotword_priority": prio,
         "asr_errors": list(errors), "match_policy": match, "context_any": list(ctx),
         "relations": list(rel), "attrs": attrs or {}, "sources": srcs, "status": "draft", "notes": notes}
    IDS[eid] = e; ENTRIES[cat].append(e)
    return e
def add_if_attested(cat, term, **kw):
    al = kw.get("aliases", ())
    if not attested(term, *al): return None
    return add(cat, term, **kw)
SKIPPED = collections.defaultdict(list)
def curated(cat, terms, **kw):
    for t in terms.split():
        if isinstance(t, str) and "/" in t:   # term/alias1/alias2
            t, *al = t.split("/")
        else: al = []
        if add_if_attested(cat, t, aliases=al, **kw) is None: SKIPPED[cat].append(t)

# ---------------------------------------------------------------- 伤寒论 clauses
clauses = json.load(open(SRC / "shl_clauses_trad.json"))
def sec_s(name):
    n = s(name); n = re.sub(r"第[一二三四五六七八九十]+$", "", n); return n.replace("（", "").replace("）", "")
# ---------------------------------------------------------------- herbs
TYPO = {"黄岑": "黄芩", "木防已": "木防己", "防已": "防己", "厚扑": "厚朴", "获苓": "茯苓", "桅于": "栀子", "水蛙": "水蛭",
        "株茯苓": "茯苓", "旋复花": "旋覆花", "大附子": "附子", "葶苈": "葶苈子", "麻仁": "麻子仁", "薏苡": "薏苡仁",
        "穹穷": "芎穷", "知母十八株": "知母", "黄芩十八株": "黄芩", "干姜两半": "干姜", "鳖甲手指大": "鳖甲",
        "戎盐弹丸大": "戎盐", "五味": "五味子", "肥栀子": "栀子", "黄檗": "黄柏", "代赭": "代赭石", "白敛": "白蔹",
        "香豉": "豉", "生葛": "葛根", "茵陈蒿末": "茵陈蒿"}
JUNK = re.compile(r"[《》'。：；;]|以水|煮|去滓|服|治|等$|^等|右|洗|渍|熏|得$|^得|内诸|末之|和令|绵裹|自然|再取|未止|顿|头痛|口不|身体|冒昧|拘急|转侧|发作|使人|心胸|自吐|气满|令能|脉|表无|病者|从腰|腰以下|难以|危急|不出|行动|汗出|心中|与小|此汤|头不|哕|数谵|妇人|取烧|商陆根|溯瞿|两檗|蟋螂|新绛|以白粉|以酒|煎减|食煮|勿以|蜘蛛$")
MERGE = {"川椒": "蜀椒", "芎穷": "芎䓖", "牡丹": "牡丹皮", "亭历": "葶苈子", "白蜜": "蜜", "食蜜": "蜜", "生竹茹": "竹茹"}
def norm_herb(n):
    n = re.sub(r"大者$", "", n); n = re.sub(r"各?等$", "", n)
    n = TYPO.get(n, n); n = MERGE.get(n, n)
    return n
herb_count = collections.Counter(); formula_ings = {}
fs = shl_formulas(); jf = jgy_formulas()
for name, ing in fs:
    formula_ings.setdefault(("shl", s(name)), [norm_herb(s(x)) for x in split_ingredients(ing)])
for name, ing, ch in jf:
    formula_ings.setdefault(("jgy", s(name)), [norm_herb(s(x)) for x in split_ingredients(ing)])
for k, v in formula_ings.items():
    v[:] = [y for x in v for y in (["泽泻", "阿胶"] if x == "泽泻阿胶" else [x])]
    v[:] = [x for x in v if x and not JUNK.search(x) and 1 <= len(x) <= 6 and not re.search(r"[汤散丸]$|^煎取$", x)]
    herb_count.update(set(v))
# bencao names that are the same drug under a different (older) name -> canonical formula-text name
BENCAO_SYN = {"茈胡": "柴胡", "杏核": "杏仁", "芎䓖": "芎䓖", "署豫": "薯蓣", "薏苡人": "薏苡仁", "五味": "五味子", "亭历": "葶苈子",
              "芫华": "芫花", "蘗木": "黄柏", "支子": "栀子", "代赭": "代赭石", "白头公": "白头翁", "桃核": "桃仁",
              "牡丹": "牡丹皮", "大豆黄卷": "豆黄卷", "梅实": "乌梅", "款冬": "款冬花", "酸枣": "酸枣仁", "委萎": "萎蕤",
              "消石": "硝石", "鞠华": "菊花", "吴公": "蜈蚣"}
EXTRA_ALIAS = {"芎䓖": ["芎穷", "川芎"], "薯蓣": ["山药"], "黄柏": ["黄檗"], "蜀椒": ["川椒"], "甘草": ["炙甘草"],
               "旋覆花": ["旋复花"], "麻子仁": ["麻仁"], "葶苈子": ["葶苈"], "朴消": ["朴硝"]}
b = bencao()
bencao_by_canon = {}
for x in b:
    n = s(x["name"])
    if "等" in n or len(n) > 6: continue
    canon = BENCAO_SYN.get(n, n)
    yiming = [s(m) for m in re.findall(r"一名([^，。、\s]{1,5})", x["text"])]
    bencao_by_canon[canon] = dict(orig=n, grade=s(x["section"]), yiming=yiming, text=s(x["text"])[:80])
YIMING_OF = {}
for canon, bc in bencao_by_canon.items():
    for y in bc["yiming"]: YIMING_OF.setdefault(y, canon)
for h in list(herb_count):
    if h not in bencao_by_canon and h in YIMING_OF:
        c = YIMING_OF[h]; herb_count[c] += herb_count.pop(h)
        EXTRA_ALIAS.setdefault(c, []).append(h)
        for v in formula_ings.values(): v[:] = [c if x == h else x for x in v]
TOP_HERBS = {h for h, _ in herb_count.most_common(70)}
for canon in sorted(set(bencao_by_canon) | set(herb_count), key=lambda h: (-herb_count[h], h)):
    bc = bencao_by_canon.get(canon)
    al = []
    if bc and bc["orig"] != canon: al.append(bc["orig"])
    al += EXTRA_ALIAS.get(canon, [])
    if len(canon) == 1:
        hot, match, ctx = False, "context", ["服", "两", "味", "药", "加", "去"]
    else:
        hot, match, ctx = True, "always", []
    in_f = herb_count[canon] > 0
    scope = (["global"] if canon in TOP_HERBS else ["shl", "jgy", "bc"]) if in_f else ["bc"]
    attrs = {}
    if bc: attrs.update(bencao_grade=bc["grade"], bencao_name=bc["orig"], **({"yiming": bc["yiming"]} if bc["yiming"] else {}))
    if in_f: attrs["formula_count"] = herb_count[canon]
    notes = ""
    if bc and bc["orig"] != canon: notes = f"本草经作「{bc['orig']}」，按通行同物异名并入（待审）"
    add("herb", canon, aliases=al, hotword=hot, scope=scope, prio=1 if canon in TOP_HERBS else (2 if in_f else 3),
        match=match, ctx=ctx, attrs=attrs, notes=notes)
GZ_RIGHT = "汤|加|去|[一二三四五六七八九十]|麻黄|附子|芍药|甘草"
IDS["herb.gui_zhi"]["asr_errors"] = [{"from": "桂子", "right": GZ_RIGHT, "note": "基准 sensevoice/whisper"},
                                     {"from": "贵子", "right": GZ_RIGHT, "note": "基准 whisper"}]
HERB_ID = {e["term"]: e["id"] for e in ENTRIES["herb"]}
for e in ENTRIES["herb"]:
    for a in e["aliases"]: HERB_ID.setdefault(a, e["id"])

# ---------------------------------------------------------------- formulas
FTYPO = {"桂技甘草汤": "桂枝甘草汤", "防已黄芪汤": "防己黄芪汤", "防已茯苓汤": "防己茯苓汤", "木防已汤": "木防己汤",
         "暮蓣丸": "薯蓣丸", "通脉四道汤": "通脉四逆汤", "梔子大黄汤": "栀子大黄汤", "旋复花汤": "旋覆花汤"}
FALIAS = {"茯苓桂枝白术甘草汤": ["苓桂术甘汤"], "桂枝去芍药加蜀漆牡蛎龙骨救逆汤": ["桂枝救逆汤"], "茵陈蒿汤": ["茵陈汤"],
          "桂枝加芍药生姜各一两人参三两新加汤": ["新加汤", "桂枝新加汤"], "麻黄杏仁甘草石膏汤": ["麻杏甘石汤"],
          "葛根黄芩黄连汤": ["葛根芩连汤"], "栀子檗皮汤": ["栀子柏皮汤"], "麻黄杏仁甘草石膏汤": ["麻杏甘石汤", "麻黄杏子甘草石膏汤"], "旋覆花汤": ["旋复花汤"], "旋复代赭汤": [], "真武汤": [], "理中丸": ["理中汤"]}
ALIAS2CANON = {a: c for c, al in FALIAS.items() for a in al}
def fname(n):
    n = re.sub(r"（.*?）", "", n); n = re.sub(r"方$", "", n.strip()); n = FTYPO.get(n, n); return ALIAS2CANON.get(n, n)
shl_text_by_clause = {c["no"]: s(c["text_trad"]) for c in clauses}
def clauses_mentioning(name, als):
    return [no for no, t in shl_text_by_clause.items() if any(a in t for a in [name, *als])]
formula_src = collections.OrderedDict()
for (book, raw), ings in formula_ings.items():
    n = fname(raw)
    if not re.search(r"[汤散丸煎]$|导$|方$", n) or n in ("附方",) or n.startswith("附《") or len(n) < 2: continue
    formula_src.setdefault(n, {"books": [], "ings": ings})
    if book not in formula_src[n]["books"]: formula_src[n]["books"].append(book)
# formulas named in 伤寒论 clauses but whose 方 header is missing in the wikisource text (manually vetted list)
CLAUSE_ONLY = {"承气汤", "柴胡汤", "泻心汤", "栀子干姜汤", "吴茱萸汤", "三物小陷胸汤"}
for no, t in shl_text_by_clause.items():
    for m in re.finditer(r"([\u4e00-\u9fff]{2,12}?[汤散丸])(?:主之|。|；|，)", t):
        n = m.group(1)
        n = re.sub(r"^(?:宜|与|可与|属|服|以|作|更作|先与|复与|却与|当|用|后服|少与|乃服|仍与|再服|反与|更服|饮|虽|欲|医以|不可与|当与|和以|针)", "", n)
        n = re.sub(r"^(?:宜|与|可与|属|服|以)", "", n)
        if n in formula_src or len(n) < 3 or n not in t: continue
        if any(n.endswith(x) for x in ("热汤", "白饮", "米汤", "丸药", "汤药", "汤")) and n in ("热汤", "汤药", "米汤"): continue
        if n in ("桂枝汤证", "此汤", "柴胡汤", "泻心汤", "承气汤") or re.search(r"^[此其诸本]", n): 
            if n not in ("柴胡汤", "泻心汤", "承气汤"): continue
        if n in CLAUSE_ONLY: formula_src.setdefault(n, {"books": ["shl"], "ings": [], "from_clause": True})
GENERIC = {"柴胡汤", "泻心汤", "承气汤"}
ferr = {"桂枝汤": [{"from": x} for x in ("桂子汤", "贵子汤", "桂之汤", "贵之汤", "桂者汤")],
        "五苓散": [{"from": x} for x in ("武林散", "五菱散", "五菱伞", "五0散")],
        "乌梅丸": [{"from": "未苗丸"}, {"from": "欧美外", "near_any": ["乌梅", "虫", "丸"], "window": 12}],
        "抵当汤": [{"from": "抵挡汤"}], "抵当丸": [{"from": "抵挡丸"}]}
for n, d in formula_src.items():
    als = FALIAS.get(n, [])
    cl = clauses_mentioning(n, als) if "shl" in d["books"] else []
    rel = []
    for h in dict.fromkeys(d["ings"]):
        if h in HERB_ID: rel.append({"pred": "composed_of", "obj": HERB_ID[h]})
    scope = ["global"] if len(cl) >= 3 else ["shl", "jgy"]
    long_name = len(n) > 8
    attrs = {"books": d["books"]}
    if cl: attrs["shl_clauses"] = cl
    if d.get("from_clause"): attrs["note_src"] = "name taken from clause text (formula header absent in source)"
    notes = "泛称（同类方总称），非单一方" if n in GENERIC else ""
    add("formula", n, aliases=als, hotword=not long_name, scope=scope, prio=1 if len(cl) >= 3 else 2,
        rel=rel, attrs=attrs, notes=notes, errors=ferr.get(n, []))

# ---------------------------------------------------------------- acupoints (zhwiki 腧穴列表 + enwiki codes)
wk = (SRC / "zhwiki_腧穴列表.wikitext").read_text()
MER = {}  # code -> (name_s, [points])
for m in re.finditer(r"^\| \[\[([^\]]+)\]\] \|\| style=\"text-align:center;\" \| (\w+) \|\| style=\"text-align:right;\" \| (\d+) ?\|\| (.+)$", wk, re.M):
    mname, code, cnt, rest = m.groups()
    pts = re.findall(r"\[\[([^|\]]+?)(?:\|([^\]]+))?\]\]", rest)
    MER[code] = (s(mname), int(cnt), pts)
en = (SRC / "acupoints_enwiki.wikitext").read_text()
EN = {}
for m in re.finditer(r"^\|\s*([A-Z]{2})-(\d+)\s*\|\|\s*\{\{lang\|zh\|\s*([^}]+?)\s*\}\}\s*\|\|\s*([^|]+?)\s*\|\|", en, re.M):
    EN[f"{m.group(1)}{int(m.group(2))}"] = (s(m.group(3)), m.group(4).strip())
CODEMAP = {"LU": "LU", "LI": "LI", "ST": "ST", "SP": "SP", "HT": "HT", "SI": "SI", "BL": "BL", "KI": "KI", "PC": "PC", "TE": "TE", "GB": "GB", "LR": "LR", "GV": "GV", "CV": "CV"}
EN_ALT = {"TE": "TB", "LR": "LV"}
jieba.initialize()
FREQ = jieba.dt.FREQ
special = set(s(x) for x in re.findall(r"\[\[([^|\]]+?)穴(?:\|[^\]]+)?\]\]", wk[wk.find("== 臨床常用穴"):wk.find("== 其他理論")]))
special |= set(s(x) for x in re.findall(r"\|([^\]|]+)\]\]", wk[wk.find("== 臨床常用穴"):wk.find("== 其他理論")]))
_core_lines = [l for l in wk.split("\n") if re.search(r"四總穴|回陽九針穴|馬丹陽天星十二穴|四關穴|十總穴", l)]
core_acu = set(s(x) for l in _core_lines for x in re.findall(r"\[\[([^|\]]+?)穴(?:\|[^\]]+)?\]\]", l))
ACU_CTX = ["穴", "针", "灸", "刺", "扎", "按", "下针", "寸", "经"]
MER_ID = {}
acu_mismatch = []
point_by_name = {}
for code, (mname, cnt, pts) in MER.items():
    if code not in CODEMAP: continue
    for raw in pts:
        label = raw[1] or raw[0]
        mm = re.match(r"(\d+)\.(.+)", label)
        if not mm: continue
        num = int(mm.group(1)); nm = mm.group(2)
        alias = re.findall(r"（(.+?)）", nm); nm = re.sub(r"（.+?）", "", nm)
        nm = s(nm)
        c = f"{code}{num}"
        STD = {"GB1": ("瞳子髎", "童子髎"), "GV15": ("哑门", "痖门"), "GV22": ("囟会", "顖会"), "LI19": ("口禾髎", "禾髎")}
        if c in STD: nm, old = STD[c]; alias.append(old)
        enk = EN.get(c) or EN.get(f"{EN_ALT.get(code, code)}{num}")
        if enk:
            for v in re.split(r"[ ()（）]+", enk[0]):
                v = s(v)
                if v and v != nm and v not in alias and v not in ("偏歴",): alias.append(v)
        if not enk or (enk[0] != nm and nm not in enk[0]): acu_mismatch.append((c, nm, enk))
        common = FREQ.get(nm, 0) > 300 or nm in ("太阳", "带脉")
        prio = 1 if nm in special else 2
        e = add("acupoint", nm, id=f"acupoint.{c.lower()}", aliases=[s(a) for a in alias] + ([nm + "穴"] if len(nm) <= 3 else []),
                hotword=not (FREQ.get(nm, 0) > 3000), scope=["global", "zj"] if nm in core_acu else ["zj"], prio=prio,
                match="context" if common else "always", ctx=ACU_CTX if common else [],
                rel=[{"pred": "on_meridian", "obj": f"meridian.{code.lower()}"}],
                attrs={"code": c, **({"pinyin_en": enk[1]} if enk else {})},
                sources=[{"ref": "zhwiki_shuxue", "at": f"{mname} {num}"}] + ([{"ref": "enwiki_acupoints", "at": c}] if enk else []))
        point_by_name[nm] = e["id"]
# extra points (经外奇穴)
ex_sec = wk[wk.find("=== [[:Category:經外奇穴"):wk.find("== 臨床常用穴")]
for raw in re.findall(r"\[\[([^|\]]+?)(?:\|([^\]]+))?\]\]", ex_sec):
    nm = s((raw[1] or raw[0]).replace("穴", "")) if not raw[0].startswith(":") else None
    if not nm or nm in point_by_name: continue
    common = FREQ.get(nm, 0) > 300 or nm in ("太阳",)
    e = add("acupoint", nm, id=f"acupoint.ex_{slug(nm)}", aliases=[nm + "穴"] if not nm.endswith("穴") else [],
            hotword=nm not in ("太阳",) and FREQ.get(nm, 0) <= 3000, scope=["zj"], prio=2,
            match="context" if common else "always", ctx=ACU_CTX if common else [],
            attrs={"extra_point": True}, sources=[{"ref": "zhwiki_shuxue", "at": "經外奇穴"}],
            notes="经外奇穴" + ("；与六经「太阳」同形，需上下文" if nm == "太阳" else ""))
    point_by_name[nm] = e["id"]
# ASR errors observed in the benchmark (zj segment)
def acu_err(name, errs):
    IDS[point_by_name[name]]["asr_errors"] += errs
acu_err("足三里", [{"from": "竹山里"}, {"from": "足山里"}, {"from": "主山里"}, {"from": "竹山", "right": "里|穴"}])
acu_err("梁丘", [{"from": "凉秋", "near_any": ["穴", "足三里", "伏兔", "阴市", "髀关"], "window": 12}])
acu_err("髀关", [{"from": "悲观", "right": "浮涂|伏兔"}])
acu_err("伏兔", [{"from": "浮涂"}])
acu_err("阴市", [{"from": "阴实", "near_any": ["梁丘", "凉秋", "伏兔", "浮涂", "穴"], "window": 8}])
acu_err("上巨虚", [{"from": "上居虚"}]); acu_err("下巨虚", [{"from": "下居虚"}])
acu_err("条口", [{"from": "调口", "near_any": ["巨虚", "居虚"], "window": 8}])

# ---------------------------------------------------------------- meridians (12 + 8)
MER_ALIAS = {"LU": "肺经", "LI": "大肠经", "ST": "胃经", "SP": "脾经", "HT": "心经", "SI": "小肠经", "BL": "膀胱经",
             "KI": "肾经", "PC": "心包经", "TE": "三焦经", "GB": "胆经", "LR": "肝经"}
for code, (mname, cnt, pts) in MER.items():
    if code in CODEMAP:
        add("meridian", mname, id=f"meridian.{code.lower()}", aliases=[MER_ALIAS[code]] if code in MER_ALIAS else [],
            scope=["global"], prio=1, attrs={"code": code, "points": cnt, "kind": "正经" if code in MER_ALIAS else "奇经"},
            sources=[{"ref": "zhwiki_shuxue"}, {"ref": "enwiki_acupoints"}],
            notes="简称「X经」为通行简称（待审）" if code in MER_ALIAS else "")
for nm, code in [("冲脉", "tv"), ("带脉", "bv"), ("阴维脉", "yinlv"), ("阳维脉", "yanglv"), ("阴跷脉", "yinhv"), ("阳跷脉", "yanghv")]:
    add("meridian", nm, id=f"meridian.{code}", aliases=["衝脉", "沖脉"] if nm == "冲脉" else [], scope=["global"], prio=1,
        match="context" if nm == "带脉" else "always", ctx=["经", "脉", "奇经", "八脉"] if nm == "带脉" else [],
        attrs={"kind": "奇经"}, sources=[{"ref": "zhwiki_shuxue"}, {"ref": "zhwiki_qijing"}])
add("meridian", "奇经八脉", scope=["global"], prio=1, attrs={"kind": "总称"})
add("meridian", "十二经脉", aliases=["十二正经"], scope=["global"], prio=1, attrs={"kind": "总称"})

# ---------------------------------------------------------------- six channels & syndromes
SIX = [("太阳", "taiyang"), ("阳明", "yangming"), ("少阳", "shaoyang"), ("太阴", "taiyin"), ("少阴", "shaoyin"), ("厥阴", "jueyin")]
for t, sl in SIX:
    add("six_channel", t, id=f"six_channel.{sl}", hotword=False, scope=[], prio=1, match="context",
        ctx=["病", "证", "经", "篇", "中风", "伤寒", "合病", "并病", "之为病", "脉"],
        notes="不进热词：基准测试中 SeACo 热词「厥阴」导致误插（道法于阴阳→道法厥阴阳）")
    add("syndrome", t + "病", rel=[{"pred": "belongs_to", "obj": f"six_channel.{sl}"}], scope=["shl"], prio=1)
SYN_REL = {"太阳中风": "taiyang", "太阳伤寒": "taiyang", "少阳证": "shaoyang", "阳明证": "yangming", "柴胡证": "shaoyang",
           "桂枝证": "taiyang", "风温": "taiyang", "温病": "taiyang", "太阳与阳明合病": "taiyang"}
curated("syndrome", "太阳中风 太阳伤寒 中风 伤寒 温病 风温 桂枝证 柴胡证 少阳证 阳明证 合病 并病 二阳并病 三阳合病 坏病 结胸 小结胸 "
        "痞 热入血室 奔豚 水逆 蓄水 蓄血 脏结/藏结 脏厥/藏厥 亡阳 亡血 阳结 阴结 脾约 蛔厥 阳明腑实 表证 里证 表里俱虚 阴阳俱虚 营卫不和 "
        "阴阳易 劳复 食复 寒湿 湿痹 风湿 刚痉 柔痉 中暍 火逆 火邪 戴阳 格阳 上热下寒 "
        "痰饮 悬饮 溢饮 支饮 留饮 伏饮 风水 皮水 正水 石水 黄汗 谷疸 酒疸 女劳疸 黑疸 血痹 虚劳 肺痿 肺痈 胸痹 寒疝 宿食 "
        "肝着 肾着 历节 百合病 狐惑 阴阳毒 疟病 牝疟 瘅疟 温疟 肠痈 浸淫疮 转筋 阴狐疝 脏躁 梅核气", scope=["shl", "jgy"], prio=2)
for t, ch in SYN_REL.items():
    if t in IDS.get(f"syndrome.{slug(t)}", {}).get("term", ""):
        IDS[f"syndrome.{slug(t)}"]["relations"].append({"pred": "belongs_to", "obj": f"six_channel.{ch}"})
for k in ("syndrome.pi", "syndrome.shang_han", "syndrome.zhong_feng"):
    if k in IDS:
        e = IDS[k]
        if len(e["term"]) == 1: e.update(hotword=False, match_policy="context", context_any=["心下", "按之", "痞硬", "痞满", "作痞"])
        else: e.update(match_policy="context", context_any=["太阳", "病", "脉", "证", "汗", "恶寒", "恶风"],
                      notes="与书名/病名同形，需上下文；书名见 classic.shang_han_lun")
# ---------------------------------------------------------------- symptoms
curated("symptom", "恶寒 恶风 发热 汗出 自汗 盗汗 无汗 头痛 头项强痛 项背强 项强 身疼 身疼痛 体痛 骨节疼痛 腰痛 呕逆 干呕 喜呕 呕吐 "
        "鼻鸣 鼻塞 咳 喘 短气 少气 口苦 咽干 咽痛 目眩 头眩 往来寒热 寒热 胸胁苦满 胁下满 胸满 心烦 烦躁 躁烦 虚烦 "
        "嘿嘿不欲饮食 不欲饮食 心下痞 心下痞硬 心下悸 心悸 心动悸 心中懊憹 心中疼热 腹满 腹痛 腹中痛 少腹满 少腹急结 "
        "下利 自利 下利清谷 便脓血 不大便 大便硬 大便难 小便不利 小便数 小便自利 失溲 潮热 日晡所发潮热 谵语 郑声 "
        "不得眠 但欲寐 嗜卧 身重 振寒 手足厥冷 手足厥逆 四肢厥逆 厥逆 厥 手足温 脚挛急 衄 吐血 下血 身黄 发黄 "
        "头汗出 渴 消渴 口渴 口燥 舌上燥 欲饮水 水入则吐 吐蛔 气上冲 饥而不欲食 身痒 口噤 背反张 喘满 "
        "心中烦 心下满 发狂 如狂 健忘 漏下 带下 恶心 噫气 哕 咳逆上气 浮肿 水肿 肿 眩冒 冒 麻木 不仁 筋惕肉瞤 "
        "身瞤动 振振欲擗地 叉手自冒心 胃中干 胃中冷 腹胀满 雷鸣 自汗出", scope=["shl", "jgy"], prio=3)
for e in ENTRIES["symptom"]:
    if len(e["term"]) == 1:
        e.update(hotword=False, match_policy="never", notes="单字症状，不做词典匹配，交给 LLM 抽取")
# ---------------------------------------------------------------- pulses
P28 = "浮 沉 迟 数 滑 涩 虚 实 长 短 洪 微 紧 缓 弦 芤 革 牢 濡 弱 散 细 伏 动 促 结 代 疾".split()
for p in P28:
    if attested("脉" + p, p + "脉"):
        add("pulse", p + "脉", id=f"pulse.{slug(p)}", aliases=["脉" + p], hotword=p in "浮沉迟数滑涩弦紧缓洪细微弱",
            scope=["global"], prio=1 if p in "浮沉迟数" else 2)
pc = collections.Counter(re.findall(r"脉(?:[浮沉迟数滑涩虚实长短洪微紧缓弦芤革牢濡弱散细伏动促结代疾大小]){2,3}",
                                    CORPUS["shl_wikisource"] + CORPUS["jgy_wikisource"]))
for t, n in pc.items():
    if n >= 3: add("pulse", t, scope=["shl", "jgy"], prio=2, hotword=len(t) >= 3, attrs={"compound": True, "count": n})
add_if_attested("pulse", "寸口", scope=["global"], prio=2); add_if_attested("pulse", "趺阳脉", scope=["shl", "jgy"], prio=3)
add_if_attested("pulse", "寸关尺", scope=["global"], prio=2); add_if_attested("pulse", "三部九候", scope=["nj"], prio=2)
add_if_attested("pulse", "关上", scope=["shl"], prio=3, hotword=False, match="context", ctx=["脉"]); add_if_attested("pulse", "尺中", scope=["shl"], prio=3, hotword=False, match="context", ctx=["脉"])
# ---------------------------------------------------------------- tongue (classical text only has a few)
curated("tongue", "舌上白胎 舌上胎滑 舌上胎 舌苔", scope=["shl", "jgy"], prio=3, hotword=False)
# ---------------------------------------------------------------- methods
curated("method", "发汗 解肌 发表 攻表 解表 攻里 救里 救表 和解 吐 下之 急下之 温之 利小便 温针 烧针 火劫 灸 针 刺 补泻 补 泻 "
        "导引 吐纳 膏摩 针灸 实脾 温经 熨 啜粥 温覆 先表后里 汗法 下法 吐法", scope=["global"], prio=2)
for e in ENTRIES["method"]:
    if len(e["term"]) == 1 or e["term"] in ("下之",):
        e.update(hotword=False, match_policy="never", notes="单字/虚词性，词典不匹配")
IDS.get("method.bu_xie", {}).setdefault("asr_errors", []) if "method.bu_xie" in IDS else None
# ---------------------------------------------------------------- zangfu
curated("zangfu", "心 肝 脾 肺 肾 胆 胃 小肠 大肠 膀胱 三焦 心包 心包络 五脏 六腑 五脏六腑 命门 脑 髓 女子胞 胞宫 膻中 "
        "上焦 中焦 下焦 丹田 血室 心下 胸胁 少腹 腠理 皮毛 肌肉 筋 骨 脉", scope=["global"], prio=2)
for e in ENTRIES["zangfu"]:
    if len(e["term"]) == 1:
        e.update(hotword=False, match_policy="context", context_any=["经", "气", "病", "脏", "腑", "火", "虚", "实", "热", "寒", "主"],
                 notes="单字脏腑，需上下文")
for t in ("膻中", "命门"):
    k = f"zangfu.{slug(t)}"
    if k in IDS: IDS[k]["notes"] = "与穴位同形（见 acupoint）"; IDS[k]["hotword"] = False
# ---------------------------------------------------------------- concepts
curated("concept", "阴阳 五行 营卫/荣卫 营气/荣气 卫气 气血 津液 精气 精神 神明 经络 腧穴 表里 寒热 虚实 六经 经方 经方家 胃气 正气 邪气 "
        "虚邪 贼风 五邪 元气 真气 宗气 平脉辨证 辨证 治未病 上工 中工 下工 君臣佐使 七情 五味 四气 相须 相使 相畏 相恶 相反 相杀 "
        "上品 中品 下品 汤液 岐黄 阴阳五行 天人合一 子午流注 井荥输经合/五输穴 原穴 络穴 俞穴 募穴 郄穴 下合穴 八会穴 八脉交会穴 "
        "过经 再经 欲解时 传经 直中 两感 热化 寒化 阳气 阴气 阳虚 阴虚 血虚 气虚 本草 汤剂 散剂 丸剂", scope=["global"], prio=2)
for t in ("经方", "阴阳", "胃气", "辨证", "营卫", "岐黄", "六经", "经络"):
    k = f"concept.{slug(t)}"
    if k in IDS: IDS[k]["hotword_priority"] = 1
if "concept.jing_fang" in IDS:
    IDS["concept.jing_fang"]["asr_errors"] = [{"from": "金方", "left_not": "千|黄|药|秘", "note": "基准：金方家→经方家"}]
if "concept.qi_huang" in IDS: IDS["concept.qi_huang"]["asr_errors"] = [{"from": "其黄", "right": "之术"}]
if "concept.wei_qi" in IDS: IDS["concept.wei_qi"]["asr_errors"] = []
# ---------------------------------------------------------------- diseases (金匮 chapter titles etc.)
curated("disease", "伤寒 中风 温病 痉病/痉 湿病 暍病 百合病 狐惑病 阴阳毒 疟病 中风病 历节病 血痹 虚劳 肺痿 肺痈 咳嗽上气 奔豚气 胸痹 心痛 "
        "腹满 寒疝 宿食 积聚 痰饮 咳嗽 消渴 小便不利 淋病 水气病 黄疸 惊悸 吐血 下血 瘀血 呕吐 哕 下利 疮痈 肠痈 浸淫疮 "
        "趺蹶 转筋 阴狐疝 蛔虫病 霍乱 癫痫 癥瘕 疝瘕 喉痹 消渴病 黄疸病", scope=["jgy"], prio=3)
for e in list(ENTRIES["disease"]):
    # surface already exists as syndrome/symptom -> keep one entity per surface
    if any(x["term"] == e["term"] for c in ("syndrome", "symptom") for x in ENTRIES[c]):
        ENTRIES["disease"].remove(e); del IDS[e["id"]]
# ---------------------------------------------------------------- classics: books, chapters
BOOKS = [("伤寒论", "shang_han_lun", ["伤寒"], ["shl"]), ("金匮要略", "jin_gui_yao_lve", ["金匮", "金匮要略方论"], ["jgy"]),
         ("伤寒杂病论", "shang_han_za_bing_lun", [], ["shl", "jgy"]), ("黄帝内经", "huang_di_nei_jing", ["内经"], ["nj"]),
         ("素问", "su_wen", [], ["nj"]), ("灵枢", "ling_shu", [], ["nj"]), ("神农本草经", "shen_nong_ben_cao_jing", ["本草经"], ["bc"]),
         ("针灸大成", "zhen_jiu_da_cheng", [], ["zj"]), ("难经", "nan_jing", [], ["nj", "zj"]), ("针灸甲乙经", "zhen_jiu_jia_yi_jing", ["甲乙经"], ["zj"]),
         ("医宗金鉴", "yi_zong_jin_jian", [], ["global"]), ("备急千金要方", "bei_ji_qian_jin_yao_fang", ["千金要方", "千金方"], ["global"]),
         ("奇经八脉考", "qi_jing_ba_mai_kao", [], ["zj"]), ("脉经", "mai_jing", [], ["shl", "jgy"]), ("金匮玉函经", "jin_gui_yu_han_jing", [], ["shl"]),
         ("针灸聚英", "zhen_jiu_ju_ying", [], ["zj"]), ("温病条辨", "wen_bing_tiao_bian", [], ["global"]), ("本草纲目", "ben_cao_gang_mu", [], ["bc"])]
for t, sl, al, sc in BOOKS:
    e = add("classic", t, id=f"classic.{sl}", aliases=al, scope=sc if sc != ["global"] else ["global"], prio=1 if sc != ["global"] else 2,
            attrs={"kind": "book"})
    if not e["sources"]:
        if t == "针灸聚英":
            e["sources"] = [{"ref": "web:douban_838463327", "at": "人纪·针灸篇参考书"}]; e["attrs"]["verification"] = "web"
        else:
            e["sources"] = [{"ref": "unverified"}]; e["attrs"]["verification"] = "unverified"
IDS["classic.shang_han_lun"]["match_policy"] = "always"
IDS["classic.shang_han_lun"]["asr_errors"] = [
    {"from": x, "to": "伤寒"} for x in ("张寒", "仓寒", "长寒")] + [
    {"from": "上海", "to": "伤寒", "left": "从|读|讲", "near_any": ["张仲景", "金匮", "金桂", "金贵"], "window": 10},
    {"from": "上寒", "to": "伤寒", "right": "论|呢?金"}]
IDS["classic.jin_gui_yao_lve"]["asr_errors"] = [
    {"from": "金金桂", "to": "金匮", "near_any": ["伤寒"], "window": 6},
    {"from": "金桂", "to": "金匮", "near_any": ["伤寒", "张仲景", "仲景"], "window": 12},
    {"from": "金贵", "to": "金匮", "near_any": ["伤寒", "张仲景", "仲景"], "window": 12}]
IDS["classic.shang_han_lun"]["notes"] = "别名「伤寒」与病名同形；实体匹配时「伤寒」默认归 syndrome，书名需《》或「论/金匮」上下文"
IDS["classic.shang_han_lun"]["aliases"] = []   # keep 伤寒 surface on syndrome to avoid double-matching
for title, prefix, book in [("shl", "辨", "shang_han_lun")]:
    pass
for c in sorted({c["section"] for c in clauses}, key=lambda x: [cc["section"] for cc in clauses].index(x)):
    add("classic", sec_s(c), id=f"classic.shl_ch_{slug(sec_s(c))[:40]}", hotword=False, scope=[], prio=3,
        attrs={"kind": "chapter", "book": "classic.shang_han_lun"}, sources=[{"ref": "shl_wikisource"}])
jt = CORPUS["jgy_wikisource"]
for m in re.finditer(r"^===\s*(.*?)\s*===\s*$", s(strip_wiki((SRC / "jgy_wikisource_simp.wikitext").read_text())), re.M):
    n = re.sub(r"第[一二三四五六七八九十]+$", "", m.group(1)).strip()
    add("classic", n, id=f"classic.jgy_ch_{slug(n)[:40]}", hotword=False, scope=[], prio=3,
        attrs={"kind": "chapter", "book": "classic.jin_gui_yao_lve"}, sources=[{"ref": "jgy_wikisource"}])
NJFIX = {"金匮真言第论": "金匮真言论", "阴阳应像大论": "阴阳应象大论"}
idx = (SRC / "neijing_index.wikitext").read_text()
part = None
for line in idx.split("\n"):
    if line.startswith("==素問") or line.startswith("==素问"): part = "su_wen"
    if line.startswith("==靈樞") or line.startswith("==灵枢"): part = "ling_shu"
    m = re.match(r"^\*\*\s*(.+?)\s*$", line)
    if m and part:
        raw = s(re.sub(r"\[\[.*?\|(.*?)\]\]", r"\1", m.group(1)))
        num = re.search(r"第([一二三四五六七八九十]+)$", raw)
        n = re.sub(r"第?[一二三四五六七八九十]+$", "", raw); n = NJFIX.get(n, n)
        if not n: continue
        safe = len(n) >= 4 and n.endswith(("论", "篇"))
        add("classic", n, id=f"classic.{'sw' if part == 'su_wen' else 'ls'}_{slug(n)[:40]}", hotword=len(n) >= 4, scope=["nj"], prio=2,
            match="always" if safe else "context", ctx=[] if safe else ["篇", "《", "》", "内经", "素问", "灵枢", "第"],
            attrs={"kind": "chapter", "book": f"classic.{part}", **({"order_cn": num.group(1)} if num else {})},
            sources=[{"ref": "neijing_index"}], notes="篇名据维基文库目录" + ("（原目录误字已改）" if n in NJFIX.values() else ""))
IDS.get("classic.sw_shang_gu_tian_zhen_lun", {}).setdefault("asr_errors", []).append({"from": "上古天中", "to": "上古天真"}) if "classic.sw_shang_gu_tian_zhen_lun" in IDS else None
# ---------------------------------------------------------------- persons
curated("person", "张仲景/张机/仲景 王叔和 林亿 孙思邈 皇甫谧 华佗 扁鹊/秦越人 岐伯/歧伯 黄帝 雷公 伯高 少俞 伊尹 神农 李时珍 杨继洲 "
        "周左宇 刘力红 吴谦 陶弘景 葛洪 张伯祖 仓公 高保衡 孙奇 赵开美 王洙", scope=["global"], prio=2)
add("person", "倪海厦", aliases=["倪海廈", "倪师"], scope=["global"], prio=1, sources=[{"ref": "zhwiki_nihaixia"}, {"ref": "jingfangjia_844"}],
    notes="别名「倪师」为学生通行称呼（待审）")
for t in ("张仲景", "岐伯", "黄帝", "杨继洲"):
    k = f"person.{slug(t)}"
    if k in IDS: IDS[k]["hotword_priority"] = 1
if "person.zhang_zhong_jing" in IDS:
    IDS["person.zhang_zhong_jing"]["asr_errors"] = [{"from": x} for x in ("张仲锦", "张仲瑾", "张仲敏", "张仲尼")] + [
        {"from": "张仲你", "right": "发明|的|也|用"}]
if "person.huang_di" in IDS:
    IDS["person.huang_di"]["asr_errors"] = [{"from": "皇帝", "near_any": ["岐伯", "内经", "岐黄", "素问", "上古天真"], "window": 15}]
if "person.zhou_zuo_yu" in IDS: IDS["person.zhou_zuo_yu"]["notes"] = "倪师针灸老师"
# ---------------------------------------------------------------- course terms (人纪 priority; 天纪/地纪 light)
for t, al, sc, note in [("人纪", [], ["global"], "倪师中医课程：针灸大成、黄帝内经、神农本草经、伤寒论、金匮要略"),
                        ("天纪", [], ["global"], "倪师易经命理课程（1994）"), ("地纪", [], ["global"], "倪师计划中的地理志著作，未完成"),
                        ("汉唐中医", [], ["global"], "倪师所创学院/诊所名"), ("汉唐中医学院", [], ["global"], ""),
                        ("汉唐经方", [], ["global"], "汉唐经方中医诊所"), ("梵宇龙", [], ["global"], "倪师讲天文时所用化名"),
                        ("北派", [], ["zj"], "倪师所称「北派真传的针刺手法」"), ("紫微斗数", [], ["tj"], ""), ("八字", [], ["tj"], ""),
                        ("风水地理", [], ["tj"], "「风水」单独出现多指金匮风水病（syndrome），故不作别名"), ("面相", [], ["tj"], ""), ("易经", [], ["tj"], ""),
                        ("命理", [], ["tj"], ""), ("占卜", [], ["tj"], ""), ("仲景心法", [], ["shl", "jgy"], "倪师复讲课程名"),
                        ("八纲辨证", [], ["global"], "倪师课程名")]:
    e = add("course_term", t, aliases=al, scope=sc, prio=1 if sc == ["global"] else 2, notes=note)
    if not e["sources"]:
        if t in ("仲景心法", "八纲辨证"):
            e["sources"] = [{"ref": "web:hongyuanguoxue_51", "at": "课程目录"}]; e["attrs"]["verification"] = "web"
        else: e["sources"] = [{"ref": "unverified"}]; e["attrs"]["verification"] = "unverified"

# common-word guard: very frequent general words never become ASR hotwords
for cat in ("concept", "symptom", "method", "zangfu", "syndrome", "pulse", "disease", "tongue"):
    for e in ENTRIES[cat]:
        if FREQ.get(e["term"], 0) > 3000 and e["hotword"]:
            e["hotword"] = False
            e["notes"] = (e["notes"] + "；" if e["notes"] else "") + "通用高频词，不进热词"
if "pulse.dong" in IDS: IDS["pulse.dong"].update(match_policy="context", context_any=["脉", "数", "浮", "滑"], hotword=False, notes="与「动脉」(artery) 同形")
# ---------------------------------------------------------------- write entries
OUT = ROOT / "entries"; OUT.mkdir(exist_ok=True)
class D(yaml.SafeDumper): pass
def _list(d, v):
    flow = all(isinstance(x, (str, int)) for x in v) or all(isinstance(x, dict) and len(x) <= 3 and all(isinstance(y, (str, int, list)) for y in x.values()) for x in v)
    return d.represent_sequence("tag:yaml.org,2002:seq", v, flow_style=flow and len(v) > 0)
D.add_representer(list, _list)
def clean(e):
    return {k: v for k, v in e.items() if not (k in ("asr_errors", "context_any", "relations", "aliases") and not v) and not (k == "attrs" and not v) and not (k == "notes" and not v)}
HDR = "# lexicon v0.1 seed — generated by scripts/lexicon/seed_v0_1.py on 2026-10-19, then hand-maintained.\n# status: draft = 未经中医人工审核。Schema: lexicon/schema/lexicon_entry.schema.json\n"
for cat, es in ENTRIES.items():
    (OUT / f"{cat}.yaml").write_text(HDR + yaml.dump([clean(e) for e in es], Dumper=D, allow_unicode=True, sort_keys=False, width=200))
# ---------------------------------------------------------------- classics/shanghanlun.yaml
FORMULA_TERMS = sorted(((e["term"], e["id"]) for e in ENTRIES["formula"]), key=lambda x: -len(x[0]))
def clause_entities(t):
    ids = []; rest = t
    for term, fid in FORMULA_TERMS:
        if term in rest: ids.append(fid); rest = rest.replace(term, "＿")
    for six, sl in SIX:
        if six + "病" in t or six + "之为病" in t or six + "中风" in t or six + "伤寒" in t: ids.append(f"six_channel.{sl}")
    return list(dict.fromkeys(ids))
cl_out = {"book_id": "shanghanlun", "title": "伤寒论", "edition": "宋本（赵开美复刻本系统）",
          "numbering": "通行 398 条编号；按维基文库原文段落顺序推算，259 条与原文内嵌编号逐条吻合",
          "source": {"ref": "shl_wikisource", "url": "https://zh.wikisource.org/wiki/傷寒論", "revid": json.load(open(SRC / "shl_wikisource.json"))["parse"]["revid"],
                     "quality": "维基文库标注 Textquality 25%（部分章节未校订）"},
          "status": "draft", "clauses": []}
for c in clauses:
    t = s(c["text_trad"])
    cl_out["clauses"].append({"id": f"clause.shl.{c['no']:03d}", "no": c["no"], "section": sec_s(c["section"]), "text": t,
                              "text_trad": c["text_trad"], "entities": clause_entities(t)})
CL = ROOT / "classics"; CL.mkdir(exist_ok=True)
class D2(yaml.SafeDumper): pass
D2.add_representer(list, lambda d, v: d.represent_sequence("tag:yaml.org,2002:seq", v, flow_style=all(isinstance(x, str) for x in v)))
(CL / "shanghanlun.yaml").write_text("# 伤寒论 398 条（宋本）— 原文为公有领域古籍；文字取自维基文库，见 lexicon/sources/SOURCES.md\n" +
                                     yaml.dump(cl_out, Dumper=D2, allow_unicode=True, sort_keys=False, width=400))
# ---------------------------------------------------------------- report
rep = {cat: len(es) for cat, es in ENTRIES.items()}
print("counts", rep, "total", sum(rep.values()))
print("acupoint zh/en mismatches", len(acu_mismatch), acu_mismatch[:40])
print("skipped (unattested) curated terms", {k: v for k, v in SKIPPED.items()})
json.dump({"counts": rep, "skipped_unattested": SKIPPED, "acupoint_mismatch": acu_mismatch}, open(ROOT / "sources" / "seed_report.json", "w"), ensure_ascii=False, indent=1)
