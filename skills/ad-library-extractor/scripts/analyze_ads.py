#!/usr/bin/env python3
"""Join ad metadata + transcripts; extract hooks, angles, selling points. Edit CONCEPTS for the category."""
import json, glob, os, re, collections
import sys
BASE=sys.argv[1] if len(sys.argv)>1 else "."   # usage: analyze_ads.py [basedir]
ads={a["id"]:a for a in json.load(open(f"{BASE}/ads_parsed.json"))}
tr={}
for f in glob.glob(f"{BASE}/transcripts/*.json"):
    d=json.load(open(f))
    if d.get("text"): tr[d["id"]]=d
print(f"ads={len(ads)}  transcripts={len(tr)}")

rows=[]
for aid,t in tr.items():
    a=ads.get(aid,{})
    segs=t.get("segments") or []
    hook=" ".join(s["t"] for s in segs if s["s"]<4.0).strip() or t["text"][:160]
    rows.append({"id":aid,"advertiser":a.get("advertiser",""),"started":a.get("started",""),
                 "dur":t.get("dur"),"hook":hook,"text":t["text"],
                 "headline":a.get("headline"),"body":(a.get("body") or "")[:120]})
json.dump(rows, open(f"{BASE}/ad_transcripts_joined.json","w"), indent=1)

def norm(s): return re.sub(r'[^a-z0-9 ]','',s.lower()).strip()
# dedupe by normalized full transcript
byt=collections.defaultdict(list)
for r in rows: byt[norm(r["text"])[:400]].append(r)
print(f"unique transcripts (first 400 norm chars): {len(byt)}")

print("\n" + "="*80)
print("TOP 40 OPENING HOOKS (first ~4s), by how many ads use them")
print("="*80)
hk=collections.defaultdict(list)
for r in rows: hk[norm(r["hook"])[:110]].append(r)
for k,v in sorted(hk.items(), key=lambda x:-len(x[1]))[:40]:
    if not k: continue
    print(f"\n[x{len(v)}] {v[0]['hook'][:190]}")
    print(f"      advertisers: {', '.join(sorted({x['advertiser'][:28] for x in v})[:3])}")

# Angle/concept patterns to count. These are GENERIC DTC starters: edit them for the brand's category.
CONCEPTS={
 "convenience / saves time":        r"easy|convenient|in (one|1) step|no mess|on the go|minutes|quick|simple",
 "problem / frustration":           r"tired of|sick of|hate when|annoying|struggl|frustrat|finally",
 "social proof / reviews":          r"reviews|customers|people (love|swear)|sold out|viral|everyone|best.?seller",
 "offer / discount":                r"% off|discount|sale|free shipping|free gift|bundle|bogo|limited time",
 "health / ingredients":            r"natural|no added sugar|clean|protein|ingredients|organic|healthy|non.?gmo",
 "taste / sensory":                 r"taste|delicious|flavor|crav|obsessed|yum",
 "gift / occasion":                 r"gift|holiday|birthday|christmas|mother.?s day|father.?s day",
 "comparison / vs competitor":      r"better than|instead of|unlike|compared|switch(ed)? from|vs\.?",
 "founder / story":                 r"founder|we started|our story|family|small business",
 "retail availability":             r"available at|find us at|in stores|now at|target|walmart|costco|sprouts|whole foods",
}
print("\n" + "="*80)
print(f"CONCEPT FREQUENCY across {len(rows)} transcribed ads")
print("="*80)
res=[]
for name,pat in CONCEPTS.items():
    hits=[r for r in rows if re.search(pat, r["text"], re.I)]
    res.append((len(hits),name,hits))
for n,name,hits in sorted(res, reverse=True):
    print(f"  {n:4d} ({100*n/max(len(rows),1):3.0f}%)  {name}")
json.dump({n:[h['id'] for h in hits] for _,n,hits in res}, open(f"{BASE}/concept_index.json","w"))
