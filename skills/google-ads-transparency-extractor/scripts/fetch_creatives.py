#!/usr/bin/env python3
"""Pull EVERY creative for a domain or advertiser id.  ->  creatives_raw.json

    python3 fetch_creatives.py example.com [US] [outdir]
    python3 fetch_creatives.py AR02151448538469367809 [US] [outdir]

Then it MEASURES the format enum instead of trusting it: public scrapers disagree
(1=TEXT vs 1=IMAGE), so we correlate the format code against the content shape.
"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gat_lib import search_creatives, content_url, image_html, RateLimited

target = sys.argv[1] if len(sys.argv) > 1 else sys.exit("usage: fetch_creatives.py <domain|AR-id> [region] [outdir]")
region = sys.argv[2] if len(sys.argv) > 2 else "US"
outdir = sys.argv[3] if len(sys.argv) > 3 else "."
os.makedirs(outdir, exist_ok=True)

print(f"fetching {target} (region {region})")
try:
    rows = search_creatives(target, region)
except RateLimited as e:
    sys.exit(f"\nRATE LIMITED: {e}")
if not rows:
    print("\n0 creatives. Either this advertiser genuinely has no ads in this region, OR your\n"
          "field shape is wrong (a bad shape returns HTTP 200 with {} -- silent). Sanity-check\n"
          f"against https://adstransparency.google.com/?region={region}&domain={target}", file=sys.stderr)
json.dump(rows, open(os.path.join(outdir, "creatives_raw.json"), "w"), indent=1)

combo = collections.Counter()
for r in rows:
    shape = "preview_url(video)" if content_url(r) else ("img_html(static)" if image_html(r) else "none")
    combo[(r.get("4"), shape)] += 1
print(f"\nTOTAL unique creatives: {len(rows)}")
print("\n=== format code x content shape (THIS is your video filter, do not guess) ===")
for (code, shape), n in sorted(combo.items(), key=lambda x: -x[1]):
    print(f"  code={code!r:5} {shape:20} -> {n}")

advs = collections.Counter((r.get("1"), r.get("12")) for r in rows)
print("\n=== advertisers (a domain can span several; do not assume rows[0]) ===")
for (aid, name), n in advs.most_common():
    print(f"  {aid}  {name}  -> {n}")
