---
name: ad-library-extractor
description: Pull EVERY ad (full copy, and optionally the native images) out of an ad library or ad-intel swipe board into one MD file + an images folder. Use when the user gives a Facebook Ad Library link (facebook.com/ads/library/?q=<brand>), a gethookd/Foreplay/Atria/Motion-style shared board link, or any "ad-intel" URL and says "go through this whole ad library", "pull all the ads / all the copy / the native images", "extract every ad on this board", "give me all the different copies + images", or "do this one too". Handles the two hard cases: (1) FB Ad Library = browser-harvest with a background scroll loop + in-browser fetch+zip for images; (2) any React SPA board (gethookd etc.) = find the paginated JSON API via read_network_requests and hit it directly. Copy-only or copy+images per request. Brand-agnostic. Saves to a project folder.
---

# ad-library-extractor

Extract all ads (copy + optional images) from an ad library / swipe board into a project folder — one `*_copy.md` (grouped, full long-form copy verbatim) + an `images/` folder. Validated July 2026 on a ~3,900-ad Facebook Ad Library advertiser and a 300-ad gethookd shared board (82 brands).

## First: which playbook?
- Only a brand NAME (no URL)? Run the **`adlib-page-resolver`** skill first: it returns the brand's verified `view_all_page_id` link (keyword search would hand you affiliates' ads).
- URL is `facebook.com/ads/library/...` → **Playbook A (browser harvest)**.
- URL is a **React SPA board** (gethookd.ai, Foreplay, Atria, Motion, etc.) → **Playbook B (hit the API)**. Always try B for SPAs — it's faster, complete, and exact. Scroll-harvesting a virtualized SPA grid caps at a useless handful.
- Ask up front only what changes the work: **copy-only or copy+images?** and **which slug/folder?** (default: a folder named after the brand or board). Then show 2-3 samples to confirm you're pulling the right thing before the full run.

## Global gotchas (both playbooks) — these WILL bite
- **`javascript_tool` output filter blocks any returned URL with a query string AND any base64 blob.** So you cannot return signed image URLs to the shell. Plain ad copy text returns fine. Workarounds below.
- **Chrome blocks a site's 2nd+ automatic (non-gesture) download.** First `<a download>.click()` works; the next is silently dropped. Fix: do each later download from a **freshly-reloaded / new tab** (fresh page session resets the block). Pass data between tabs via `localStorage` — but some apps (Facebook) call `localStorage.clear()` on load, so write it from an already-loaded tab and read it in the new tab's FIRST call.
- **Long CDP calls "time out" at 45s but the page keeps running the async** — fire-and-forget background loops keep harvesting; poll a `window.__x` var with instant calls.
- **`read_network_requests` only tracks from its first call** — call it once, then RELOAD the page so the data-fetch requests are captured.
- Build big outputs (MD, image zip) **in-browser and download them**; only return small status/counts to yourself. Save deliverables to the project folder.

## Playbook A0 — Chrome extension dead? Use Playwright (PREFERRED for FB)
If `tabs_context_mcp` says "Browser extension is not connected" and `list_connected_browsers` → `[]`, **do not stop.** The FB Ad Library is public — no login needed — and install them with `pip install playwright && playwright install chromium`. Headless chromium with a desktop UA renders the grid fine, and it beats the extension outright: no `javascript_tool` output filter, no download blocks, no `localStorage.clear()`. Harvest straight into Python; download images with `ctx.request.get(url)` (carries cookies, no CORS, no in-browser zip). Raw `curl` to `/ads/library/async/search_ads/` is dead — 403 + JS challenge.

**⚠️ `media_type=image` MATCHES NOTHING.** The chip renders ("Media type: Images") so it looks applied, but returns "No ads match your search criteria" even for advertisers with dozens of statics — FB classifies nearly every static creative as a **meme**. For "anything that's an image" use **`media_type=image_and_meme`**. (Others: `meme`, `video`, `none`.) Always sanity-check a filter's result count against `media_type=all` before trusting a zero.

**Resolution ceiling:** statics cap at 600px tall (`stp=dst-jpg_s600x600_tt6` → 338x600); the `?id=` detail page serves the same, and rewriting `stp` 403s (the `oh=` signature covers it). Video posters come full-res 1080x1920 — which doubles as a perfect **image-vs-video classifier** (poster height >700 ⇒ video).

**Two card layouts:** normal is `…copy… / DOMAIN / headline / description / CTA`, but the domain line can be a full `HTTPS://SITE.COM/path` URL (regex needs optional `HTTPS?://` + `WWW.`), and **creator/partnership ads** (`<Creator> with <Brand>`) have **no domain line at all** — the link block just trails the copy. Fix: learn `(headline, description, cta)` triples from domain-bearing ads, then match them against the tail of the domain-less ones.

**Grouped ads** (`N ads use this creative and text` + `See summary details`) hide the link block from both the card and the detail page. Open the modal — Playwright `.click()` is intercepted by the video overlay, so dispatch `.click()` in page JS, then scroll every inner scrollable of `[role=dialog]`. **Never fall back to scraping `document.body`** when that fails: the page behind the modal is the full advertiser grid and you will attribute another brand's headline to the ad.

**Harness:** `nohup … &` from a Bash call is killed when the call returns — use `run_in_background: true`.

**Ready-to-run scripts** live in `scripts/` next to this file (validated July 2026 on a 119-ad and a 34-ad advertiser: zero empty bodies, zero missing headlines):
```bash
S=<this skill's base directory>/scripts
mk(){ echo "https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=$1&search_type=page&sort_data[direction]=desc&sort_data[mode]=total_impressions&view_all_page_id=$2"; }

python3 $S/harvest.py "$(mk all            <PAGE_ID>)" brand_all.json   # copy corpus + images
python3 $S/harvest.py "$(mk image_and_meme <PAGE_ID>)" brand_img.json   # static-ad id set
python3 $S/harvest.py "$(mk video          <PAGE_ID>)" brand_vid.json   # video ad id set
# any ads still missing a headline -> recover from the summary modal:
python3 $S/gapfill2.py brand_gap.json gap_ids.json
GAPFILL=brand_gap.json VIDSET=brand_vid.json \
  python3 $S/parse.py brand_all.json "Brand" brand-slug ./brand-ad-library brand_img.json
```
`harvest.py <url> <out.json> [max_idle]` scrolls + harvests + downloads images to `<out>_img/`. `parse.py <src.json> <Brand> <slug> <dest> [img_set.json]` writes `<slug>_ad-copy.txt` (unique-headline + unique-opener rollups, offer/starter-kit section, then full ad-by-ad copy), `<slug>_ads.json`, and `images/`. Merge multiple runs of the same filter before parsing — the grid caps, and a second pass picks up a few more. Finish with a labelled `montage images/*.jpg -tile 8x -geometry 170x302+4+4` contact sheet: it's the fastest way to answer "is there a creative for X?" and it caught a Starter Kit creative that copy-grepping alone had missed.

## Playbook A1 — VIDEO ads: get the files and the transcripts
`harvest.py` gets copy + statics. When the ask includes video, angles, or "what are they
actually saying", you need the videos, because **an account can run one primary text across
a thousand ads and put every angle in the creative.** (Real case: 1,041 live ads, ~4 unique
primary-text bodies, 447 unique video scripts.)

**The video URL is already in the DOM.** No GraphQL, no yt-dlp, no blob/MSE:
```js
[...el.querySelectorAll('video')].map(v => v.src)     // https://video-<dc>.xx.fbcdn.net/o1/v/t2/f2/m412/AQ...
[...el.querySelectorAll('video')].map(v => v.poster)
```
1. `python3 $S/vid_harvest.py` — reruns the card-root walker over the **`media_type=video`**
   grid and emits `{id, text, vsrc, poster}` per ad. Keeps the video URL joined to its Library ID.
2. Download with plain `curl -sL -A '<desktop UA>' -H 'Referer: https://www.facebook.com/'`,
   10 threads. ~2.4MB per 50s clip, zero auth. **Signed URLs expire — snapshot the JSON and
   download in the same session.**
3. `python3 $S/transcribe_fw.py <shard> <nshard>` — faster-whisper `base.en` int8, one JSON
   per clip so it is resumable. Run 3 shards x 3 threads. **Do NOT use mlx_whisper for a
   corpus**: on a loaded 16GB Mac it collapses 16x (196s/clip) while base.en does 14x
   realtime. Benchmarked near-identical output on ad voiceover. Needs `pip install faster-whisper` and ffmpeg.
4. `python3 $S/analyze_ads.py` — joins transcripts to ad metadata and prints recurring
   opening hooks, concept/angle frequency, and repeated selling sentences.

**Dedupe only on the transcript text.** FB mints a new asset id per upload, so the same
creative does not dedupe on URL, poster id, or md5 (522 of 533 files were byte-unique).

**Split the corpus by owner before drawing conclusions.** Parse the line directly above
`Sponsored`: `<Brand>` = brand-owned, `<Creator> with <Brand>` = branded-content
partnership. Publishers and creators say measurably different things, and the split is
usually the most useful cut in the whole dataset.


## Playbook A — Facebook Ad Library (browser harvest via the extension)
1. `navigate` to the search URL, `wait` ~4s, `screenshot`. Confirm right advertiser.
2. Read the result count shown at the top of the grid to know the coverage target.
3. Install a harvester + background scroll loop. Card root = walk text nodes for `/Library ID:\s*\d+/`, climb to smallest ancestor whose innerText contains `Sponsored` AND exactly one `Library ID:`. Dedup by Library ID.
4. Background loop (NOT awaited): `scrollBy(~550px)` + ~850ms waits; jiggle (`scrollTo(h-1600)`→`scrollTo(h)`) when near bottom to re-arm the loader; auto-stop after ~30 idle cycles. Fast `scrollTo(0,scrollHeight)` jumps STALL the virtualizer — go gentle. Poll `Object.keys(window.__AL).length`.
5. **Coverage reality:** the grid caps ~a few hundred unique cards even when the header says thousands. Sort is `total_impressions desc`, so you get the **top-N winners** (the long tail is 1-day rapid-test variants recycling the same copy). Parse `"N ads use this creative and text"` to report true coverage. For exhaustive long-tail, the official Ad Library API is the tool, not browser scroll — offer it.
6. **Images:** cross-origin `fetch()` to `scontent.fbcdn.net` SUCCEEDS with CORS. Fetch each into a Uint8Array and build a **store-mode ZIP** (CRC32 + local headers + central dir + EOCD, no lib) in-browser, then download the one zip. `unzip` into `images/`.
7. **Copy (MB-scale):** build the MD in-browser from `window.__AL`; if the download is blocked, stash the MD in `localStorage` from the loaded tab and download it from a fresh tab. Copy = text after `\nSponsored`, cut at earliest of `/\nBRAND\.COM/i`, `/\n0:00 \/ 0:00/`, `/Library ID:/`. **Long advertorials (30k+ chars) are real single ads — keep them whole.** Note: FB page scripts tamper with `Object.values` → use `Object.keys(x).map(k=>x[k])`.

## Playbook B — gethookd / any ad-intel SPA (HIT THE API)
1. `read_network_requests({tabId})` (call once), then RELOAD the board, then `read_network_requests({urlPattern:'api'})`. Find the board-data endpoint.
2. gethookd: `GET /api/get-shared-board/<boardId>?signature=<sig>&page=N&per_page=12` → Laravel paginator `{ads:{data:[...],total,last_page,per_page},folder:{title}}`. Loop `page=1..last_page`, same-origin `fetch()`, concat `ads.data`.
3. Per-ad copy fields: `title` (headline), `body` (FULL long-form copy, up to ~37k chars), `link_description`, `caption`, `cta_text`/`cta_type`, `display_format`, `platform`, `landing_page` (**group brands by its domain** — no brand-name field; `brand_id` is just a number), `external_id` (the real FB Ad Library ID), `start_date`/`end_date`/`days_active`, `used_count`/`saved_count`/`likes`/`winning_score`, `impressions_text`.
4. Build the MD in-browser, `<a download>` it (first download on a freshly-reloaded tab isn't blocked). 300 ads + full MD in ONE js call (~6s).
5. **Images (if asked):** gethookd media are **clean public paths, no query string** — `static-gp.gethookd.ai/media/ads_media/<adId>/media-*.jpg` (in `item.media[].path`/`url`; the `.jpg` may actually be a PNG). In-browser `fetch()` of them FAILS CORS, but they `curl` fine from the shell (CORS is browser-only, needs a normal UA). So return the clean paths and `curl` server-side into `images/`.
6. Other SPAs: same shape — find the paginated JSON call, replicate it, map its copy fields. When unsure which field holds the copy, dump one item with long strings truncated to see the schema.

## Output format (the MD)
```
# <Board/Brand> — Ad Copy[/Creative] Extract
**Source:** <url>  |  **Captured:** <date>  |  <coverage note: N of ~M, sort/order>
## <Pages|Brands> table  (name · #ads · role/domain)
## Ad copy (grouped by page/brand-domain)
### <group> — N ads
#### #NNN — <headline>   *<fmt · platform · dates · Nd · CTA · FB ad id>*
*Image:* `images/<slug>_NNN_<id>.jpg`   (omit if copy-only)
> full body copy, verbatim
_Link description:_ ...   _Caption:_ ...   (if present)
```
Number ads `#001…` in a stable order so image filenames (`<slug>_NNN_<id>.jpg`) line up with the MD. QA at the end: 0 empty bodies, every image ref resolves, longest advertorials intact.

## Honesty
State real coverage (e.g. "top 222 of ~3,900 by impressions" or "all 300 on the board"). Never imply completeness you didn't get. Skip images entirely if the user asked for copy only.
