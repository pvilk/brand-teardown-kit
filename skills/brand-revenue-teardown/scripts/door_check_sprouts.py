#!/usr/bin/env python3
"""
door_check.py - per-store availability + shelf price of Drizzy Peanut Butter at Sprouts Farmers Market,
read from Sprouts' Instacart-powered storefront (shop.sprouts.com) public GraphQL (guest session, no login).

Usage
  python3 door_check_sprouts.py 80210 85016 75206           # nearest Sprouts to each ZIP
  python3 door_check_sprouts.py --nearest 3 80210 85016     # 3 nearest stores per ZIP
  python3 door_check_sprouts.py --census                    # every Sprouts location reachable from the
                                                    #   brand's Stockist list (set STOCKIST_FILE to stockist_all.py output)
  python3 door_check_sprouts.py --reuse-locations door_checks/census_baseline_20260916_locations.json   # same 499 stores
  python3 door_check_sprouts.py --product 127683139 --delay 1.5 --out my.csv 92101

Output: CSV (default retail/door_checks/door_check_<UTCSTAMP>.csv) with one row per store:
  checked_at_utc, query_zip, retailer_location_id, store_name, store_number, street, city, state, store_zip,
  distance_mi, instore_shop_id, product_id, item_listed, available, stock_level, availability_score,
  low_stock_label, price, reg_price, on_sale, error

How the fields behave (learned 2026-09-16)
  - item_listed=False  -> Instacart returned no item for that location: not in that store's catalog
                          (not carried / not ranged / delisted). It is NOT proof the shelf is empty.
  - stock_level        -> Instacart's predicted in-store stock ("inStock", "lowStock", "outOfStock").
  - availability_score -> Instacart's ML availability probability (0-1), driven by shopper found/not-found
                          events. Re-run over time: a falling score / lowStock flips = sell-through or
                          stock-out signal; a jump back = restock.
  - price / reg_price  -> price only resolves when shopId belongs to the same location (script handles it).
  - Items accepts ONE retailer location per request ("Too many products or locations" otherwise).
Persisted-query hashes can rotate when Instacart deploys; if every call errors with PersistedQueryNotFound,
re-capture them: load a shop.sprouts.com product page in headless Playwright, log responses whose URL contains
"graphql", read each operationName + sha256Hash from the request URL, and update HASHES below.
"""
import argparse, csv, datetime, glob, json, os, re, sys, time
from curl_cffi import requests

# Set INTEL_DIR to the teardown folder (e.g. ~/research/<brand>-intel) and STOCKIST_MAP to the brand's Stockist map id.
BASE = os.path.expanduser(os.environ.get("INTEL_DIR", os.getcwd()))
STOCKIST_MAP = os.environ.get("STOCKIST_MAP", "map_w3rggxyq")
HASHES = {
    "Items": "388f200246a7fcc0f10ed9c1bb97952f9046e69c1be3b14ebae5855822cec831",
    "AvailableInStoreRetailerServices": "44105036e7fbffa98cf4ac2cf41cb1c0c47dfa9b3e19b8e56154f543637a7699",
    "ShopCollectionScoped": "f20693c3c551f0e0fbdcac9b2ca7aa6db50f9224a39967ba5ac767bb2b598f85",
}
DRIZZY_PRODUCT_ID = os.environ.get("PRODUCT_ID", "127683139")  # Sprouts/Instacart product id from the shop.sprouts.com product URL (default = the Drizzy worked example)
ZONE_ID = "943"                   # any valid zone works for price resolution (tested in two metros)
REUSE = None
FIELDS = ["checked_at_utc", "query_zip", "retailer_location_id", "store_name", "store_number", "street", "city",
          "state", "store_zip", "distance_mi", "instore_shop_id", "product_id", "item_listed", "available",
          "stock_level", "availability_score", "low_stock_label", "price", "reg_price", "on_sale", "error"]


class Sprouts:
    def __init__(self, delay):
        self.s = requests.Session(impersonate="chrome124")
        self.delay = delay
        self.s.get("https://shop.sprouts.com/store/sprouts/storefront", timeout=40)
        self.h = {"Referer": "https://shop.sprouts.com/store/sprouts/storefront"}

    def gql(self, op, variables, tries=4):
        params = {"operationName": op,
                  "variables": json.dumps(variables, separators=(",", ":")),
                  "extensions": json.dumps({"persistedQuery": {"version": 1, "sha256Hash": HASHES[op]}},
                                           separators=(",", ":"))}
        for attempt in range(tries):
            time.sleep(self.delay)
            try:
                r = self.s.get("https://shop.sprouts.com/graphql", params=params, headers=self.h, timeout=40)
            except Exception as e:  # network hiccup
                err = str(e); time.sleep(5 * (attempt + 1)); continue
            if r.status_code in (429, 503):
                print(f"  {op}: HTTP {r.status_code}, backing off", file=sys.stderr)
                time.sleep(30 * (attempt + 1)); continue
            if "captcha" in r.text[:2000].lower():
                raise SystemExit("CAPTCHA returned; stopping (do not bypass).")
            try:
                return r.json()
            except Exception:
                err = f"HTTP {r.status_code} non-JSON: {r.text[:120]}"
                time.sleep(5 * (attempt + 1))
        return {"errors": [{"message": f"failed after retries: {err if 'err' in dir() else ''}"}]}

    def stores_near(self, zip_code, coords=None):
        v = {"postalCode": zip_code, "coordinates": coords, "retailerIds": ["279"]}
        j = self.gql("AvailableInStoreRetailerServices", v)
        d = (j.get("data") or {}).get("availableInStoreRetailerServices") or {}
        center = d.get("geographicCenter") or coords
        out = []
        for ret in d.get("retailers") or []:
            for loc in ret.get("locations") or []:
                vs = loc.get("viewSection") or {}
                name = vs.get("locationNameString") or ""
                m = re.search(r"Store #(\d+)", name)
                line2 = vs.get("lineTwoString") or ""
                m2 = re.match(r"(.*),\s*([A-Z]{2})\s+(\d{5})", line2)
                out.append({"retailer_location_id": loc["retailerLocationId"], "store_name": name,
                            "store_number": m.group(1) if m else "",
                            "street": (vs.get("lineOneString") or "").split(",")[0],
                            "city": m2.group(1) if m2 else "", "state": m2.group(2) if m2 else "",
                            "store_zip": loc.get("postalCode") or (m2.group(3) if m2 else ""),
                            "distance_mi": loc.get("distance"),
                            "lat": (loc.get("coordinates") or {}).get("latitude"),
                            "lon": (loc.get("coordinates") or {}).get("longitude")})
        return out, center

    def instore_shops(self, zip_code, center):
        if not center:
            return {}
        v = {"retailerSlug": "sprouts", "postalCode": zip_code,
             "coordinates": {"latitude": center["latitude"], "longitude": center["longitude"]},
             "addressId": None, "includeAllRetailerLocations": True}
        j = self.gql("ShopCollectionScoped", v)
        shops = (((j.get("data") or {}).get("shopCollection") or {}).get("shops")) or []
        return {s["retailerLocationId"]: s["id"] for s in shops if s.get("serviceType") == "instore"}

    def item(self, loc_id, shop_id, zip_code, product_id):
        v = {"ids": [f"items_{loc_id}-{product_id}"], "shopId": str(shop_id or "516379"),
             "zoneId": ZONE_ID, "postalCode": zip_code}
        j = self.gql("Items", v)
        errs = "; ".join(e.get("message", "") for e in (j.get("errors") or []))
        items = ((j.get("data") or {}).get("items")) or []
        it = items[0] if items else None
        row = {"product_id": product_id, "item_listed": bool(it), "error": errs}
        if it:
            av = it.get("availability") or {}
            tp = ((it.get("viewSection") or {}).get("trackingProperties")) or {}
            ic = (((it.get("price") or {}).get("viewSection") or {}).get("itemCard")) or {}
            row.update({"available": av.get("available"), "stock_level": av.get("stockLevel"),
                        "availability_score": tp.get("availability_score"),
                        "low_stock_label": tp.get("low_stock_label"),
                        "price": ic.get("priceString"),
                        "reg_price": ic.get("plainFullPriceString") or ic.get("priceString"),
                        "on_sale": (tp.get("on_sale_ind") or {}).get("on_sale")})
        return row


def census_seeds():
    if os.environ.get("STOCKIST_FILE"):
        files = [os.path.expanduser(os.environ["STOCKIST_FILE"])]
    else:
        files = sorted(glob.glob(f"{BASE}/raw/retail/stockist_{STOCKIST_MAP}_locations_union_*.json"))
    if not files:
        raise SystemExit("no Stockist locations file: run stockist_all.py first and set STOCKIST_FILE=<its output json>")
    locs = json.load(open(files[-1]))
    return [(l["postal_code"], {"latitude": float(l["latitude"]), "longitude": float(l["longitude"])}) for l in locs]


def _mi(a, b):
    import math
    R = 3958.8
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * R * math.asin(math.sqrt(d))


def census(sp, seeds, out, product):
    """Discover every Sprouts location around the seed doors (store lookups return ~25-40 stores each,
    so most seeds are skipped once a nearby lookup already covered them), then check the item per location."""
    locs, shop_of, q = {}, {}, 0
    if REUSE:
        saved = json.load(open(REUSE))
        locs, shop_of, seeds = saved["locations"], saved["instore_shop_of"], []
        print(f"reusing {len(locs)} store locations from {REUSE}", flush=True)
    for zip_code, coords in seeds:
        p = (coords["latitude"], coords["longitude"])
        if any(l["lat"] and _mi(p, (l["lat"], l["lon"])) < 0.3 for l in locs.values()):
            continue
        stores, center = sp.stores_near(zip_code, coords)
        shops = sp.instore_shops(zip_code, center)
        q += 1
        for s in stores:
            s["query_zip"] = zip_code
            locs.setdefault(s["retailer_location_id"], s)
        for lid, sid in shops.items():
            shop_of.setdefault(lid, sid)
        print(f"lookup {q}: seed {zip_code} -> {len(stores)} stores, {len(locs)} known", flush=True)
    json.dump({"locations": locs, "instore_shop_of": shop_of},
              open(out.replace(".csv", "_locations.json"), "w"), indent=1)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for i, (lid, s) in enumerate(sorted(locs.items(), key=lambda kv: (kv[1]["state"], kv[1]["city"])), 1):
            row = {"checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                   "instore_shop_id": shop_of.get(lid, ""), **s}
            row.update(sp.item(lid, row["instore_shop_id"], s["store_zip"] or s["query_zip"], product))
            w.writerow(row); fh.flush()
            print(f"{i:4d}/{len(locs)} {s['store_name'][:40]:40s} {s['state']} listed={row['item_listed']} "
                  f"{row.get('stock_level')} {row.get('availability_score')} {row.get('price')}", flush=True)
    print("wrote", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("zips", nargs="*")
    ap.add_argument("--nearest", type=int, default=1, help="stores per ZIP (default 1)")
    ap.add_argument("--census", action="store_true", help="every Sprouts location near every Stockist door")
    ap.add_argument("--product", default=DRIZZY_PRODUCT_ID)
    ap.add_argument("--delay", type=float, default=1.2, help="seconds between requests (be polite)")
    ap.add_argument("--out")
    ap.add_argument("--reuse-locations", help="census *_locations.json from a prior run: skip store discovery, "
                                                "re-check exactly the same stores (fastest re-run for a time series)")
    a = ap.parse_args()
    global REUSE
    REUSE = a.reuse_locations
    if REUSE:
        a.census = True
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%MZ")
    out = a.out or f"{BASE}/retail/door_checks/door_check_{stamp}.csv"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sp = Sprouts(a.delay)
    seeds = ([] if REUSE else census_seeds()) if a.census else [(z, None) for z in a.zips]
    if not seeds and not REUSE:
        ap.error("give ZIPs or --census")
    seen, n = set(), 0
    if a.census:
        return census(sp, seeds, out, a.product)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for zip_code, coords in seeds:
            stores, center = sp.stores_near(zip_code, coords)
            if a.census:
                # the seed store itself is the one within ~0.3 mi; fall back to nearest
                todo = [s for s in stores if (s["distance_mi"] or 99) <= 0.5][:1] or stores[:1]
            else:
                todo = stores[:a.nearest]
            todo = [s for s in todo if s["retailer_location_id"] not in seen]
            if not todo:
                if not stores:
                    w.writerow({"checked_at_utc": stamp, "query_zip": zip_code, "error": "no Sprouts store returned"})
                continue
            shops = sp.instore_shops(zip_code, center)
            for s in todo:
                seen.add(s["retailer_location_id"])
                row = {"checked_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
                       "query_zip": zip_code, "instore_shop_id": shops.get(s["retailer_location_id"], ""), **s}
                row.update(sp.item(s["retailer_location_id"], row["instore_shop_id"], s["store_zip"] or zip_code, a.product))
                w.writerow(row); fh.flush(); n += 1
                print(f"{n:4d} {row['store_name'][:45]:45s} {row['state']:2s} listed={row['item_listed']} "
                      f"{row.get('stock_level')} score={row.get('availability_score')} {row.get('price')} reg={row.get('reg_price')}")
    print("wrote", out)


if __name__ == "__main__":
    main()
