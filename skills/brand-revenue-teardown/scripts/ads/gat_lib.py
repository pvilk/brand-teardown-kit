"""Shared client for the Google Ads Transparency Center RPC.

The RPC needs NO cookie, NO api key and NO XSRF token -- but only from OUTSIDE a
browser. Called from inside the page it fails with XsrfException. Do not debug the
token; leave the browser.
"""
import gzip, json, random, sys, time, urllib.error, urllib.parse, urllib.request

BASE = "https://adstransparency.google.com/anji/_/rpc"
HDR = {
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Referer": "https://adstransparency.google.com/",
    "X-Same-Domain": "1",
    "Accept-Encoding": "gzip",
}
# regionCode = 2000 + ISO-3166-1 numeric. Full map: faniAhmed/GoogleAdsTransparencyScraper regions.py
REGIONS = {"US": 2840, "GB": 2826, "CA": 2124, "AU": 2036, "DE": 2276,
           "FR": 2250, "IN": 2356, "JP": 2392, "BR": 2076, "MX": 2484}


class RateLimited(RuntimeError):
    """HTTP 429. Google returns an HTML error page, so a naive json.loads() raises a
    confusing 'Expecting value: line 1 column 1' -- which looks identical to 'no ads'."""


def rpc(method, payload, tries=5):
    """POST f.req=<json> to a SearchService/LookupService method. Returns parsed dict.

    Raises RateLimited on 429 so callers never mistake throttling for an empty library.
    """
    url = f"{BASE}/{method}?authuser="
    body = ("f.req=" + urllib.parse.quote(json.dumps(payload, separators=(",", ":")))).encode()
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=HDR)
            status = 200
            try:
                resp = urllib.request.urlopen(req, timeout=60)
                raw, status = resp.read(), resp.status
            except urllib.error.HTTPError as e:
                raw, status = e.read(), e.code   # error bodies are gzipped even when success bodies are not
            if raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
            txt = raw.decode("utf-8", "replace")

            if status == 429 or txt.lstrip()[:9].lower() == "<!doctype":
                wait = 30 * (attempt + 1)
                if attempt == tries - 1:
                    raise RateLimited(
                        "HTTP 429 from adstransparency. Your IP is throttled -- this is NOT "
                        "an empty result. Wait ~10-30 min, lower page_size, raise the sleep "
                        "between pages, or switch egress IP. (Google rate-limits IPv6 harder.)")
                print(f"  .. 429 rate limited, backing off {wait}s "
                      f"(attempt {attempt+1}/{tries})", file=sys.stderr, flush=True)
                time.sleep(wait)
                continue
            if "BadRequestException" in txt[:200]:
                # the ONLY informative error this surface produces -- your field shape is wrong
                print(f"  !! payload rejected: {txt[:220]}", file=sys.stderr)
                return {}
            return json.loads(txt)
        except RateLimited:
            raise
        except Exception as e:
            if attempt == tries - 1:
                print(f"  !! rpc failed: {e}", file=sys.stderr)
                return {}
            time.sleep(4 * (attempt + 1))
    return {}


def search_creatives(target, region="US", page_size=100, max_pages=60, verbose=True):
    """Paginate every creative for a domain (example.com) or an advertiser id (AR...).

    Pagination: response key "2" is the cursor; feed it back as request key "4".
    A WRONG FIELD SHAPE RETURNS HTTP 200 WITH {} -- silent, and indistinguishable from
    "this advertiser has no ads". Always sanity-check the count against the web UI.
    """
    rc = REGIONS.get(region.upper(), region if isinstance(region, int) else 2840)
    is_adv = str(target).startswith("AR")
    filt = {"8": [rc]}
    if is_adv:
        filt["13"] = {"1": [target]}
    else:
        filt["12"] = {"1": target, "2": True}

    rows, seen, token, page = [], set(), None, 0
    while page < max_pages:
        payload = {"2": page_size, "3": filt, "7": {"1": 1}}
        if token:
            payload["4"] = token
        data = rpc("SearchService/SearchCreatives", payload)
        batch = data.get("1") or []
        token = data.get("2")
        page += 1
        new = 0
        for r in batch:
            cid = r.get("2")
            if cid and cid not in seen:
                seen.add(cid); rows.append(r); new += 1
        if verbose:
            print(f"  page {page}: {len(batch)} rows, {new} new, total {len(rows)}"
                  f", cursor={'yes' if token else 'END'}", flush=True)
        if not token or not batch or new == 0:
            break
        time.sleep(1.1 + random.random() * 0.4)
    return rows


def content_url(row):
    """The video preview URL (content.js), if this creative has one."""
    return ((row.get("3") or {}).get("1") or {}).get("4")


def image_html(row):
    """The <img> snippet, if this creative is a static."""
    return ((row.get("3") or {}).get("3") or {}).get("2")
