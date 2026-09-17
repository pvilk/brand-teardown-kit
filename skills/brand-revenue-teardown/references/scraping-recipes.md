# Scraping recipes and traps, by source

Everything here was used on the Drizzy teardown (Sept 2026). Endpoints change; if one fails, say so and try the fallback rather than guessing. Default HTTP client: `curl_cffi` (`requests.Session(impersonate="chrome124")`). Never bypass a login or a captcha; if one appears, stop on that source and report it.

## Search when WebSearch runs out
- WebSearch is capped per session and shared by all subagents. Six agents can exhaust it in one pass, so cap each agent.
- **DuckDuckGo HTML via POST** works: `requests.post('https://html.duckduckgo.com/html/', data={'q': query}, impersonate='chrome124')`, parse `a.result__a`, unquote the `uddg=` target. GET is dead. Space queries ~25s apart or you get 202 with zero results.
- Vertical searches that need no key: YouTube (`/results?search_query=` then regex `var ytInitialData = (\{.*?\});</script>`), Apple Podcasts (`https://itunes.apple.com/search?term=<q>&entity=podcastEpisode&country=US`).

## TikTok Shop
- **Public product page** `https://www.tiktok.com/shop/pdp/<slug>/<product_id>` via plain curl with a Chrome user agent returns `sold_count` (product and shop), review count and score, price. Get `product_id` from the `extra` JSON of a type-35 anchor on any shoppable video. Snapshot it on two dates for a run-rate.
- **Profile** `https://www.tiktok.com/@<handle>`: `<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">` → `webapp.user-detail.userInfo` (followers, likes, video count, `ttSeller: true` if a shop exists).
- **With Euka (MCP):** `list_social_intelligence_brands` (query = brand, 30-day max range) → seller id and 30-day GMV; `get_social_intelligence_brand` → `gmvTrend` daily array; `get_social_intelligence_product` → list price vs average selling price; `discover_social_intelligence_videos` (sellerIds, sortBy revenue) → which videos sell. Retry with `limit` 20 if a call aborts. Watch look-alike seller names. Kalodata and FastMoss offer similar data in their UIs.
- GMV is gross of TikTok fees, affiliate commissions and seller-funded coupons.

## Brand storefront (Shopify)
- `/meta.json` (shop name, city, currency), `/products.json?limit=250`, `/pages.json`. Created dates date the store. Check regional stores (`au.`, `us.` subdomains).
- **Hidden B2B products** in products.json name the distributor and wholesale price: "KeHE Case Pack (6 units) $32.10" = $5.35/unit, case of 6.
- Homepage HTML `webPixelsConfigList`: Meta pixel (`"pixel_type":"facebook_pixel"`, `facebookCapiEnabled`), Klaviyo, TikTok and Google pixels. No ad pixels = not set up to measure paid social.
- Not what they look like: `cart/add.js` with qty 99999 returning "Only 50 items were added" is a per-order cap, not stock. A Judge.me div with `data-auto-install='false'` plus a 404 from the widget API = no review app.
- Label images in products.json: "Manufactured for <entity>, <city>" names the legal entity and means a co-packer; origin claims and kosher marks.

## Store locator door count (Stockist)
1. Grep the locator page for `map_xxxxxxxx` (`data-stockist-widget-tag`).
2. `https://stockist.co/api/v1/<map>/locations/overview.js` → `{"i":["<geohash>:",...]}`. `len(i)` is the door count.
3. Names and addresses: `.../locations/search?latitude=..&longitude=..&distance=15` with `Referer: <brand site>`. `scripts/stockist_all.py` tiles these until every overview point is matched.
- **Silent throttle:** HTTP 429 with JSON `{"error":"Your computer or network has made too many requests"}`. Code that does `r.json().get("locations", [])` reads it as "no stores". A fast pass returned 343 of 501. Reconcile against the overview count and re-query gaps slowly.
- **Locators can be the retailer's raw location file:** Drizzy's 500 "Sprouts stores" included 4 distribution centres and 4 unopened stores, and missed 7 live ones.

## Retailer store-by-store check
**Sprouts (Instacart-powered `shop.sprouts.com`), guest access:**
- Start a session: GET `https://shop.sprouts.com/store/sprouts/storefront` (sets cookies). ~1 request/second for ~1,100 requests drew no captcha.
- GraphQL GETs with persisted-query hashes (see `scripts/door_check_sprouts.py`): `AvailableInStoreRetailerServices` (stores near a ZIP), `ShopCollectionScoped` (shop id per store, coordinates required), `Items` with id `items_<retailerLocationId>-<productId>` (stock level, availability score, price).
- `Items` takes ONE store per call. Price needs that store's in-store shop id plus any valid zone id (943 worked nationally).
- `item = null` = not in that store's catalog, not proof of an empty shelf. Query a control product at the same store before calling it a gap.
- Sprouts' pricing policy: online prices "generally reflect the everyday in-store prices". Purchase counts are hidden for guests.
- If every call returns PersistedQueryNotFound, re-capture hashes from a product page's network log in headless Playwright.

**Harris Farm (Australia, Shopify):** product page `data-available-locations` (stocked now) vs `data-location-prices` (price file, wider); store names in the theme asset `location-manager.js`. The public storefront token (`<meta name="shopify-storefront-token">`) returns `totalInventory`, but the site seeds SKUs near 10,000, so only the direction over time means anything.

**Shelf prices without a browser:** Instacart product pages (`instacart.com/products/<id>`) include current and original price. Woolworths: POST `/apis/ui/Search/products` after a homepage GET, with a control query ("peanut butter" = 178) so a 0 means absent. Coles: the page JSON's `noOfResults` plus `autoCorrections` to another word = not stocked.

## Ads
**Meta Ad Library:**
- Find the page id: keyword search ranks affiliates first, so pick by name; else query the domain; else the Ad Library's own typeahead (`adlib-page-resolver` skill). Confirm with the About tab (IG handle, page created date, manager country).
- The authoritative zero is Meta's payload `search_results_connection.count: 0` on `view_all_page_id=<id>&active_status=all&country=ALL`, not a count of cards on screen (`scripts/ads/meta_ads_harvest.py`).
- Outside the EU, ended commercial ads stay in the library (verified back ~12 months), so `active_status=all` = 0 means no ads or boosted posts in that period.
- Always run a control page with known ads through the same script. Also search the handle and domain as keywords to catch "Creator with Brand" partnership ads. Organic paid-partnership posts never run as ads are invisible to every library.

**Google Ads Transparency Center:** plain-Python RPC, no cookie or key (`scripts/ads/gat_lib.py`, `google_ads_check.py`). A wrong request shape returns `{}` silently, so always check a control domain. The web UI shows a captcha to headless browsers.

**TikTok:** Creative Center Top Ads works logged out, but the URL `keyword=` parameter is ignored; type into the box after removing the promo modal (`scripts/ads/tiktok_top_ads.py`). It only lists opted-in, high-performing ads: weak evidence. library.tiktok.com covers the EU/UK/Switzerland only.

## Social and founders
- **TikTok videos:** `tiktok.com/@<handle>/video/<id>` via curl → `webapp.video-detail.itemInfo.itemStruct` (plays, likes, shares, saves, `isECVideo`). Video id → date: `id >> 32` = unix seconds. The profile's video list needs a browser grid scroll. Comments: from a tiktok.com tab, `fetch('/api/comment/list/?aid=1988&aweme_id=<id>&count=50&cursor=N')`. Search API gives page 1 then 403s, so creator counts are a floor.
- **Trap:** `isAd: true` is set on shoppable/affiliate videos, not only paid ones.
- **Instagram:** shortcode → date: decode base64 (`A-Za-z0-9-_`) to media id, `ms = (id >> 23) + 1314220021721`. The profile API 429s quickly; the grid stalls after ~48 reels. `/p/<shortcode>/embed/captioned/` exposes every carousel slide image URL.
- **LinkedIn without login:** post URLs `linkedin.com/posts/...-activity-<id>-...` return full text, date and comments as `<script type="application/ld+json">` to curl_cffi. Country-subdomain profiles (`au.linkedin.com/in/<vanity>`) often return recent posts; numeric-id profile URLs return HTTP 999. Activity id → date: `(id >> 22) / 1000` = unix seconds. Company pages show followers and "N employees", which includes investors who list the company; read titles before calling it headcount.
- **Facebook page:** vanity URLs can say "content isn't available" while the page exists as `profile.php?id=`; find it by searching the Instagram handle.
- **Google Trends:** from a trends.google.com tab, `fetch('/trends/api/explore?req=...')` then `/trends/api/widgetdata/multiline?req=<request>&token=<token>` (strip the `)]}'` prefix).
- **Reddit:** `https://api.pullpush.io/reddit/search/comment/?q=<q>&size=100`; 429 after ~10 fast queries.
- **Hiring:** Ashby/Lever/Greenhouse/Workable slug 404s are clean zeros. Seek, Indeed and Wellfound serve bot checks: unknown, not zero.
- **Paywalled news** (e.g. News Corp Australia) still exposes og:title/description; community outlets often rewrite those stories with the numbers.

## Funding, companies, supply chain
- **SEC EDGAR full text:** `https://efts.sec.gov/LATEST/search-index?q=%22<Brand>%22` and `%22<Brand>%20SPV%22`, all forms and `&forms=D`. Send a User-Agent with a name and email or you get 403. Syndicate SPVs (Sydecar, AngelList) file Form Ds named "<Brand> SPV <Mon YYYY>, a Series of <master LLC>" even when the company files nothing. Read `primary_doc.xml` for amount sold, investor count and first sale date.
- **Investor cheque ranges:** the lead investor's own site often states a first-cheque range. Combine it with SPV floors for a band; never state a point figure.
- **US company:** Delaware search has a captcha, but the New York Department of State public inquiry (`apps.dos.ny.gov/publicInquiry/`, JSON endpoints behind the search) shows a Delaware corporation's formation date if it registered in NY. Florida Sunbiz loads with curl_cffi `impersonate="safari17_0"`.
- **Australia:** ABN Lookup `https://abr.business.gov.au/ABN/View?abn=<abn>` (registration date, postcode).
- **Trademarks:** USPTO `tmsearch.uspto.gov` search works; TSDR document bodies return 403. A suspended application plus an earlier similar mark in the same class = brand-name risk. Goods classes show planned product lines.
- **Import records:** ImportYeti `GET https://www.importyeti.com/api/search?q=<brand>` then `/company/<slug>`. The consignee address can match an investor's office; packaging imports (kg, cartons) bound launch volume. US sea imports only.
- **Domain history:** `https://crt.sh/?q=%25.<domain>&output=json` (first certificate date, subdomains like `au.` or `trk.`), WHOIS for creation date.

## Sources to distrust
- **coherecommerce.com brand pages:** the funding widget ("$1.7M Round A"), review blurb and repeat-purchase % are identical boilerplate across brands. Its product list is real (scraped from Shopify).
- **Founder round numbers** for stores and sell-outs: record them as claims and verify.
- **Any count at a search or scroll cap:** report as a floor.
