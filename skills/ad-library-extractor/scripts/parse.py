#!/usr/bin/env python3
"""Parse harvested FB Ad Library cards into structured copy + a plain-text report."""
import sys, json, re, os, shutil
from collections import Counter, OrderedDict

SRC, BRAND, SLUG, DEST = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
IMGSET = sys.argv[5] if len(sys.argv) > 5 else None   # optional: ids known to be image/meme ads

CTAS = {"shop now","learn more","sign up","order now","get offer","buy now","subscribe",
        "send message","contact us","apply now","download","watch more","see menu","book now",
        "get quote","play game","install now","try it","save","like page","open link",
        "get directions","see more","donate now","request time","listen now","start order",
        "get showtimes","send whatsapp message","message page","use app","watch video","join now"}

DOMAIN_RE = re.compile(
    r"^(HTTPS?://)?(WWW\.)?[A-Z0-9][A-Z0-9.\-]*\."
    r"(COM|CO|NET|ORG|IO|SHOP|US|AI|APP|STORE|INFO|BIZ|TV|ME)(/\S*)?$")
NOISE = {"open dropdown","see ad details","see summary details","sponsored","platforms","active",
         "inactive","","this ad has multiple versions","see ad detail","low impression count"}


def parse_card(text, known=None):
    d = {}
    m = re.search(r"Library ID:\s*(\d+)", text);            d["id"] = m.group(1) if m else None
    m = re.search(r"Started running on ([^\n]+)", text);    d["started"] = m.group(1).strip() if m else ""
    m = re.search(r"(\d[\d,]*) ads use this creative and text", text)
    d["variants"] = int(m.group(1).replace(",", "")) if m else 1
    d["status"] = "Active" if re.search(r"\nActive\n", text) else ""
    m = re.search(r"Platforms\n", text)

    parts = re.split(r"\nSponsored\n", text, maxsplit=1)
    if len(parts) < 2:
        d["primary"] = ""; d["blocks"] = []; return d
    head, tail = parts
    m = re.search(r"\n([^\n]+)\nSponsored", text)
    d["advertiser"] = m.group(1).strip() if m else ""

    lines = tail.split("\n")
    # locate first link-domain line -> everything before it is the primary text
    di = next((i for i, l in enumerate(lines) if DOMAIN_RE.match(l.strip())), None)

    if di is not None:
        body, rest = lines[:di], lines[di:]
    else:
        # No domain line (creator/partnership ads): the link block trails the copy.
        # Match the card tail against link blocks already learned from domain-bearing ads.
        clean = [re.sub("​", "", l).strip() for l in lines]
        clean = [l for l in clean if l and l.lower() not in NOISE]
        cut = None
        for tri in (known or []):
            seq = [x for x in tri if x]
            n = len(seq)
            if n and [c.lower() for c in clean[-n:]] == [s.lower() for s in seq]:
                cut = len(clean) - n
                d["_tail"] = {"domain": "", "headline": tri[0],
                              "description": tri[1], "cta": tri[2]}
                break
        if cut is None:
            # fall back: video timer marks the end of the primary text
            vi = next((i for i, l in enumerate(clean) if re.match(r"^0:00\s*/\s*\d", l)), None)
            if vi is not None and len(clean) - vi - 1 in (2, 3):
                tail_ls = clean[vi+1:]
                cta = tail_ls[-1] if tail_ls[-1].lower() in CTAS else ""
                core = tail_ls[:-1] if cta else tail_ls
                d["_tail"] = {"domain": "", "headline": core[0] if core else "",
                              "description": " | ".join(core[1:]), "cta": cta}
                cut = vi
        body, rest = (lines[:0] + clean[:cut], []) if cut is not None else (lines, [])

    body = [l for l in body if l.strip().lower() not in NOISE]
    prim = "\n".join(body)
    prim = re.split(r"\n?0:00\s*/\s*\d+:\d+", prim)[0]   # video timer line (0:00 / 0:30) ends the copy
    prim = re.sub(r"​", "", prim).strip()
    d["primary"] = prim

    # rest = repeating [DOMAIN, headline, (description), (CTA)] blocks (carousel = many)
    blocks, cur = [], None
    for l in rest:
        s = re.sub(r"​", "", l).strip()
        if not s or s.lower() in NOISE or s.startswith("Library ID:") or s.startswith("Started running"):
            continue
        if DOMAIN_RE.match(s):
            if cur: blocks.append(cur)
            cur = {"domain": s, "lines": [], "cta": ""}
        elif cur is not None:
            if s.lower() in CTAS and not cur["cta"]:
                cur["cta"] = s
            else:
                cur["lines"].append(s)
    if cur: blocks.append(cur)

    for b in blocks:
        b["headline"] = b["lines"][0] if b["lines"] else ""
        b["description"] = " | ".join(b["lines"][1:]) if len(b["lines"]) > 1 else ""
        b.pop("lines")
    if not blocks and d.get("_tail"):
        blocks = [d.pop("_tail")]
    d.pop("_tail", None)
    d["blocks"] = blocks
    return d


data = json.load(open(SRC))
ads_raw = data["ads"]
imgset = set(json.load(open(IMGSET))["ads"].keys()) if IMGSET and os.path.exists(IMGSET) else None

# pass 1: learn link blocks from ads that DO carry a domain line
known = Counter()
for rec in ads_raw.values():
    for b in parse_card(rec["text"])["blocks"]:
        if b["headline"]:
            known[(b["headline"], b["description"], b["cta"])] += 1
KNOWN = [k for k, _ in known.most_common()]

# optional: link blocks recovered from "See summary details" modals
GAP = json.load(open(os.environ["GAPFILL"])) if os.environ.get("GAPFILL") and \
      os.path.exists(os.environ["GAPFILL"]) else {}
VIDSET = set(json.load(open(os.environ["VIDSET"]))["ads"].keys()) if os.environ.get("VIDSET") and \
      os.path.exists(os.environ["VIDSET"]) else set()

ads = []
for aid, rec in ads_raw.items():
    p = parse_card(rec["text"], KNOWN)
    p["src"] = "card"
    if not any(b["headline"] for b in p["blocks"]):
        g = GAP.get(aid)
        if g and g.get("headline"):
            p["blocks"] = [{"domain": g.get("domain", ""), "headline": g["headline"],
                            "description": g.get("description", ""), "cta": g.get("cta", "")}]
            p["src"] = "summary-modal"
    p["files"] = rec.get("files", [])
    p["nvideo"] = rec.get("nvideo", 0)
    if imgset is not None:
        if aid in imgset:                       p["kind"] = "IMAGE"
        elif aid in VIDSET or rec.get("nvideo"): p["kind"] = "VIDEO"
        else:                                   p["kind"] = "UNCLASSIFIED"
    else:
        p["kind"] = "VIDEO" if rec.get("nvideo") else "IMAGE"
    ads.append(p)

# stable order: most creative-variants first (proxy for spend), then id
ads.sort(key=lambda a: (-a["variants"], a["id"] or ""))

os.makedirs(DEST, exist_ok=True)
imgdir = os.path.join(DEST, "images")
os.makedirs(imgdir, exist_ok=True)

srcimg = SRC.replace(".json", "_img")
copied = 0
for i, a in enumerate(ads, 1):
    a["n"] = f"{i:03d}"
    newfiles = []
    for k, fn in enumerate(a["files"]):
        sp = os.path.join(srcimg, fn)
        if not os.path.exists(sp): continue
        ext = os.path.splitext(fn)[1]
        nf = f"{SLUG}_{a['n']}_{a['id']}{'' if k == 0 else '_' + str(k)}{ext}"
        shutil.copy2(sp, os.path.join(imgdir, nf))
        newfiles.append(nf); copied += 1
    a["outfiles"] = newfiles

# Ads outside both filtered harvests: classify by creative size. Video posters come
# back full-res (1080x1920); grid statics are capped at 600px tall.
def _dims(path):
    b = open(path, "rb").read(200000)
    if b[:4] == b"\x89PNG":
        import struct as _s; return _s.unpack(">II", b[16:24])
    import struct as _s
    i = 2
    while i < len(b) - 9:
        if b[i] != 0xFF: i += 1; continue
        if b[i+1] in (0xC0, 0xC1, 0xC2):
            return _s.unpack(">H", b[i+7:i+9])[0], _s.unpack(">H", b[i+5:i+7])[0]
        i += 2 + _s.unpack(">H", b[i+2:i+4])[0]
    return 0, 0

for a in ads:
    if a["kind"] == "UNCLASSIFIED" and a["outfiles"]:
        try:
            w, h = _dims(os.path.join(imgdir, a["outfiles"][0]))
            a["kind"] = "VIDEO" if h > 700 else "IMAGE"
        except Exception:
            pass

# ---------------- text report ----------------
L = []
W = 78
L.append("=" * W)
L.append(f"{BRAND.upper()} — FACEBOOK AD LIBRARY: PRIMARY TEXT + HEADLINES")
L.append("=" * W)
L.append(f"Source      : {data['url']}")
import datetime as _dt
L.append(f"Captured    : {_dt.date.today().isoformat()}")
L.append(f"Coverage    : {len(ads)} unique ads captured (library reports {data['label']})")
L.append(f"Sort        : total impressions, descending (top performers first)")
L.append(f"Images saved: {copied} files in ./images/")
L.append("")

heads = Counter()
for a in ads:
    for b in a["blocks"]:
        if b["headline"]: heads[b["headline"]] += 1
prims = Counter(a["primary"][:120] for a in ads if a["primary"])

L.append("-" * W)
L.append(f"UNIQUE HEADLINES ({len(heads)}) — count = how many ads use it")
L.append("-" * W)
for h, c in heads.most_common():
    L.append(f"[{c:>3}x] {h}")
L.append("")
L.append("-" * W)
L.append(f"UNIQUE PRIMARY-TEXT OPENERS ({len(prims)}) — first 120 chars")
L.append("-" * W)
for t, c in prims.most_common():
    L.append(f"[{c:>3}x] {t.replace(chr(10),' / ')}")
# Offer phrases to flag. Edit for the brand being extracted.
OFFER_RE = re.compile(os.environ.get("OFFER_RE", r"free gift|free shipping|bundle|% off|bogo|buy one|starter kit|free trial"), re.I)
offer = [a for a in ads
         if OFFER_RE.search(a["primary"]) or
            any(OFFER_RE.search(b["headline"] + " " + b["description"]) for b in a["blocks"])]
NAMED_OFFER = os.environ.get("NAMED_OFFER", "starter kit")
named = [a for a in ads if re.search(NAMED_OFFER, a["primary"], re.I)]
L.append("")
L.append("-" * W)
L.append(f"OFFER ADS ({len(offer)} of {len(ads)})")
L.append("-" * W)
L.append(f"Ads naming '{NAMED_OFFER}' outright in the body copy: {len(named)}")
L.append(f"Ads matching any offer phrase (OFFER_RE): {len(offer)}")
L.append("")
for a in offer:
    h = a["blocks"][0]["headline"] if a["blocks"] else ""
    star = "*" if re.search(NAMED_OFFER, a["primary"], re.I) else " "
    L.append(f" {star}#{a['n']} [{a['kind']:5s}] {a['outfiles'][0] if a['outfiles'] else '-'}")
    L.append(f"        headline: {h}")
L.append("")
L.append(f"  (* = the body copy names '{NAMED_OFFER}' explicitly)")
L.append("")
L.append("=" * W)
L.append("FULL AD-BY-AD COPY")
L.append("=" * W)

for a in ads:
    L.append("")
    L.append("#" * W)
    tag = f"#{a['n']}  Library ID {a['id']}  [{a['kind']}]"
    if a["variants"] > 1: tag += f"  ({a['variants']} ads use this creative & text)"
    L.append(tag)
    L.append(f"Started: {a['started']}   Advertiser: {a.get('advertiser','')}")
    if a["outfiles"]: L.append(f"Image(s): {', '.join('images/' + f for f in a['outfiles'])}")
    L.append("#" * W)
    L.append("")
    L.append("--- PRIMARY TEXT ---")
    L.append(a["primary"] if a["primary"] else "(none)")
    L.append("")
    if a["blocks"]:
        for j, b in enumerate(a["blocks"], 1):
            lbl = "--- LINK ---" if len(a["blocks"]) == 1 else f"--- CAROUSEL CARD {j} ---"
            L.append(lbl)
            L.append(f"Domain     : {b['domain']}")
            L.append(f"HEADLINE   : {b['headline']}")
            if b["description"]: L.append(f"Description: {b['description']}")
            if b["cta"]:         L.append(f"CTA        : {b['cta']}")
            L.append("")
    else:
        L.append("--- LINK ---")
        L.append("(no link block captured)")
        L.append("")

txt = os.path.join(DEST, f"{SLUG}_ad-copy.txt")
open(txt, "w").write("\n".join(L))
json.dump(ads, open(os.path.join(DEST, f"{SLUG}_ads.json"), "w"), indent=1)

print(f"{BRAND}: {len(ads)} ads | {len(heads)} unique headlines | {copied} images -> {DEST}")
empty = sum(1 for a in ads if not a["primary"])
noh   = sum(1 for a in ads if not any(b['headline'] for b in a['blocks']))
print(f"  QA: empty primary text = {empty} | ads with no headline = {noh}")
