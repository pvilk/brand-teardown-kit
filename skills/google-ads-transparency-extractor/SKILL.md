---
name: google-ads-transparency-extractor
description: Pull a brand's ENTIRE Google Ads library (every creative, and the actual video files) out of the Google Ads Transparency Center. Use when the user gives an adstransparency.google.com link or names a brand/domain and says "scrape this brand's whole library", "find all the videos they're running and download them", "what Google/YouTube ads is X running", "get me their landscape ads", or "do this one too". Handles the parts that break every naive attempt - the UI is virtualized and caps at ~120 cards, the RPC needs no auth but ONLY from outside a browser, video takes a two-hop resolve, and yt-dlp's defaults produce mp4s that will not play. Brand-agnostic. Saves to a project folder.
---

# google-ads-transparency-extractor

Full Google/YouTube ad library for any brand → a project folder: every creative's metadata, a
per-video manifest with run dates, and **playable** mp4s. Validated Sept 2026 on a nicotine-pouch advertiser
(576 creatives, 447 video, 341 unique videos, 10 landscape) and a wallet brand
(**2,261 creatives over 23 pages**, 1,678 video, 8 advertiser accounts on the one domain).

Sibling: `ad-library-extractor` (Meta). Needs `yt-dlp` and `ffmpeg` for video downloads.

## Do not open the browser

The web UI **cannot** give you the library. It virtualizes the grid and plateaus at ~80–120 DOM cards
however you scroll, while the header claims ~500. Scroll loops, "See more results" clicking and DOM
harvesting all dead-end. The backing RPC has no such limit.

**The counter-intuitive bit:** the RPC needs no cookie, no API key and no XSRF token — *but only from
outside a browser*. Called from inside the page (`javascript_tool`) it fails with
`XsrfException: XSRF token is MISSING`. Do not go hunting for the token. Leave the browser, use bash.

Use the browser for exactly one thing: eyeballing a creative to confirm what you scraped is right.

## The pipeline

```bash
S=<this skill's base directory>/scripts
D=./<brand>-google-ads; mkdir -p $D

python3 $S/fetch_creatives.py <domain|AR-id> US $D   # 1. every creative + MEASURED format enum
python3 $S/resolve_videos.py $D                      # 2. two-hop -> youtube_ids.txt + manifests
$S/probe_aspect.sh $D                                # 3. (optional) bucket by TRUE aspect ratio
$S/download.sh $D youtube_ids.txt videos             # 4. playable H.264+AAC, resumable, verified
```

Aspect-filtered download: `$S/download.sh $D ids_16x9_landscape.txt landscape_16x9`.

Ask up front only what changes the work: **all videos or one aspect ratio?** Show the format/advertiser
breakdown from step 1 before committing to a full download, and confirm with the user.

## Domain vs advertiser

`fetch_creatives.py` takes either. Prefer the **domain** — it spans every advertiser account pointing
there, and a brand can run several. The script prints the advertiser breakdown; if one name dominates
you can pin to its `AR…` id. **Never assume `rows[0]`'s advertiser is the brand** — competitors bid on
brand terms, and a well-known scraper shipped a bug calling hubspot.com "Authsignal Limited" that way.
Live example: one wallet brand's domain returned **8 advertisers**; the brand's own account held 2,253 of 2,261 and the
other 7 held 1–2 each. Rank by ad count and prefer the name matching the domain — don't take the first row.
**The brand's own account is often its LEGAL name, not the brand name:** davidprotein.com's real ads run under
"Linus Technology, Inc." (25 of 48 rows; the other 23 were unrelated advertisers). Confirm the legal entity from the
trademark owner (USPTO/Justia) or the site's terms page before discarding a non-matching advertiser name.

## Gotchas that WILL bite

- **A wrong field shape returns HTTP 200 with `{}`.** Silent, and identical to "this advertiser has no
  ads". The only informative error is `BadRequestException: Trouble converting f.req`. `fetch_creatives.py`
  prints a loud warning on a zero result — always sanity-check the count against the web UI.
- **429 comes back as an HTML page, not JSON**, so a naive `json.loads` raises
  `Expecting value: line 1 column 1` — which *also* looks like "no ads". `gat_lib` raises `RateLimited`
  instead and backs off 30/60/90s. If it trips: wait 10–30 min, lower `page_size`, or change egress IP.
  A heavy session (600 creatives + 450 preview fetches) is enough to get throttled.
- **The format enum is contested online and three public scrapers disagree.** Do not hardcode it.
  Step 1 prints `format code × content shape`; the code paired with `preview_url` is video. Measured on
  two unrelated advertisers: `3`=video, `1`/`2`=image (two independent advertisers agree). Still cheap to
  verify — step 1 prints it every run.
- **There is no server-side video filter.** The UI's `?format=VIDEO` is a page param, not an RPC field.
  Over-fetch and filter locally.
- **`uiFeatures` in the preview URL** biases the response toward a UI render instead of the video
  payload — strip it, keep the original as fallback. The payload is **double**-unicode-escaped.
- Region code = `2000 + ISO-3166-1 numeric` (US=2840). Wrong region returns zero rows, silently.
- **Pagination is stable at depth** — validated to 23 pages / 2,261 creatives with no cursor drift or
  duplicate bleed. Public scrapers only ever tested shallow; one claimed the cursor was session-bound.
  It isn't. `max_pages` defaults to 60 (≈6,000 creatives); raise it for a very large advertiser.

## Aspect ratio: measure pixels, never trust the name

Advertisers label some creatives `16x9` / `9x16` in the title, and it is tempting to filter on that.
**It is partial and it will burn you:** on one advertiser, title-matching found **4 of 10** landscape
videos and missed all three 4K ones. `probe_aspect.sh` runs a metadata-only yt-dlp probe (no video data)
and buckets on true `width/height`, writing `ids_<aspect>.txt` batch files. It also prints the
title-vs-pixel cross-check so you can show the miss rate.

Expect vertical dominance — this advertiser ran 278 of 341 at 9:16. If the user wants landscape, say the
number early; "3% of the library is 16:9" changes the plan.

## Playability — the failure the user will notice

`yt-dlp`'s `-S "codec:avc1"` is a **preference, not a filter**. It silently falls back to AV1/VP9 +
Opus, and `--merge-output-format mp4` wraps **Opus in an .mp4** that QuickTime refuses to open. A first
pass produced 93/108 unplayable files that looked perfect in `ls`. `download.sh` forces a hard `-f`
chain (`avc1` + `mp4a`), re-encodes audio to AAC with `-c:v copy` (fast, lossless video), adds
`+faststart`, and **verifies codec AND resolution** at the end — a codec-only check happily passes a
360p fallback.

- **403 mid-download** = a stale `.part` resuming at an offset the signed URL rejects → delete `.part`,
  re-run with `--no-continue`. `download.sh` does this each pass.
- **403 on every HD itag** = try other clients; `mweb` often serves when `default` won't, but may expose
  *only* format 18 (360p) — so check what you actually got. `download.sh` walks
  `mweb → android_vr → tv_embedded → web_embedded` for stragglers.
- To learn whether HD is genuinely reachable, force `-f "136+140"` with **no fallback** and read the error.

## Shell traps (macOS/zsh)

- An unmatched glob **aborts the whole command** in zsh: `rm -f a/*.json a/*.webp` deletes nothing if
  either pattern misses. Use `find … -delete`.
- **Video ids can start with `-` or `_`** (`-7KrhZTmKuo`, `_gwTEzLZ8rY`): `grep "$id"` reads it as a flag
  and `cut -d_ -f1` returns empty. Use `grep -F --` or `cut -c1-11` on an `%(id)s`-prefixed filename.
- `timeout` does not exist by default. `nohup … &` from a Bash call dies when the call returns — use
  `run_in_background: true`.
- The claude-in-chrome extension **redacts** hrefs, `location.pathname` and token-shaped values
  (`BLOCKED: Cookie/query string data` / `Sensitive key`). If you must read the DOM, regex out bare id
  tokens, never whole URLs. This is a safety guard — do not try to defeat it, use the RPC instead.

## Outputs

| File | What |
|---|---|
| `videos/` (or `landscape_16x9/`) | the mp4s, H.264+AAC, verified |
| `manifest_videos.csv` | one row per unique video — reuse count, first/last shown |
| `manifest_creatives.csv` | one row per creative — video id, run dates, transparency deep link |
| `creatives_raw.json` | raw RPC rows (statics included) |
| `resolved.json` | resolution results incl. failures |
| `ids_<aspect>.txt` | per-aspect batch files from step 3 |

Creatives **reuse** videos heavily (442 creatives → 341 videos); `manifest_videos.csv` is the one to
open, and `creative_count` + run window is a decent proxy for which asset is their workhorse.

Unresolved creatives are almost always statics. A *video-format* creative that still fails on both
`content.js` and `LookupService/GetCreativeById` has no archived video — report it, don't chase it.
