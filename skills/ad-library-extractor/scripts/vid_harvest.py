#!/usr/bin/env python3
"""Scroll the FB Ad Library video-filtered grid and harvest Library ID -> video src + poster + copy.
usage: vid_harvest.py <PAGE_ID> [outdir]   ->  <outdir>/videos_meta.json"""
import json, asyncio, sys
from playwright.async_api import async_playwright

import sys
PID=sys.argv[1] if len(sys.argv)>1 else None
BASEDIR=sys.argv[2] if len(sys.argv)>2 else "."
if not PID:
    sys.exit("usage: vid_harvest.py <PAGE_ID> [outdir]")
URL=("https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US"
     "&is_targeted_country=false&media_type=video&search_type=page"
     "&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id="+PID)
OUT=f"{BASEDIR}/videos_meta.json"

HARVEST = r"""
() => {
  const out = {};
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const roots = new Set();
  let n;
  while ((n = walker.nextNode())) {
    if (!/Library ID:\s*\d+/.test(n.nodeValue || '')) continue;
    let el = n.parentElement, best = null;
    while (el && el !== document.body) {
      const t = el.innerText || '';
      const ids = t.match(/Library ID:\s*\d+/g) || [];
      if (ids.length === 1 && /Sponsored/.test(t)) { best = el; break; }
      if (ids.length > 1) break;
      el = el.parentElement;
    }
    if (best) roots.add(best);
  }
  roots.forEach(el => {
    const t = el.innerText || '';
    const m = t.match(/Library ID:\s*(\d+)/);
    if (!m) return;
    const vs = [...el.querySelectorAll('video')];
    out[m[1]] = {
      id: m[1], text: t,
      vsrc: vs.map(v => v.src).filter(s => s && s.startsWith('http')),
      poster: vs.map(v => v.poster).filter(Boolean)
    };
  });
  return out;
}
"""

async def main():
    acc={}
    async with async_playwright() as p:
        b=await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx=await b.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                                viewport={"width":1440,"height":1200}, locale="en-US")
        pg=await ctx.new_page()
        await pg.goto(URL, wait_until="domcontentloaded", timeout=90000)
        for _ in range(15):
            await pg.wait_for_timeout(2500)
            if await pg.evaluate("document.body.innerText.includes('Library ID:')"): break
        idle=0; cycle=0
        while idle < 40 and cycle < 900:
            cycle+=1
            cur=await pg.evaluate(HARVEST)
            before=len(acc)
            for k,v in cur.items():
                if k not in acc: acc[k]=v
                else:
                    for s in v.get("vsrc",[]):
                        if s not in acc[k]["vsrc"]: acc[k]["vsrc"].append(s)
                    for s in v.get("poster",[]):
                        if s not in acc[k]["poster"]: acc[k]["poster"].append(s)
            idle = 0 if len(acc)>before else idle+1
            await pg.evaluate("window.scrollBy(0, 550)")
            await pg.wait_for_timeout(850)
            if idle>0 and idle%12==0:
                h=await pg.evaluate("document.body.scrollHeight")
                await pg.evaluate(f"window.scrollTo(0,{max(0,h-1600)})"); await pg.wait_for_timeout(1200)
                await pg.evaluate(f"window.scrollTo(0,{h})"); await pg.wait_for_timeout(1500)
            if cycle%15==0:
                withv=sum(1 for a in acc.values() if a["vsrc"])
                print(f"cycle {cycle} | ads {len(acc)} | with_video_url {withv} | idle {idle}", flush=True)
                json.dump(acc, open(OUT,"w"), indent=1)
        json.dump(acc, open(OUT,"w"), indent=1)
        withv=sum(1 for a in acc.values() if a["vsrc"])
        print(f"DONE ads={len(acc)} with_video_url={withv}", flush=True)
        await b.close()
asyncio.run(main())
