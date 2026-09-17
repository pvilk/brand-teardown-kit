# Pull every location in a brand's Stockist store locator by tiling searches over the geohash overview.
# Usage: python3 stockist_all.py <map_id> <brand_site_url> [overview.json] [out.json]
#   map_id: from the locator page HTML ("map_xxxxxxxx"); overview: GET https://stockist.co/api/v1/<map_id>/locations/overview.js saved to a file
import json, math, time, sys
MAP_ID = sys.argv[1] if len(sys.argv) > 1 else "map_w3rggxyq"
REFERER = sys.argv[2] if len(sys.argv) > 2 else "https://getdrizzy.co/"
OVERVIEW = sys.argv[3] if len(sys.argv) > 3 else "overview_stockist.txt"
OUT = sys.argv[4] if len(sys.argv) > 4 else "stockist_locations_all.json"
from curl_cffi import requests
B32="0123456789bcdefghjkmnpqrstuvwxyz"
def gh_decode(g):
    lat=[-90.0,90.0]; lon=[-180.0,180.0]; even=True
    for c in g:
        cd=B32.index(c)
        for mask in [16,8,4,2,1]:
            rng = lon if even else lat
            mid=(rng[0]+rng[1])/2
            if cd & mask: rng[0]=mid
            else: rng[1]=mid
            even=not even
    return (lat[0]+lat[1])/2,(lon[0]+lon[1])/2
def dist(a,b):
    R=3958.8
    la1,lo1=map(math.radians,a); la2,lo2=map(math.radians,b)
    d=math.sin((la2-la1)/2)**2+math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(math.sqrt(d))
ov=json.load(open(OVERVIEW))
pts=[gh_decode(x.split(":")[0]) for x in ov["i"]]
s=requests.Session(impersonate="chrome124")
found={}
queries=0
for i,p in enumerate(pts):
    if any(dist(p,(float(l["latitude"]),float(l["longitude"])))<0.5 for l in found.values()):
        continue
    u=f"https://stockist.co/api/v1/{MAP_ID}/locations/search?latitude={p[0]}&longitude={p[1]}&distance=15"
    r=s.get(u,headers={"Referer":REFERER}); queries+=1
    for l in r.json().get("locations",[]):
        found[l["id"]]=l
    time.sleep(0.3)
print("queries",queries,"found",len(found),"overview",len(pts))
json.dump(list(found.values()),open(OUT,"w"),indent=1)
