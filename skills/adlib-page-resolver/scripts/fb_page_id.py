#!/usr/bin/env python3
"""Read a Facebook page's numeric page ID (and title) from its public profile HTML."""
import sys, re, asyncio
from playwright.async_api import async_playwright

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


async def one(ctx, slug):
    pg = await ctx.new_page()
    try:
        await pg.goto(f"https://www.facebook.com/{slug}", wait_until="domcontentloaded", timeout=60000)
        await pg.wait_for_timeout(5000)
        html = await pg.content()
        title = await pg.title()
        ids = {}
        for pat in [r'"pageID":"(\d+)"', r'"delegate_page":\{"id":"(\d+)"', r'"userID":"(\d+)"',
                    r'"profile_owner":\{"id":"(\d+)"', r'fb://page/\??id=(\d+)', r'fb://profile/(\d+)']:
            for m in re.findall(pat, html):
                ids.setdefault(m, pat.split('"')[1] if '"' in pat else pat[:12])
        print(f"{slug:28s} | {title[:50]!r:52s} | {pg.url[:60]} | {ids}", flush=True)
    except Exception as e:
        print(f"{slug}: ERR {e}")
    await pg.close()


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await b.new_context(user_agent=UA, locale="en-US")
        await asyncio.gather(*[one(ctx, s) for s in sys.argv[1:]])
        await b.close()

asyncio.run(main())
