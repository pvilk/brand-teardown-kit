#!/usr/bin/env python3
"""compare_runs.py OLD.csv NEW.csv - turn two door_check census runs into a sell-through signal.
Prints: listed/delisted flips, stock_level transitions (inStock->lowStock/outOfStock = sell-through or
supply gap; out->in = restock), availability_score shift (median and per-store drops > 0.15), price changes."""
import csv, sys, statistics, collections
old = {r["retailer_location_id"]: r for r in csv.DictReader(open(sys.argv[1]))}
new = {r["retailer_location_id"]: r for r in csv.DictReader(open(sys.argv[2]))}
both = sorted(set(old) & set(new))
flips = collections.Counter((old[k]["item_listed"], new[k]["item_listed"]) for k in both)
trans = collections.Counter((old[k]["stock_level"] or "-", new[k]["stock_level"] or "-") for k in both)
f = lambda r: float(r["availability_score"]) if r["availability_score"] else None
so = [f(old[k]) for k in both if f(old[k]) is not None and f(new[k]) is not None]
sn = [f(new[k]) for k in both if f(old[k]) is not None and f(new[k]) is not None]
print(f"stores in both runs: {len(both)} (only old {len(set(old)-set(new))}, only new {len(set(new)-set(old))})")
print("listed old->new:", dict(flips))
print("stock level old->new:", dict(trans))
if so:
    print(f"availability_score median {statistics.median(so):.3f} -> {statistics.median(sn):.3f}")
drops = [(old[k]["store_name"], old[k]["state"], f(old[k]), f(new[k])) for k in both
         if f(old[k]) is not None and f(new[k]) is not None and f(old[k]) - f(new[k]) > 0.15]
print(f"stores with score drop > 0.15: {len(drops)}")
for d in sorted(drops, key=lambda x: x[2] - x[3], reverse=True)[:25]:
    print("  ", d)
pc = collections.Counter((old[k]["price"], new[k]["price"]) for k in both if old[k]["price"] != new[k]["price"] and new[k]["price"])
print("price changes:", dict(pc))
