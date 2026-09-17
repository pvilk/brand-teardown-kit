#!/usr/bin/env python3
"""Hop 2: content.js preview URL -> YouTube id (or signed googlevideo URL).

    python3 resolve_videos.py [dir]

Reads creatives_raw.json; writes resolved.json, youtube_ids.txt,
manifest_videos.csv, manifest_creatives.csv.
"""
import csv, datetime, gzip, json, os, random, re, sys, threading, time
import urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gat_lib import content_url

D = sys.argv[1] if len(sys.argv) > 1 else "."
HDR = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
       "Referer": "https://adstransparency.google.com/", "Accept-Encoding": "gzip"}
RE_YT = [re.compile(r"yt_video_id'\s*:\s*'([A-Za-z0-9_-]{11})'"),
         re.compile(r"video_id'\s*:\s*'([A-Za-z0-9_-]{11})'"),
         re.compile(r"video_videoId'\s*:\s*'([A-Za-z0-9_-]{11})'"),
         re.compile(r"/embed/([A-Za-z0-9_-]{11})"),
         re.compile(r"ytimg\.com/vi/([A-Za-z0-9_-]{11})"),
         re.compile(r"youtube\.com/watch\?v=([A-Za-z0-9_-]{11})")]
RE_GV = re.compile(r"(https?://[\w.-]*googlevideo\.com/[^\s\"'\]\\]+)")


def get(url):
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers=HDR), timeout=45).read()
    except urllib.error.HTTPError as e:
        raw = e.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


def unesc(s):
    for _ in range(2):                      # the payload is DOUBLE-escaped
        try:
            s = s.encode("utf-8", "surrogatepass").decode("unicode_escape")
        except Exception:
            break
    return s


def strip_ui(url):
    """uiFeatures biases the response toward a UI render instead of the video payload."""
    p = urllib.parse.urlsplit(url)
    q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True) if k != "uiFeatures"]
    return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q), p.fragment))


lock, done = threading.Lock(), [0]


def resolve(r):
    url, out = content_url(r), {"kind": "none"}
    for u in (strip_ui(url), url):          # stripped first, original as fallback
        try:
            txt = get(u)
        except Exception:
            continue
        body = txt + "\n" + unesc(txt)
        hit = None
        for rx in RE_YT:
            m = rx.search(body)
            if m:
                hit = {"kind": "youtube", "id": m.group(1)}; break
        if not hit:
            m = RE_GV.search(body)
            if m:
                hit = {"kind": "googlevideo", "url": unesc(m.group(1))}
        if hit:
            out = hit; break
    time.sleep(0.25 + random.random() * 0.35)
    with lock:
        done[0] += 1
        if done[0] % 40 == 0:
            print(f"  resolved {done[0]}", flush=True)
    return {"creative_id": r.get("2"), "advertiser_id": r.get("1"), "advertiser": r.get("12"),
            "format_code": r.get("4"), "first_shown": (r.get("6") or {}).get("1"),
            "last_shown": (r.get("7") or {}).get("1"), **out}


rows = json.load(open(os.path.join(D, "creatives_raw.json")))
targets = [r for r in rows if content_url(r)]
print(f"resolving {len(targets)} creatives with preview URLs (6 workers)", flush=True)
with ThreadPoolExecutor(max_workers=6) as ex:
    results = list(ex.map(resolve, targets))
json.dump(results, open(os.path.join(D, "resolved.json"), "w"), indent=1)

yt = sorted({r["id"] for r in results if r["kind"] == "youtube"})
open(os.path.join(D, "youtube_ids.txt"), "w").write("\n".join(yt) + "\n")

def dt(ts):
    try:
        return datetime.datetime.fromtimestamp(int(ts), datetime.UTC).strftime("%Y-%m-%d")
    except Exception:
        return ""

crows = [{"video_id": r["id"], "youtube_url": f'https://www.youtube.com/watch?v={r["id"]}',
          "creative_id": r["creative_id"], "advertiser": r["advertiser"],
          "format_code": r["format_code"], "first_shown": dt(r["first_shown"]),
          "last_shown": dt(r["last_shown"]),
          "transparency_url": f'https://adstransparency.google.com/advertiser/{r["advertiser_id"]}/creative/{r["creative_id"]}?region=US'}
         for r in results if r["kind"] == "youtube"]
if crows:
    with open(os.path.join(D, "manifest_creatives.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(crows[0].keys())); w.writeheader(); w.writerows(crows)
    byv = {}
    for r in crows:
        byv.setdefault(r["video_id"], []).append(r)
    vrows = [{"video_id": v, "youtube_url": f"https://www.youtube.com/watch?v={v}",
              "creative_count": len(rs),
              "first_shown": min([x["first_shown"] for x in rs if x["first_shown"]] or [""]),
              "last_shown": max([x["last_shown"] for x in rs if x["last_shown"]] or [""])}
             for v, rs in byv.items()]
    vrows.sort(key=lambda x: (x["last_shown"], x["creative_count"]), reverse=True)
    with open(os.path.join(D, "manifest_videos.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(vrows[0].keys())); w.writeheader(); w.writerows(vrows)

kinds = {}
for r in results:
    kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
print(f"\n=== resolution: {kinds}")
print(f"unique youtube videos: {len(yt)}  (creatives reuse videos across variations)")
print("unresolved are usually statics; a format-video creative that still fails has no archived video")
