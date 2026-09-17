#!/usr/bin/env python3
"""Harvest FB Ad Library cards (copy + creative image URLs) via Playwright."""
import sys, json, re, asyncio, time
from playwright.async_api import async_playwright

URL      = sys.argv[1]
OUT      = sys.argv[2]
MAX_IDLE = int(sys.argv[3]) if len(sys.argv) > 3 else 30

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
    const imgs = [...el.querySelectorAll('img')].map(i => i.src)
      .filter(s => s && s.includes('fbcdn') && !/[ps]60x60/.test(s) && !/s\d\dx\d\d[_.]/.test(s));
    const vids = [...el.querySelectorAll('video')].map(v => v.poster || '').filter(Boolean);
    out[m[1]] = { id: m[1], text: t, imgs: [...new Set(imgs)],
                  nvideo: el.querySelectorAll('video').length, posters: [...new Set(vids)] };
  });
  return out;
}
"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = await b.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 1200}, locale="en-US")
        pg = await ctx.new_page()
        await pg.goto(URL, wait_until="domcontentloaded", timeout=90000)

        for _ in range(15):
            await pg.wait_for_timeout(3000)
            if await pg.evaluate("document.body.innerText.includes('Library ID:')"): break

        body = await pg.evaluate("document.body.innerText")
        label = re.search(r"~?[\d,]+ results", body)
        label = label.group(0) if label else "unknown"
        print(f"results label: {label}", flush=True)

        store, idle, cycles, t0 = {}, 0, 0, time.time()
        while idle < MAX_IDLE and time.time() - t0 < 2400:
            batch = await pg.evaluate(HARVEST)
            before = len(store)
            store.update(batch)
            gained = len(store) - before
            idle = 0 if gained else idle + 1
            cycles += 1
            if cycles % 15 == 0:
                print(f"  cycle {cycles} | unique {len(store)} | idle {idle}", flush=True)

            await pg.evaluate("window.scrollBy(0, 550)")
            await pg.wait_for_timeout(850)

            # near bottom -> jiggle to re-arm the loader
            near = await pg.evaluate(
                "(window.innerHeight + window.scrollY) > (document.body.scrollHeight - 1800)")
            if near:
                h = await pg.evaluate("document.body.scrollHeight")
                await pg.evaluate(f"window.scrollTo(0, {max(0, h-1600)})")
                await pg.wait_for_timeout(700)
                await pg.evaluate(f"window.scrollTo(0, {h})")
                await pg.wait_for_timeout(1600)

        print(f"DONE cycles={cycles} unique={len(store)}", flush=True)

        # ---- download images with the browser's own session ----
        imgdir = OUT.replace(".json", "_img")
        import os, hashlib
        os.makedirs(imgdir, exist_ok=True)
        ok = fail = 0
        for aid, rec in store.items():
            rec["files"] = []
            for k, u in enumerate(rec["imgs"] + rec["posters"]):
                try:
                    r = await ctx.request.get(u, timeout=45000)
                    if r.status != 200:
                        fail += 1; continue
                    buf = await r.body()
                    if len(buf) < 3000:
                        continue
                    ext = ".png" if buf[:4] == b"\x89PNG" else ".jpg"
                    fn = f"{aid}_{k}{ext}"
                    with open(os.path.join(imgdir, fn), "wb") as f:
                        f.write(buf)
                    rec["files"].append(fn); ok += 1
                except Exception:
                    fail += 1
        print(f"images ok={ok} fail={fail} -> {imgdir}", flush=True)

        json.dump({"url": URL, "label": label, "count": len(store),
                   "ads": store}, open(OUT, "w"), indent=1)
        await b.close()

asyncio.run(main())
