#!/usr/bin/env python3
"""Serial ingest daemon: staged raw PNG -> rembg cutout -> QC -> webp -> manifest.

Exactly ONE rembg at a time, process-wide, and it waits out any machine-wide
xcodebuild before starting a cutout (master's swap rule, 2026-07-16). Renders
are elsewhere (render_worker.py) and never blocked — freezing an HTTPS request
protects no memory and just times the request out.

Usage:
  tools/ingest_daemon.py --stage /path/to/staging [--idle-exit 900]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate import V1, cutout, ensure_venv, qc, rebuild_manifest, to_webp  # noqa: E402


def build_running() -> bool:
    return subprocess.run(["pgrep", "-x", "xcodebuild"], capture_output=True).returncode == 0


def wait_for_build_clear() -> None:
    said = False
    while build_running():
        if not said:
            print("   holding cutout: xcodebuild active", flush=True)
            said = True
        time.sleep(20)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", type=Path, required=True)
    ap.add_argument("--idle-exit", type=int, default=900,
                    help="exit after this many seconds with an empty queue")
    args = ap.parse_args()
    args.stage.mkdir(parents=True, exist_ok=True)
    done_dir = args.stage / "_ingested"
    done_dir.mkdir(exist_ok=True)

    py = ensure_venv()
    ok = fail = 0
    idle_since = time.time()
    pending_manifest = False

    while True:
        pngs = sorted(p for p in args.stage.glob("*.png") if not p.name.endswith(".part"))
        if not pngs:
            if pending_manifest:
                rebuild_manifest()
                pending_manifest = False
            if time.time() - idle_since > args.idle_exit:
                print(f"idle {args.idle_exit}s — exiting. ok={ok} fail={fail}", flush=True)
                return 0
            time.sleep(10)
            continue

        idle_since = time.time()
        raw = pngs[0]
        slug = raw.stem.replace("__", "/")
        dst = V1 / f"{slug}.webp"
        if dst.exists():
            raw.rename(done_dir / raw.name)
            continue

        wait_for_build_clear()
        cut = raw.with_suffix(".cut.png")
        t = time.time()
        try:
            cutout(py, raw, cut)
            reason = qc(py, cut)
            if reason:
                print(f"FAIL {slug}: QC — {reason}", flush=True)
                fail += 1
            else:
                to_webp(cut, dst)
                ok += 1
                pending_manifest = True
                print(f"ok {slug} ({dst.stat().st_size // 1024}KB, {time.time()-t:.0f}s)", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {slug}: {e}", flush=True)
            fail += 1
        finally:
            cut.unlink(missing_ok=True)
            raw.rename(done_dir / raw.name)


if __name__ == "__main__":
    sys.exit(main())
