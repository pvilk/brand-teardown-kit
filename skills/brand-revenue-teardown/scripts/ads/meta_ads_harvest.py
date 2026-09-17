#!/usr/bin/env python3
"""Harvest FB Ad Library GraphQL ad records (server HTML + pagination XHRs) for a view_all_page_id URL.
usage: harvest_records.py <url> <out.json> [max_idle]"""
import sys, json, re, asyncio
from playwright.async_api import async_playwright
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
URL, OUT = sys.argv[1], sys.argv[2]
MAX_IDLE = int(sys.argv[3]) if len(sys.argv) > 3 else 25
recs, counts = {}, []

def walk(o):
    if isinstance(o, dict):
        if "ad_archive_id" in o and isinstance(o.get("snapshot"), dict):
            recs[str(o["ad_archive_id"])] = o
        if "search_results_connection" in o and isinstance(o["search_results_connection"], dict):
            c = o["search_results_connection"].get("count")
            if c is not None: counts.append(c)
        for v in o.values(): walk(v)
    elif isinstance(o, list):
        for v in o: walk(v)

def parse(t):
    t = t.lstrip()
    if t.startswith("for (;;);"): t = t[9:]
    try:
        walk(json.loads(t)); return
    except Exception: pass
    for line in t.split("\n"):
        line=line.strip()
        if not line: continue
        try: walk(json.loads(line))
        except Exception: pass

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await b.new_context(user_agent=UA, viewport={"width": 1440, "height": 1200}, locale="en-US")
        pg = await ctx.new_page()
        async def on_resp(r):
            try: t = await r.text()
            except Exception: return
            if "ad_archive_id" in t or "search_results_connection" in t: parse(t)
        pg.on("response", on_resp)
        await pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
        body = ""
        for _ in range(10):
            await pg.wait_for_timeout(2500)
            body = await pg.evaluate("document.body.innerText")
            if "Library ID:" in body or "No ads match" in body: break
        html = await pg.content()
        for s in re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', html, re.S): parse(s)
        m = re.search(r"~?[\d,]+ results?", body)
        label = m.group(0) if m else ("0 results" if "No ads match" in body else None)
        print("label:", label, "initial recs:", len(recs), flush=True)
        idle, last = 0, -1
        while idle < MAX_IDLE:
            await pg.evaluate("window.scrollBy(0,550)")
            await pg.wait_for_timeout(850)
            h = await pg.evaluate("document.body.scrollHeight"); y = await pg.evaluate("window.scrollY+window.innerHeight")
            if h - y < 1800:
                await pg.evaluate("window.scrollTo(0, document.body.scrollHeight-1600)"); await pg.wait_for_timeout(700)
                await pg.evaluate("window.scrollTo(0, document.body.scrollHeight)"); await pg.wait_for_timeout(1600)
            if len(recs) == last: idle += 1
            else: idle, last = 0, len(recs)
        # final DOM text per library id (for EU reach etc.)
        body = await pg.evaluate("document.body.innerText")
        html = await pg.content()
        for s in re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', html, re.S): parse(s)
        json.dump({"url": URL, "label": label, "payload_counts": counts, "records": recs}, open(OUT, "w"), ensure_ascii=False)
        print("done recs:", len(recs), "payload counts:", sorted(set(counts)), flush=True)
        await b.close()
asyncio.run(main())
