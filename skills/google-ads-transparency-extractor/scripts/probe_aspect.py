#!/usr/bin/env python3
"""Bucket every resolved video by TRUE pixel dimensions, and write per-aspect batch files.

    ./probe_aspect.sh <dir>      # runs the yt-dlp metadata probe, then this

⚠️ NEVER filter on the creative TITLE. Advertisers label some files "16x9"/"9x16", but the
convention is partial: measured on a real library, title-matching found 4 of 10 landscape
videos and missed all three 4K ones. Pixels are authoritative; titles are a cross-check.
"""
import collections, os, re, sys

D = sys.argv[1] if len(sys.argv) > 1 else "."
rows = []
for line in open(os.path.join(D, "dims_raw.txt")):
    p = line.rstrip("\n").split("|")
    if len(p) < 5:
        continue
    try:
        w, h = int(p[1]), int(p[2])
    except ValueError:
        continue
    rows.append((p[0], w, h, p[3], "|".join(p[4:])))


def bucket(w, h):
    r = w / h
    if r >= 1.6:  return "16x9_landscape"
    if r >= 1.2:  return "other_landscape"
    if 0.95 <= r <= 1.05: return "1x1_square"
    if 0.7 <= r < 0.95:   return "4x5_portrait"
    return "9x16_vertical"


groups = collections.defaultdict(list)
for vid, w, h, dur, title in rows:
    groups[bucket(w, h)].append((vid, w, h, dur, title))

print(f"probed {len(rows)} videos\n=== TRUE pixel dimensions ===")
for k, v in sorted(groups.items(), key=lambda x: -len(x[1])):
    print(f"  {k:18} {len(v):4}   ({100*len(v)/max(len(rows),1):.0f}%)")
    open(os.path.join(D, f"ids_{k}.txt"), "w").write("\n".join(sorted({r[0] for r in v})) + "\n")

land = groups.get("16x9_landscape", [])
if land:
    print(f"\n=== the {len(land)} landscape videos ===")
    for vid, w, h, dur, title in sorted(land, key=lambda x: x[4]):
        tok = "[16x9 in name]" if re.search(r"16[x_:]9", title, re.I) else "[UNLABELED]"
        print(f"  {vid}  {w}x{h}  {str(dur)+'s':>6}  {tok:15} {title[:58]}")
    named = sum(1 for r in rows if re.search(r"16[x_:]9", r[4], re.I))
    print(f"\ncross-check: only {named} of {len(land)} carry '16x9' in the title "
          f"-- title-filtering would have MISSED {len(land)-named}")
print(f"\nwrote ids_<aspect>.txt batch files in {D}")
