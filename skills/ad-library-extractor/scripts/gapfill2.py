#!/usr/bin/env python3
"""Open the 'See summary details' modal for grouped ads to recover the hidden link block."""
import sys, json, re, asyncio
from playwright.async_api import async_playwright

OUT, IDS_JSON = sys.argv[1], sys.argv[2]
ids = json.load(open(IDS_JSON))
DOM = re.compile(r"^[A-Z0-9][A-Z0-9.\-]*\.(COM|CO|NET|ORG|IO|SHOP|US|AI|APP|STORE)(/\S*)?$")
CTAS = {"shop now","learn more","sign up","order now","get offer","buy now","subscribe",
        "send message","contact us","apply now","download","watch more","book now","see more"}

CLICK = """()=>{const e=[...document.querySelectorAll('a,div[role=button],span')]
  .filter(x=>['See summary details','See ad details'].includes((x.textContent||'').trim()));
  if(e.length){e[0].click(); return true;} return false;}"""

SCROLL = """()=>{document.querySelectorAll('[role=dialog] *').forEach(n=>{
  if(n.scrollHeight>n.clientHeight+50) n.scrollTop=n.scrollHeight;});}"""


def link_blocks(text):
    lines = [re.sub("​", "", l).strip() for l in text.split("\n")]
    out = []
    for i, l in enumerate(lines):
        if not DOM.match(l):
            continue
        nxt = [x for x in lines[i+1:i+5] if x]
        head = desc = cta = ""
        rest = []
        for x in nxt:
            if x.lower() in CTAS and not cta: cta = x; break
            if x.startswith("Library ID") or x == "Active": break
            rest.append(x)
        if rest: head = rest[0]
        if len(rest) > 1: desc = " | ".join(rest[1:])
        out.append({"domain": l, "headline": head, "description": desc, "cta": cta})
    return out


async def main():
    res = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await b.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1500, "height": 1300}, locale="en-US")
        pg = await ctx.new_page()
        for i, aid in enumerate(ids, 1):
            blocks = []
            try:
                await pg.goto(f"https://www.facebook.com/ads/library/?id={aid}",
                              wait_until="domcontentloaded", timeout=90000)
                for _ in range(10):
                    await pg.wait_for_timeout(2500)
                    if await pg.evaluate("document.body.innerText.includes('Library ID:')"): break
                clicked = await pg.evaluate(CLICK)
                if clicked:
                    await pg.wait_for_timeout(5000)
                    for _ in range(5):
                        await pg.evaluate(SCROLL); await pg.wait_for_timeout(1800)
                    dlg = await pg.evaluate(
                        "[...document.querySelectorAll('[role=dialog]')].map(d=>d.innerText).join('\\n')")
                    blocks = link_blocks(dlg or "")
                # NOTE: deliberately no page-body fallback — it pulls in other
                # advertisers' cards from the grid and yields wrong headlines.
            except Exception as e:
                print(f"  [{i}/{len(ids)}] {aid} ERROR {type(e).__name__}", flush=True)
            # keep the most common block (all versions share one link block)
            uniq = {}
            for bl in blocks:
                k = (bl["headline"], bl["description"], bl["cta"])
                uniq[k] = uniq.get(k, 0) + 1
            best = max(uniq.items(), key=lambda kv: kv[1])[0] if uniq else None
            res[aid] = ({"domain": blocks[0]["domain"] if blocks else "",
                         "headline": best[0], "description": best[1], "cta": best[2]}
                        if best else None)
            print(f"  [{i}/{len(ids)}] {aid} -> {res[aid]['headline'][:55] if res[aid] else 'NONE'}", flush=True)
        json.dump(res, open(OUT, "w"), indent=1)
        await b.close()

asyncio.run(main())
