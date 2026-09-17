#!/usr/bin/env python3
"""For each brand query, load the FB Ad Library keyword search and tally the advertiser pages
(page_id, page_name, likes, profile uri) found in the embedded ad records. Output: candidates.json"""
import sys, json, re, asyncio, urllib.parse
from playwright.async_api import async_playwright

QUERIES = json.load(open(sys.argv[1]))          # {"label": "query", ...}
OUT = sys.argv[2] if len(sys.argv) > 2 else "candidates.json"
CONC = 4
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def walk(o, found):
    if isinstance(o, dict):
        if "page_id" in o and "page_name" in o and o.get("page_id"):
            found.append({k: o.get(k) for k in ("page_id", "page_name", "page_like_count",
                                                "page_profile_uri", "page_is_deleted")})
        for v in o.values():
            walk(v, found)
    elif isinstance(o, list):
        for v in o:
            walk(v, found)


def parse_blobs(texts):
    found = []
    for t in texts:
        t = t.lstrip()
        if t.startswith("for (;;);"):
            t = t[9:]
        chunks = [t]
        if "\n" in t:
            chunks += t.split("\n")
        for c in chunks:
            try:
                walk(json.loads(c), found)
            except Exception:
                pass
    return found


async def resolve(ctx, label, q, sem, results):
    async with sem:
        pg = await ctx.new_page()
        bodies = []

        async def on_resp(r):
            try:
                t = await r.text()
            except Exception:
                return
            if "page_name" in t:
                bodies.append(t)
        pg.on("response", on_resp)
        url = ("https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=US"
               f"&is_targeted_country=false&media_type=all&q={urllib.parse.quote(q)}"
               "&search_type=keyword_unordered")
        try:
            await pg.goto(url, wait_until="domcontentloaded", timeout=90000)
            for _ in range(8):
                await pg.wait_for_timeout(2500)
                if await pg.evaluate("document.body.innerText.includes('Library ID:') || document.body.innerText.includes('No ads match')"):
                    break
            await pg.wait_for_timeout(1500)
            html = await pg.content()
            scripts = re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', html, re.S)
            found = parse_blobs(scripts + bodies)
            body = await pg.evaluate("document.body.innerText")
            label_m = re.search(r"~?[\d,]+ results?", body)
        except Exception as e:
            found, label_m = [], None
            print(f"ERR {label}: {e}", flush=True)
        tally = {}
        for f in found:
            pid = str(f["page_id"])
            d = tally.setdefault(pid, {"page_id": pid, "page_name": f["page_name"], "ads": 0,
                                       "likes": f.get("page_like_count"),
                                       "uri": f.get("page_profile_uri")})
            d["ads"] += 1
            if f.get("page_like_count"):
                d["likes"] = f["page_like_count"]
            if f.get("page_profile_uri"):
                d["uri"] = f["page_profile_uri"]
        cands = sorted(tally.values(), key=lambda d: -d["ads"])[:8]
        results[label] = {"query": q, "results_label": label_m.group(0) if label_m else None,
                          "candidates": cands}
        top = cands[0] if cands else {}
        print(f"{label:32s} | {q:28s} | {top.get('page_name')} ({top.get('page_id')}) x{top.get('ads')} | {len(cands)} pages", flush=True)
        await pg.close()


async def main():
    results = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await b.new_context(user_agent=UA, viewport={"width": 1440, "height": 1200}, locale="en-US")
        sem = asyncio.Semaphore(CONC)
        await asyncio.gather(*[resolve(ctx, k, v, sem, results) for k, v in QUERIES.items()])
        await b.close()
    json.dump(results, open(OUT, "w"), indent=1, ensure_ascii=False)
    print("wrote", OUT)

asyncio.run(main())
