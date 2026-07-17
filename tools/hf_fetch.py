#!/usr/bin/env python3
"""Given a jobid->slug map, find each render's CDN URL by probing timestamps,
download it, and print `slug|path` lines for ingest. Avoids the huge
show_generations JSON entirely — the URL is hf_<date>_<HHMMSS>_<jobid>.png and
renders land within ~2min of firing, so a small window brute-forces cleanly.

Usage: hf_fetch.py <mapfile> <YYYYMMDD> <HHMM-start> <stage-dir> [window-min]
map lines: "<jobid> <slug>"
"""
import subprocess, sys, concurrent.futures
from pathlib import Path

BASE = "https://d8j0ntlcm91z4.cloudfront.net/user_39U2nakOhBeRGNTDnmOrk0dZChx"
mapf, date, hhmm, stage = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4])
win = int(sys.argv[5]) if len(sys.argv) > 5 else 4
stage.mkdir(parents=True, exist_ok=True)
jobs = [l.split() for l in Path(mapf).read_text().splitlines() if l.strip()]
h0, m0 = int(hhmm[:2]), int(hhmm[2:])
stamps = []
for dm in range(win):
    mm = m0 + dm
    for s in range(60):
        stamps.append(f"{h0 + mm//60:02d}{mm%60:02d}{s:02d}")

def find(job):
    jid, slug = job
    def probe(ts):
        url = f"{BASE}/hf_{date}_{ts}_{jid}.png"
        r = subprocess.run(["curl","-s","-o","/dev/null","-w","%{http_code}","-I",url],
                           capture_output=True, text=True, timeout=15)
        return url if r.stdout.strip() == "200" else None
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        for u in ex.map(probe, stamps):
            if u:
                out = stage / f"{slug.replace('/','__')}.png"
                subprocess.run(["curl","-s","-o",str(out),u])
                return f"{slug}|{out}"
    return None

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    got = [r for r in ex.map(find, jobs) if r]
Path(str(stage)+"-ingest.txt").write_text("\n".join(got)+"\n")
print(f"found {len(got)}/{len(jobs)}")
