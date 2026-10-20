import re, json, sys
import pathlib, os
os.chdir(pathlib.Path(__file__).resolve().parents[2] / 'lexicon' / 'sources')
t=open('shl_wikisource.wikitext').read()
t=re.sub(r'-\{(.*?)\}-',r'\1',t)
secs=list(re.finditer(r'^(=+)\s*(.*?)\s*\1\s*$',t,re.M))
EXP=[('辨太陽病脈證並治（上）第五',1,30),('辨太陽病脈證並治（中）第六',31,127),('辨太陽病脈證並治（下）第七',128,178),
('辨陽明病脈證並治第八',179,262),('辨少陽病脈證並治第九',263,272),('辨太陰病脈證並治第十',273,280),('辨少陰病脈證並治第十一',281,325),
('辨厥陰病脈證並治第十二',326,381),('辨霍亂病脈證並治第十三',382,391),('辨陰陽易差後勞復病脈證並治第十四',392,398)]
CN={'〇':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
def cnnum(s): return int(''.join(str(CN[c]) for c in s))
def is_formula_line(p):
    if re.match(r'^上[一二三四五六七八九十]+味',p): return True
    if re.search(r'同體別名',p): return True
    # ingredient line: no comma clause, contains dosage units
    if '，' not in p and re.search(r'[兩枚箇升斤銖合]',p) and len(p)<60: return True
    return False
out=[];dropped=[];anchors_ok=0;anchors_bad=[]
for name,a,b in EXP:
    i=[k for k,m in enumerate(secs) if m.group(2)==name][0]
    body=t[secs[i].end():secs[i+1].start()]
    paras=[p.strip().strip('\u3000 ') for p in body.split('\n') if p.strip() and not p.lstrip().startswith(':')]
    keep=[]
    for p in paras:
        (dropped if is_formula_line(p) else keep).append(p)
    if len(keep)!=b-a+1:
        print('COUNT MISMATCH',name,len(keep),b-a+1); sys.exit(1)
    for j,p in enumerate(keep):
        no=a+j
        m=re.match(r'^([〇一二三四五六七八九]{2,3})、',p)
        if m:
            if cnnum(m.group(1))==no: anchors_ok+=1
            else: anchors_bad.append((no,p[:20]))
            p=p[m.end():]
        out.append({'no':no,'section':name,'text_trad':p})
print('clauses',len(out),'anchors_ok',anchors_ok,'bad',anchors_bad)
print('dropped',dropped)
json.dump(out,open('shl_clauses_trad.json','w'),ensure_ascii=False,indent=0)
