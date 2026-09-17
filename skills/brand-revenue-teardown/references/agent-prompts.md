# Agent prompts (fill <BRAND>, <DOMAIN>, <DIR>, <SKILL>, caps)

`<DIR>` = the research folder (e.g. ~/research/<brand>-intel). `<SKILL>` = this skill's absolute base directory. Subagents cannot see the skill unless you pass absolute paths.

Launch all six in ONE message with the Agent tool (`run_in_background: true`, `subagent_type: general-purpose`). Paste the constraints block into every prompt, and tell each agent to read `<SKILL>/references/scraping-recipes.md` for its section.

## Standing constraints block (paste into every prompt)
```
First read the seeds: cat <DIR>/SEEDS.md, then the matching section of <SKILL>/references/scraping-recipes.md
- Write findings to <DIR>/<FILE>.md (NOT /tmp, which can be wiped); raw files under <DIR>/raw/<category>/. Save as you go.
- Cite EVERY claim with the exact URL you loaded. Never invent. Label INFERRED (show arithmetic), ASSUMPTION (no source) and UNVERIFIED. Report NULLs honestly and say whether a miss was a block, a cap or a true absence.
- Watch name collisions listed in SEEDS.md; verify any entity by address, product or officer before attributing it.
- WebSearch is a shared session pool: use at most <N> WebSearch calls. Prefer direct URLs and APIs. curl_cffi with impersonate="chrome124" gets past most Cloudflare checks. Avoid the Wayback Machine (it rate-limits all agents on one IP). macOS has no `timeout` command; don't suppress stderr while diagnosing.
- <Only for non-browser agents:> Do NOT use the Claude in Chrome browser tools; another agent owns the browser. Use headless Playwright if you need a browser.
- Return (final message, max ~500 words): numbers first, each with URL and date, then NULLs.
```

## 1. Press + founder posts (file: press-founders.md, WebSearch cap 25)
Read every article in the seeds plus anything else: local trade press for the home market, US trade press (NOSH, BevNET, Food Navigator USA, Grocery Dive, Modern Retail), founder-story outlets. Podcasts via iTunes Search API (`itunes.apple.com/search?term=<q>&entity=podcastEpisode&country=US` and the home country). YouTube via `ytInitialData` on `/results?search_query=`, transcripts with youtube-transcript-api. Founder LinkedIn POSTS: curl a linkedin.com/posts/... URL with a browser UA and read og:description (DuckDuckGo POST search finds post URLs). Extract verbatim with URL + date: revenue, units, "sold out", customers, doors and retailer names, raise amount, investors, prices, manufacturing, team size, launch dates. Separate founder claims from third-party facts. Founder backgrounds (prior companies, exits). Flag any "intel" site that looks templated.

## 2. Funding + filings (file: funding-corporate.md, cap 20)
1. SEC EDGAR full-text: `efts.sec.gov/LATEST/search-index?q=%22<BRAND>%22` and `%22<BRAND>%20SPV%22`, all forms and forms=D; send a User-Agent with name + email. Pull primary_doc.xml of any hit (amount sold, investor count, first sale date, related persons).
2. US entity: NY DOS public inquiry API (reveals Delaware formation date), Florida Sunbiz (curl_cffi impersonate="safari17_0"), OpenCorporates if not captcha-gated.
3. Home-country registry (AU: ABN Lookup; UK: Companies House; NZ: Companies Office).
4. Investors: each named investor's site for stated first-cheque range and portfolio listing; Form Ds for their SPVs.
5. Trademarks: USPTO tmsearch (POST works; TSDR documents 403), home-country register. Goods classes = roadmap; suspensions + earlier similar marks = risk.
6. ImportYeti `GET /api/search?q=<BRAND>` (curl_cffi): consignee address, supplier, goods, weight. Check the address against investor offices.
7. crt.sh for the domain (first cert date, subdomains such as au./trk.), WHOIS creation date.
8. Label copy on product images in `/products.json` ("Manufactured for ...", kosher marks, origin).
Return: amount raised with confidence, entity names and dates, investor cheque ranges, trademark status, supply chain, NULLs.

## 3. Ads (files: ads.md, ads.csv, cap 10)
Read the `adlib-page-resolver` skill (in this plugin) and the "Ads" section of `<SKILL>/references/scraping-recipes.md` first. Headless Playwright, no login. Scripts: `<SKILL>/scripts/ads/`.
1. Meta Ad Library: resolve the brand's page id (the advertiser typeahead works when keyword search is buried), then pull ALL ads (active_status=all, country=ALL) and active counts for each market. Record count from the payload, not the scroll. Run a control page through the same script. Search handle, domain and "<brand> <retailer>" for partnership ads.
2. Google Ads Transparency: SearchCreatives for each domain × region, with a control domain.
3. TikTok Creative Center top ads (opt-in, weak) and the EU library (expected empty outside Europe).
4. Shopify `webPixelsConfigList` on each storefront: which ad pixels exist.
If ads exist: per-ad start date, format, copy, CTA, landing page, days live, monthly launch curve, top angles with counts. If zero: prove it with controls and say what the zero cannot cover.

## 4. Storefront + marketplaces (file: storefront-retail.md, cap 20)
1. Platform and stores: `/meta.json`, `/products.json?limit=250`, `/pages.json` on each regional store (au., us. subdomains). Hidden B2B SKUs give wholesale price, case pack and distributor. Created dates date the store.
2. Stack from HTML and `webPixelsConfigList` (email, subscriptions, reviews, A/B testing, store locator).
3. Reviews: find the app (Judge.me, Okendo, Yotpo, Loox, Stamped) and pull totals + monthly counts; else note the absence.
4. Marketplaces: Amazon (ASIN, BSR, "bought in past month"), TikTok Shop PDP sold_count, Walmart, Instacart, home-country grocers' search APIs (Woolworths `apis/ui/Search/products`), each retailer's online shop price.
5. Store locator (Stockist, Storemapper, Destini): pull every door, count by retailer and state. Save the JSON.
6. Traffic proxies if reachable (Similarweb, Tranco).
Then a first-pass revenue bracket per method with arithmetic (reviews, doors × velocity, Amazon, TikTok Shop), clearly INFERRED.

## 5. Social + LinkedIn (file: social-linkedin.md, cap 20; the ONLY browser agent)
If the Claude in Chrome extension is connected: create your own tab, close it at the end, read only (never follow, like or message). Without it, use the no-login curl routes in scraping-recipes.md (LinkedIn posts and profiles return ld+json; TikTok profile and video JSON).
1. TikTok: profile JSON (followers, likes, videos, `ttSeller`), every video's plays/likes/shares with dates, the viral video(s) and a comment read (count themes, don't quote one). Creator/affiliate video count via search + hashtag grid (note caps).
2. Instagram (followers, reels with views), Facebook, YouTube, X.
3. LinkedIn: company page (followers, size, associated members with titles and locations), founder profiles and their last ~15 posts (numbers only), jobs tab.
4. Hiring: careers page, Ashby/Lever/Greenhouse/Workable slugs, Seek/Indeed (often bot-walled: NULL, not zero).
5. Community: Reddit via api.pullpush.io, review sites, X search.
6. Google Trends via the in-page API (a Trends-overlay Chrome extension may spend credits when the UI loads).
Do not write employees' personal contact details.

## 6. Retail depth (files: retail.md, retail/doors.csv, cap 15)
Owns: "How many stores? How much in retail? How many units?"
1. Door count = enumerate, never estimate. Start from the storefront agent's locator JSON, then verify store by store on each retailer's own online shop (Sprouts and other Instacart-powered retailers: guest GraphQL, see `<SKILL>/scripts/door_check_sprouts.py`). Record listed / available / stock level / price per store. Flag locator rows that are distribution centres or unopened stores.
2. Other retailers: search each plausible grocer's product API; say which were uncheckable.
3. Distribution: distributor named in B2B SKUs, Faire/RangeMe, trade-show exhibitor lists.
4. Units: record exactly what each retail surface exposes (usually nothing). Pipeline fill + sell-through brackets with SOURCED u/s/w benchmarks (see `<SKILL>/references/revenue-model.md`), low/base/high, brand $ and shelf $.
5. Leave a re-runnable checker and a timestamped baseline CSV; explain how a re-run turns stock flips into a sell-through signal.
