#!/usr/bin/env python3
"""Google Ads Transparency Center check for a brand: advertiser-name suggestions, creative counts per
domain and region, plus a CONTROL domain so an empty result means "no ads", not "broken request".

usage: python3 google_ads_check.py --brand "Drizzy" --domain getdrizzy.co [--domain au.getdrizzy.co] \
         [--region US --region AU] [--control takeultra.com] [--out google_ads.json]
The RPC works from plain Python (no cookie, no key). The web UI serves a captcha to headless browsers,
so do not use it as the sanity check; use the control domain."""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gat_lib import rpc, REGIONS

ap = argparse.ArgumentParser()
ap.add_argument("--brand", action="append", default=[])
ap.add_argument("--domain", action="append", default=[])
ap.add_argument("--region", action="append", default=[])
ap.add_argument("--control", default="takeultra.com")
ap.add_argument("--out", default="google_ads.json")
a = ap.parse_args()
out = {"suggestions": {}, "creatives": {}}

for q in a.brand:
    r = rpc("SearchService/SearchSuggestions", {"1": q, "2": 10, "3": 10})
    out["suggestions"][q] = r
    print("SUGGEST", q, json.dumps(r)[:400])

regions = a.region or ["ANYWHERE"]
for d in a.domain:
    for reg in regions:
        filt = {"12": {"1": d, "2": True}}
        if reg != "ANYWHERE":
            filt["8"] = [REGIONS.get(reg.upper(), 2840)]
        r = rpc("SearchService/SearchCreatives", {"2": 100, "3": filt, "7": {"1": 1}})
        n = len(r.get("1") or [])
        out["creatives"][f"{d}|{reg}"] = {"rows": n, "has_more": bool(r.get("2"))}
        print(f"{d:30s} {reg:9s} creatives on first page: {n}{' (more pages)' if r.get('2') else ''}")

r = rpc("SearchService/SearchCreatives", {"2": 10, "3": {"8": [2840], "12": {"1": a.control, "2": True}}, "7": {"1": 1}})
out["control"] = {a.control: len(r.get("1") or [])}
print(f"CONTROL {a.control} US rows: {out['control'][a.control]}  (0 here means the request is broken, not that ads are absent)")
json.dump(out, open(a.out, "w"), indent=1)
print("wrote", a.out)
