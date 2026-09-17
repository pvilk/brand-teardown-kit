---
name: brand-revenue-teardown
description: Estimate how an early-stage DTC / CPG brand is actually performing from public sources only - revenue run-rate by channel (retail, TikTok Shop, DTC), store count verified store by store, units, funding raised, ads, social traction, team - and ship it as a shareable report. Use when the user asks "how is <brand> performing", "how much revenue is <brand> doing", "how many stores are they in", "how many units are they selling", "how much did they raise", "deep research this brand", or runs /brand-teardown. Brand-agnostic. Built on a real teardown of Drizzy, a squeeze-bottle peanut butter brand (Sept 2026).
---

# Brand revenue teardown

Young consumer brands leave almost no filings and founders never publish revenue. The number still exists in the public record, split across channels. **Build revenue channel by channel from hard signals, show every input, and keep brand dollars apart from shelf dollars.** That is what stops a model from underselling (or overselling) a brand.

This skill's files live in the **Base directory** shown when it loads. Call it `$SKILL` below and pass absolute paths to subagents.
- `$SKILL/references/agent-prompts.md`: the six research-agent prompts
- `$SKILL/references/revenue-model.md`: formulas, sourced benchmarks, the "why estimates look bigger" section
- `$SKILL/references/scraping-recipes.md`: endpoints and traps for every source
- `$SKILL/references/report-example.html`: the finished Drizzy report, as the output template
- `$SKILL/scripts/`: store locator puller, Sprouts store-by-store checker, run comparer, ad checks

Setup once: `pip install curl_cffi playwright && playwright install chromium`.

## Step 0: pin the brand (do it yourself, 2 minutes)
- Find the real storefront domain. Short brand domains are often parked: a ~114-byte page with `location.href="/lander"` is a parked domain. Search "<brand> <category> founder".
- Create `~/research/<brand>-intel/` (any folder works) and write `SEEDS.md`: domain, founders, investors, launch dates, retailers, known articles, and **name collisions** (Drizzy the peanut butter vs Drizly the delivery app vs Drake's nickname). Every agent reads it first.

## Step 1: TikTok Shop sales (the one real sales number)
Read `$SKILL/references/scraping-recipes.md` section "TikTok Shop". Two routes:
- **Free:** the public TikTok Shop product page returns an all-time `sold_count` to plain curl. One reading gives sales to date; a reading a week later gives a weekly run-rate.
- **With a TikTok Shop analytics tool** (Euka, Kalodata, FastMoss): 30-day GMV, units and a daily sales curve for any seller. The first non-zero day is the shop's launch date. With Euka, first call `list_accessible_brands` to get your own `brandId`; every Social Intelligence call needs it, and your brand's TikTok Shop region sets the market searched.
Check whether sales come from affiliate videos; if none are credited, sales come from shop ads, shop search or the brand's own posts.

## Step 2: fan out six agents in parallel (one message)
Use the prompts in `$SKILL/references/agent-prompts.md`, each with the standing constraints block. Give only **one** agent the Chrome browser (social/LinkedIn) if you have the Claude in Chrome extension; the others use headless Playwright. WebSearch is capped per session and shared by every agent, so give each an explicit cap.

| Agent | Output file | Must return |
|---|---|---|
| Press + founder posts | `press-founders.md` | Every disclosed number (stores, sell-outs, raise, units), founder backgrounds, what was not found |
| Funding + filings | `funding-corporate.md` | SPV Form Ds, company formation dates, investor cheque ranges, import records, trademarks |
| Ads | `ads.md` | Ad counts with controls, or a proven zero; ad pixels on each store |
| Storefront + marketplaces | `storefront-retail.md` | Platform, hidden B2B products (wholesale price, distributor), prices, reviews, marketplaces, store-locator door list |
| Social + LinkedIn | `social-linkedin.md` | Followers, per-video views, the viral moment, team size, hiring |
| Retail depth | `retail.md`, `retail/doors.csv` | Store-by-store verification, shelf price, sourced sales benchmarks, unit brackets, re-runnable checker |

When an agent reports, **spot-check one load-bearing claim yourself** (re-fetch the Form D, recount the locator JSON, re-read the post) and pass cross-agent inputs along (wholesale price and door list go to the retail agent).

## Step 3: build the revenue table
Formulas and benchmarks: `$SKILL/references/revenue-model.md`.

| Channel | What it rests on | Low | Base | High |
|---|---|---|---|---|
| Retailer | verified stores × sourced units/store/week × wholesale × 52 | | | |
| TikTok Shop | actual sales annualised; low case assumes decay | | | |
| Brand's own site | reviews or customer claim × orders × order value (label weak) | | | |
| Total | | | | |

Always add:
- **Why other estimates look bigger:** shelf dollars are about 2× brand dollars; gross vs net (free fill, trade spend, fees); the sales-per-store swing in dollars.
- **Revenue to date** (one-time stocking order plus channel sales so far).
- A **launch-promo ceiling** if a sweepstakes or price cut is running.

## Step 4: deliver
- **In chat first:** the number, the range, the store count, the raise estimate, one line each on ads and team. Then: hardest call, what you rejected, what you are least confident about.
- **Report:** use `$SKILL/references/report-example.html` as the template. If the Artifact tool is available, publish it there so it can be shared; otherwise save a standalone HTML file and open it.
- **Leave a re-runnable tracker** (below) so sell-through can be read over time.

## Scripts
- `scripts/stockist_all.py <map_id> <brand_site_url> <overview.json> <out.json>`: every door in a Stockist store locator. The `map_xxxxxxxx` id is in the locator page HTML; save the overview from `https://stockist.co/api/v1/<map_id>/locations/overview.js` first. **Verify the list against the retailer:** Drizzy's 500 included 4 distribution centres and 4 unopened stores (483 real).
- `scripts/door_check_sprouts.py`: listing, stock level, availability score and shelf price in every Sprouts store, from Sprouts' Instacart-powered shop (guest access, no login). `PRODUCT_ID=<id> STOCKIST_FILE=<doors.json> INTEL_DIR=<folder> python3 door_check_sprouts.py --census`. Re-run the same stores with `--reuse-locations <..._locations.json>` (~11 min for ~500 stores). Other Instacart-powered retailers likely work with a different retailer slug; untested.
- `scripts/compare_runs.py OLD.csv NEW.csv`: listed/delisted flips, stock changes, availability-score drift. Run after a promotion ends and again two weeks later.
- `scripts/ads/meta_ads_harvest.py "<Ad Library view_all_page_id URL>" out.json`: every ad record plus Meta's own result count.
- `scripts/ads/google_ads_check.py --brand X --domain x.com --region US`: Google ads with a control domain.
- `scripts/ads/tiktok_top_ads.py --term x --region US`: TikTok Creative Center top ads with a control term.
- To find a brand's Meta page id first, use the `adlib-page-resolver` skill in this plugin.
- **When the brand runs ads, pull the whole library:** the `ad-library-extractor` skill (every Meta ad's full copy, images, optional video downloads and transcripts) and the `google-ads-transparency-extractor` skill (every Google/YouTube creative, run dates, playable video files). The count scripts above only prove whether ads exist.

## Traps that cost the original run time
- **Placeholder "intel" sites:** coherecommerce.com shows fake funding ("$1.7M Round A") and review text copied across brands. Never cite it.
- **Founder store counts drift** ("480+", "nearly 500", "500+"). Count and verify; report the verified number.
- **A zero is a finding only with a control** (ads, Reddit, Amazon). A capped or blocked search is unknown, not zero.
- **TikTok `isAd: true`** marks any shoppable post, not only paid ones.
- **Instagram reels with low likes per view** look paid; the Meta Ad Library can prove they are not.
- **Headless Chrome screenshots can't go below 500px wide**; use Playwright's viewport setting for phone checks.
- **Chrome extensions that overlay Google Trends** may spend their own credits when the page loads; use the Trends API from the page instead.
