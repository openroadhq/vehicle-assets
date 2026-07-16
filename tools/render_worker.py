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
        try:
            subprocess.run(
                [str(CIMG), PROMPT_TEMPLATE.format(desc=desc), "-o", str(tmp),
                 "--size", GEN_SIZE, "--timeout", "300", "--quiet"],
                check=True, capture_output=True,
            )
            tmp.rename(out)  # atomic: the daemon only ever sees complete files
            ok += 1
            print(f"[w{args.id}] ok {slug} ({time.time()-t:.0f}s)", flush=True)
        except subprocess.CalledProcessError as e:
            fail += 1
            tmp.unlink(missing_ok=True)
            print(f"[w{args.id}] FAIL {slug}: {e.stderr.decode()[:120] if e.stderr else 'gen error'}", flush=True)
        except Exception as e:  # noqa: BLE001
            fail += 1
            tmp.unlink(missing_ok=True)
            print(f"[w{args.id}] FAIL {slug}: {e}", flush=True)
    print(f"[w{args.id}] DONE rendered={ok} failed={fail} skipped={skip}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
