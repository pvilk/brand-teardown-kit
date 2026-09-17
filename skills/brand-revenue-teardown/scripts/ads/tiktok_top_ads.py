#!/usr/bin/env python3
"""TikTok Creative Center "Top Ads" keyword search, logged out, with a control term.
usage: python3 tiktok_top_ads.py --term drizzy --term getdrizzy --region US --region AU [--control "peanut butter"] [--out-dir tiktok/]
Weak evidence: Top Ads only lists ads the advertiser opted in AND that cleared performance thresholds.
The URL keyword= param is ignored, so the script types into the search box after removing the promo modal."""
import argparse, asyncio, json, os
from playwright.async_api import async_playwright
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
ap = argparse.ArgumentParser()
ap.add_argument("--term", action="append", required=True)
ap.add_argument("--region", action="append", default=[])
ap.add_argument("--control", default="peanut butter")
ap.add_argument("--out-dir", default="tiktok")
a = ap.parse_args()
os.makedirs(a.out_dir, exist_ok=True)

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await b.new_context(user_agent=UA, viewport={"width": 1440, "height": 1200}, locale="en-US")
        res = {}
        for region in (a.region or ["US"]):
            for term in a.term + [a.control]:
                pg = await ctx.new_page(); caps = []
                async def on_resp(r):
                    if "top_ads" in r.url:
                        try: caps.append({"url": r.url, "body": await r.text()})
                        except Exception: pass
                pg.on("response", on_resp)
                await pg.goto(f"https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en?period=180&region={region}",
                              wait_until="domcontentloaded", timeout=90000)
                await pg.wait_for_timeout(8000)
                inp = None
                for i in await pg.query_selector_all("input"):
                    ph = (await i.get_attribute("placeholder")) or ""
                    if await i.is_visible() and ("earch" in ph or "keyword" in ph.lower()):
                        inp = i; break
                if not inp:
                    print(region, term, "search input not found"); await pg.close(); continue
                caps.clear()
                await pg.keyboard.press("Escape"); await pg.wait_for_timeout(800)
                await pg.evaluate("document.querySelectorAll('.byted-modal-wrapper,.byted-modal-mask,[class*=RevampPopup]').forEach(e=>e.remove())")
                await inp.click(force=True); await inp.type(term, delay=80); await pg.keyboard.press("Enter")
                await pg.wait_for_timeout(9000)
                total = None
                for c in caps:
                    try:
                        j = json.loads(c["body"]); pag = (j.get("data") or {}).get("pagination") or {}
                        if "total_count" in pag: total = pag["total_count"]
                    except Exception:
                        pass
                res[f"{region}|{term}"] = total
                print(f"{region} {term!r:24s} total_count={total}{'  (control)' if term == a.control else ''}")
                await pg.close()
        json.dump(res, open(os.path.join(a.out_dir, "top_ads_counts.json"), "w"), indent=1)
        await b.close()
asyncio.run(main())
