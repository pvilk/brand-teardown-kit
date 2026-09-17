#!/usr/bin/env python3
import os, glob, json, subprocess, sys, time
from faster_whisper import WhisperModel
SHARD=int(sys.argv[1]); NSHARD=int(sys.argv[2])  # usage: transcribe_fw.py <shard> <nshard> [basedir]
BASE=sys.argv[3] if len(sys.argv)>3 else "."
VID=f"{BASE}/videos"; TR=f"{BASE}/transcripts"; AUD=f"{BASE}/audio"
os.makedirs(TR,exist_ok=True); os.makedirs(AUD,exist_ok=True)
vids=sorted(glob.glob(f"{VID}/*.mp4"))
mine=[v for i,v in enumerate(vids) if i%NSHARD==SHARD]
m=WhisperModel("base.en", device="cpu", compute_type="int8", cpu_threads=3)
print(f"shard {SHARD}: {len(mine)} clips", flush=True)
t0=time.time(); done=skip=fail=0
for i,v in enumerate(mine,1):
    aid=os.path.splitext(os.path.basename(v))[0]
    out=f"{TR}/{aid}.json"
    if os.path.exists(out): skip+=1; continue
    wav=f"{AUD}/{aid}.wav"
    r=subprocess.run(["ffmpeg","-nostdin","-v","error","-y","-i",v,"-vn","-ac","1","-ar","16000",wav],capture_output=True)
    if r.returncode!=0 or not os.path.exists(wav):
        json.dump({"id":aid,"error":"no_audio","text":""},open(out,"w")); fail+=1; continue
    try:
        segs,info=m.transcribe(wav, language="en", vad_filter=True, beam_size=1)
        segs=list(segs)
        json.dump({"id":aid,"dur":round(info.duration,1),
                   "text":"".join(s.text for s in segs).strip(),
                   "segments":[{"s":round(s.start,2),"e":round(s.end,2),"t":s.text.strip()} for s in segs]},
                  open(out,"w"), indent=1)
        done+=1
    except Exception as e:
        json.dump({"id":aid,"error":str(e)[:200],"text":""},open(out,"w")); fail+=1
    finally:
        if os.path.exists(wav): os.remove(wav)
    if i%15==0:
        el=time.time()-t0
        print(f"  s{SHARD} {i}/{len(mine)} done={done} fail={fail} {el:.0f}s ({el/max(done,1):.1f}s/clip)", flush=True)
print(f"SHARD{SHARD} DONE done={done} skip={skip} fail={fail} elapsed={time.time()-t0:.0f}s", flush=True)
