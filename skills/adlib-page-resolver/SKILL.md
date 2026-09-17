---
name: adlib-page-resolver
description: Turn a list of brand names into VERIFIED links to each brand's own Facebook Ad Library page (view_all_page_id), not a keyword search. Use when the user gives a brand list (doc, sheet, chat) and says "link each of these to their ad library", "find the actual brand page", "hyperlink each page", "get me the ad library for every brand", or before running ad-library-extractor when all you have is a brand NAME. Handles the traps - keyword search ranks affiliates/advertorials first, domains beat names, delegate_page is the page ID, parked domains, brands with zero active ads - and proves every link by reading the page name back.
---

# adlib-page-resolver

Brand names -> `facebook.com/ads/library/?...&search_type=page&view_all_page_id=<ID>` links, each verified.
Validated Sept 2026 on 52 brands: 52/52 verified.

Work in a project folder. All scripts are headless Playwright (no login; the Ad Library is public) and run from that folder.

## 0. Get the list and back it up
- Google Doc shared by link: `curl -sL ".../export?format=txt"` for the list.
- Dedupe to unique brands. Map display variants to one label (`Carnivore.snax` = `Carnivore Snax`, `RYZE Superfoods` = `Ryze`, an IG handle like `Jakkspacific.toys` = JAKKS Pacific). Split lines with two brands (`MASA Chips // VacaChips`, `Skool / Alex Hormozi`) into two.

## 1. Pass 1: keyword search, pick by NAME
```bash
S=<this skill's base directory>/scripts
# queries.json: {"<label>": "<query>"}. Use the product-specific name when the brand name is generic ("Neuro Gum", "Joyride Sweets", "Ridge wallet", "Brick phone").
python3 $S/resolve_pages.py queries.json candidates.json     # run_in_background; ~52 brands in ~4 min at 4 tabs
python3 $S/pick.py candidates.json                           # -> picked.json, prints ?? for anything not an exact name match
```
**Never pick by ad count.** The top advertiser for a brand keyword is usually an affiliate or advertorial page
(Everyday Dose -> "Wellness Insider", Sun Powder -> Zespri, MASA -> Tostitos). `pick.py` matches normalized names;
eyeball every `??` row's full candidate list before accepting it.

## 2. Pass 2 for the misses (in this order)
1. **Domain as the query** (`sunpowder.com`, `masachips.com`): ad link captions carry the domain, so it lands on the real advertiser.
2. **Facebook page slug** -> `python3 $S/fb_page_id.py <slug> <slug2> ...`. The **`delegate_page` id IS the Ad Library page ID**; `userID` is not.
2b. **Still nothing? Use the Ad Library's own typeahead** -> `python3 $S/typeahead_pages.py "Brand" "brandhandle"`.
   Use it when the brand name is a celebrity nickname (Drizzy = Drake), the domain query returns 0 (brands with no ads have no
   captions to match), and `facebook.com/<slug>` is login-walled (no `delegate_page` in the HTML). The script returns
   `page_id + ig_username + ig_followers + category` for up to ~70 pages. **Pick the one whose `ig_username` equals the handle in the
   brand site's footer.** Typing the handle also surfaces the brand's `IG_ADS_IDENTITY` id, which is a separate id to check.
   Trap: the search box is disabled ("Choose an ad category") on the bare `/ads/library/` URL and only enabled on a `?q=` URL.
   Validated on Drizzy 2026-09-16 -> 994505917081830.
3. **Parked domain?** A ~114-byte homepage with `location.href="/lander"` means the brand lives elsewhere. One WebSearch for the brand finds the real site; `curl` its footer for the Facebook/Instagram link, then step 1 or 2 on that.
4. Put final choices in `final.json`: `{"<label>": {"page_id": "...", "page_name": "...", "status": "active|all"}}`.

## 3. Verify every link (non-negotiable)
```bash
python3 $S/verify.py final.json verified.json                         # active, US
ADLIB_COUNTRY=ALL ADLIB_STATUS=all python3 $S/verify.py zeros.json z.json   # recheck any 0-result pages
```
- `OK` = the expected page name appears on the loaded Ad Library page.
- A **0 active** result: recheck with a fixed ~12s wait (the verifier's early exit can catch a "0 results" placeholder). If
  it's genuinely zero, set `"status": "all"` so the link isn't a blank page, and report which brands are dark right now.
- Flag brands whose ads mostly run from OTHER pages (founder/celebrity pages, UGC agencies like Arcads AI, persona pages):
  the brand-page link will look thin.

## Hand-off message
Lead with the count linked + verified. Then list: brands with 0 active ads (linked to all ads), brands whose ads run from
other pages, and every ambiguous-name call (e.g. Hollow = Hollow Alpaca Socks). Deliverable folder path last.
