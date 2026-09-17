#!/usr/bin/env python3
"""Pick the brand's own page from candidates.json by NAME match (not ad count), flag the rest."""
import json, re, sys, unicodedata

C = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "candidates.json"))
OVERRIDE = json.load(open("overrides.json")) if __import__("os").path.exists("overrides.json") else {}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(the|official|inc|co|llc|hq|us|usa)\b", " ", s)
    return re.sub(r"[^a-z0-9]", "", s)


out, flags = {}, []
for label, r in C.items():
    if label in OVERRIDE:
        out[label] = OVERRIDE[label]
        continue
    lab, q = norm(label), norm(r["query"])
    best, score = None, 0
    for c in r["candidates"]:
        n = norm(c["page_name"])
        s = 0
        if n in (lab, q):
            s = 3
        elif n and (n in lab or lab in n or n in q or q in n):
            s = 2
        if s > score or (s == score and s and c["ads"] > best["ads"]):
            best, score = c, s
    if best:
        out[label] = {"page_id": best["page_id"], "page_name": best["page_name"], "match": score}
        if score < 3:
            flags.append(label)
    else:
        flags.append(label)
        out[label] = None

for label in C:
    v = out[label]
    mark = "  " if label not in flags else "??"
    print(f"{mark} {label:28s} -> {v['page_name'] + ' (' + v['page_id'] + ')' if v else 'NONE'}")
print("\nFLAGGED:", flags)
json.dump(out, open("picked.json", "w"), indent=1, ensure_ascii=False)
