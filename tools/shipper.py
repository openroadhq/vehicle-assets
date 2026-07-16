#!/usr/bin/env python3
"""Ship whatever the ingest daemon has produced: manifest -> ledger -> git -> CDN purge.

Runs on a loop so cars go live continuously instead of piling up locally
(master's continuous-push rule, 2026-07-16). Safe to run alongside the daemon:
it only ever touches committed-ready files, and a no-op cycle costs nothing.

Usage:
  tools/shipper.py [--interval 600] [--once]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate import REPO, V1, rebuild_manifest  # noqa: E402

PURGE = "https://purge.jsdelivr.net/gh/openroadhq/vehicle-assets@main"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)


def sync_ledger() -> tuple[int, int]:
    f = REPO / "ledger.json"
    led = json.loads(f.read_text()) if f.exists() else {}
    now = time.strftime("%m-%d %H:%M")
    for slug, e in led.items():
        if (V1 / f"{slug}.webp").exists() and e.get("status") != "live":
            e.update(status="live", ts=now)
    live = sum(1 for v in led.values() if v.get("status") == "live")
    f.write_text(json.dumps(led, indent=1, sort_keys=True) + "\n")
    return live, len(led)


def ship() -> int:
    new = [l for l in git("status", "--porcelain", "v1").stdout.splitlines() if l.strip()]
    if not new:
        return 0
    rebuild_manifest()
    sync_ledger()
    slugs = [l.split("v1/", 1)[1][:-5] for l in new if l.endswith(".webp")]
    git("add", "-A")
    r = git("commit", "-q", "-m", f"assets: +{len(slugs)} cars (auto-ship)")
    if r.returncode != 0 and "nothing to commit" in (r.stdout + r.stderr):
        return 0
    push = git("push", "-q")
    if push.returncode != 0:
        print(f"push failed: {push.stderr[:200]}", flush=True)
        return 0
    for s in slugs:
        subprocess.run(["curl", "-s", "-o", "/dev/null", f"{PURGE}/v1/{s}.webp"])
    subprocess.run(["curl", "-s", "-o", "/dev/null", f"{PURGE}/manifest.json"])
    total = len(list(V1.rglob("*.webp")))
    print(f"shipped {len(slugs)} cars -> {total} live, purged", flush=True)
    return len(slugs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=600)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()
    while True:
        try:
            ship()
        except Exception as e:  # noqa: BLE001 — a shipper crash must never kill the run
            print(f"ship error (continuing): {e}", flush=True)
        if args.once:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
