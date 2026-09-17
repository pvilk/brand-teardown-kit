#!/usr/bin/env python3
"""Load each final view_all_page_id link and read back the page name + result count the
Ad Library itself shows. Proves every link lands on the right brand page. Output: verified.json"""
import sys, json, re, asyncio
from playwright.async_api import async_playwright

PICKS = json.load(open(sys.argv[1]))           # {"label": {"page_id":..., "page_name":...}}
OUT = sys.argv[2] if len(sys.argv) > 2 else "verified.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


import os
STATUS = os.environ.get("ADLIB_STATUS", "active")
COUNTRY = os.environ.get("ADLIB_COUNTRY", "US")


def link(pid):
    return (f"https://www.facebook.com/ads/library/?active_status={STATUS}&ad_type=all&country={COUNTRY}"
            f"&is_targeted_country=false&media_type=all&search_type=page&view_all_page_id={pid}")


async def check(ctx, label, v, sem, res):
    async with sem:
        pg = await ctx.new_page()
        names = []
        try:
            await pg.goto(link(v["page_id"]), wait_until="domcontentloaded", timeout=90000)
            for _ in range(8):
                await pg.wait_for_timeout(2500)
                body = await pg.evaluate("document.body.innerText")
                if "Library ID:" in body or "No ads match" in body or re.search(r"\d+ results?", body):
                    break
            html = await pg.content()
            names = re.findall(r'"page_name":"((?:[^"\\]|\\.)*)"', html)
            names = [json.loads(f'"{n}"') for n in names]
            count = re.search(r"~?[\d,]+ results?", body)
            count = count.group(0) if count else ("0 results" if "No ads match" in body else None)
        except Exception as e:
            count = f"ERR {e}"
        top = max(set(names), key=names.count) if names else None
        in_text = v["page_name"].lower() in (body or "").lower()
        res[label] = {**v, "url": link(v["page_id"]), "shown_name": top, "name_in_text": in_text,
                      "active_results": count}
        ok = "OK " if (top and top.lower() == v["page_name"].lower()) or in_text else "?? "
        print(f"{ok}{label:26s} {v['page_id']:>18s}  expected={v['page_name']!r:32s} shown={top!r:32s} {count}", flush=True)
        await pg.close()


async def main():
    res = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await b.new_context(user_agent=UA, viewport={"width": 1440, "height": 1200}, locale="en-US")
        sem = asyncio.Semaphore(4)
        await asyncio.gather(*[check(ctx, k, v, sem, res) for k, v in PICKS.items() if v])
        await b.close()
    json.dump(res, open(OUT, "w"), indent=1, ensure_ascii=False)
    print("wrote", OUT)

asyncio.run(main())
