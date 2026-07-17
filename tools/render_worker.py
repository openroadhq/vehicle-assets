#!/usr/bin/env python3
"""Generation-only worker: prompt -> ChatGPT image -> raw PNG in a staging dir.

Split out from generate.py so the SLOW part (a ~4.5 min HTTPS render, ~0 RAM)
can run N-way parallel while the HEAVY part (rembg, RAM-bound) stays strictly
serial in ingest_daemon.py — master's swap rule, honored by construction.

Usage:
  tools/render_worker.py --list slice.txt --stage /path/to/staging [--id 1]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate import CIMG, GEN_SIZE, PROMPT_TEMPLATE, V1  # noqa: E402

# ChatGPT's image quota is a rolling window; 429 means wait, not fail.
#
# The quota is GLOBAL, not per-car: if one car 429s, every car will. So a long
# per-car backoff is worse than useless — it burns ~1h per car while the whole
# account is shut (266 cars would take ~68h). Retry briefly in case it's a
# momentary throttle, then bail out of the WHOLE worker and let supervisor.sh
# idle once and start a fresh round. Nothing is lost: the next round rebuilds
# the pending list from the filesystem, so unrendered cars simply come back.
MAX_429_RETRIES = 3
BACKOFF_BASE = 20          # 20s, 40s, 80s — ~2min before we call the quota shut
QUOTA_SHUT_EXIT = 42       # exit code supervisor.sh reads as "quota is closed"


def already_done(slug: str, stage: Path) -> bool:
    return (V1 / f"{slug}.webp").exists() or (stage / f"{slug.replace('/', '__')}.png").exists()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", type=Path, required=True)
    ap.add_argument("--stage", type=Path, required=True)
    ap.add_argument("--id", default="0")
    args = ap.parse_args()
    args.stage.mkdir(parents=True, exist_ok=True)

    jobs = []
    for line in args.list.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "|" in line:
            slug, desc = line.split("|", 1)
            jobs.append((slug.strip().lower(), desc.strip()))

    ok = fail = skip = 0
    for slug, desc in jobs:
        if already_done(slug, args.stage):
            skip += 1
            continue
        out = args.stage / f"{slug.replace('/', '__')}.png"
        tmp = out.with_suffix(".part")
        t = time.time()
        # A 429 is "come back later", not "this car is broken". The first run
        # burned ~1,192 cars by treating it as fatal and walking on — they were
        # simply never rendered, and the run would have looked complete. Back off
        # and retry; only give up on a genuine error.
        for attempt in range(MAX_429_RETRIES):
            try:
                subprocess.run(
                    [str(CIMG), PROMPT_TEMPLATE.format(desc=desc), "-o", str(tmp),
                     "--size", GEN_SIZE, "--timeout", "300", "--quiet"],
                    check=True, capture_output=True,
                )
                tmp.rename(out)  # atomic: the daemon only ever sees complete files
                ok += 1
                print(f"[w{args.id}] ok {slug} ({time.time()-t:.0f}s)", flush=True)
                break
            except subprocess.CalledProcessError as e:
                tmp.unlink(missing_ok=True)
                err = (e.stderr.decode() if e.stderr else "") + (e.stdout.decode() if e.stdout else "")
                if "429" in err or "usage_limit" in err or "Rate limit" in err:
                    if attempt == MAX_429_RETRIES - 1:
                        # Quota is shut account-wide — every remaining car would
                        # 429 too. Stop the worker; supervisor.sh idles and
                        # re-rounds. This car stays pending and comes back.
                        print(f"[w{args.id}] QUOTA SHUT at {slug} — "
                              f"rendered={ok} this run, {len(jobs)-ok-fail-skip} still pending",
                              flush=True)
                        return QUOTA_SHUT_EXIT
                    wait = BACKOFF_BASE * (2 ** attempt)
                    print(f"[w{args.id}] 429 on {slug} — retrying in {wait}s", flush=True)
                    time.sleep(wait)
                    continue
                fail += 1
                print(f"[w{args.id}] FAIL {slug}: {err[:120] or 'gen error'}", flush=True)
                break
            except Exception as e:  # noqa: BLE001
                fail += 1
                tmp.unlink(missing_ok=True)
                print(f"[w{args.id}] FAIL {slug}: {e}", flush=True)
                break
    print(f"[w{args.id}] DONE rendered={ok} failed={fail} skipped={skip}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
