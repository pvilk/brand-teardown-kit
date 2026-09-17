#!/usr/bin/env python3
"""Resolve advertiser pages via the Ad Library's OWN typeahead (the search box dropdown).
Use when keyword search is buried (brand name = a celebrity nickname), the domain query returns 0,
and facebook.com/<slug> is login-walled. Returns page_id + name + category + likes + ig_username + ig_followers.
Match on ig_username = the handle in the brand's site footer.

usage: typeahead_pages.py "Term 1" "Term 2" ... > pages.jsonl
Trap: the search input is DISABLED ("Choose an ad category") on the bare /ads/library/ URL.
It is enabled on a results URL that already carries q=..., so we load one of those first."""
import sys, json, asyncio
from playwright.async_api import async_playwright
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
START = ("https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=ALL"
         "&is_targeted_country=false&media_type=all&q=a&search_type=keyword_unordered")

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await b.new_context(user_agent=UA, viewport={"width": 1440, "height": 1200}, locale="en-US")
        pg = await ctx.new_page()
        caps = []
        async def on_resp(r):
            if "graphql" in r.url:
                try: caps.append(await r.text())
                except Exception: pass
        pg.on("response", on_resp)
        await pg.goto(START, wait_until="domcontentloaded", timeout=90000)
        await pg.wait_for_timeout(6000)
        inp = None
        for i in await pg.query_selector_all("input"):
            if await i.is_visible() and await i.is_enabled() and (await i.get_attribute("type")) == "search":
                inp = i
        if not inp:
            sys.exit("search input not found/enabled")
        for term in sys.argv[1:]:
            caps.clear()
            await inp.click(); await inp.fill("")
            await inp.type(term, delay=120)
            await pg.wait_for_timeout(5000)
            seen = {}
            for c in caps:
                for line in c.split("\n"):
                    try:
                        pr = json.loads(line.replace("for (;;);", ""))["data"]["ad_library_main"]["typeahead_suggestions"]["page_results"]
                    except Exception:
                        continue
                    for x in pr:
                        seen[x["page_id"]] = {k: x.get(k) for k in ("page_id", "name", "category", "likes", "ig_username",
                                                                      "ig_followers", "entity_type", "page_alias")}
            print(json.dumps({"term": term, "pages": list(seen.values())}, ensure_ascii=False), flush=True)
        await b.close()

asyncio.run(main())
