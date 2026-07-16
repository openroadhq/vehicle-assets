#!/usr/bin/env python3
"""Serial ingest daemon: staged raw PNG -> rembg cutout -> QC -> webp -> manifest.

Exactly ONE rembg at a time, process-wide, and it holds off whenever the machine
is actually short on memory (master's swap rule, 2026-07-16). Renders live in
render_worker.py and are never blocked — freezing an HTTPS request protects no
memory and just times the request out.

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
from generate import (CUTOUT_MODEL, V1, WEBP_WIDTH, ensure_venv, qc,  # noqa: E402
                      rebuild_manifest, to_webp)


MIN_FREE_PCT = 15

# A persistent cutout worker. The per-car subprocess reloaded the isnet model
# from disk every time — about half of the ~14s. Loading once and streaming
# paths over stdin keeps one cutout in flight at a time (master's rule) while
# paying the model-load cost exactly once for the whole run.
WORKER_SRC = """
import sys, warnings
warnings.filterwarnings("ignore")
from rembg import remove, new_session
from PIL import Image
W = {width}
session = new_session({model!r})
print("READY", flush=True)
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    src, dst = line.split("\\t")
    try:
        img = Image.open(src).convert("RGB")
        if img.width > W:
            img.thumbnail((W, W), Image.LANCZOS)
        remove(img, session=session, post_process_mask=True).save(dst)
        print("OK", flush=True)
    except Exception as e:
        print("ERR " + str(e).replace("\\n", " ")[:150], flush=True)
"""


class CutoutWorker:
    """One warm rembg process. Restarts itself if it ever dies."""

    def __init__(self, py: Path):
        self.py = py
        self.p: subprocess.Popen | None = None

    def _spawn(self) -> None:
        src = WORKER_SRC.format(width=WEBP_WIDTH, model=CUTOUT_MODEL)
        self.p = subprocess.Popen(
            [str(self.py), "-c", src],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1,
        )
        if (self.p.stdout.readline() or "").strip() != "READY":
            raise RuntimeError("cutout worker failed to start")

    def run(self, src: Path, dst: Path) -> None:
        if self.p is None or self.p.poll() is not None:
            self._spawn()
        assert self.p and self.p.stdin and self.p.stdout
        self.p.stdin.write(f"{src}\t{dst}\n")
        self.p.stdin.flush()
        reply = (self.p.stdout.readline() or "").strip()
        if reply != "OK":
            self.p = None  # a dead/desynced worker must not be reused
            raise RuntimeError(reply or "cutout worker died")


def free_mem_pct() -> int:
    """System-wide free memory %, per macOS's own memory_pressure tool."""
    try:
        out = subprocess.run(["memory_pressure"], capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            if "free percentage" in line:
                return int(line.rsplit(":", 1)[1].strip().rstrip("%"))
    except Exception:  # noqa: BLE001
        pass
    return 100  # can't measure -> don't self-block


def wait_for_headroom() -> None:
    """Gate the cutout on ACTUAL memory headroom, not on 'is a build running'.

    Master's swap rule (2026-07-16) exists to stop this lane from pushing the
    machine into swap death. The original proxy — pause whenever any xcodebuild
    runs — was written when a cutout meant BiRefNet: a 928MB model chewing ~278s.
    A cutout is now isnet: 0.72GB peak for ~14s (measured). Builds are near
    constant, so the proxy starved this lane to a literal 0.00 cars/min while
    the risk it guards against no longer exists. Gating on free memory honors
    the intent and does the work.
    """
    said = False
    while free_mem_pct() < MIN_FREE_PCT:
        if not said:
            print(f"   holding cutout: free memory under {MIN_FREE_PCT}%", flush=True)
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
    worker = CutoutWorker(py)
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

        wait_for_headroom()
        cut = raw.with_suffix(".cut.png")
        t = time.time()
        try:
            worker.run(raw, cut)
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
