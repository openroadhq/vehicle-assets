#!/usr/bin/env python3
"""Ingest pre-generated raw car renders (e.g. Higgsfield) into the asset pipeline.

Same cutout -> QC -> webp -> manifest path as generate.py, minus generation.
Strictly serial (one rembg at a time — swap-emergency rule, 2026-07-16).

Usage:
  tools/ingest.py "toyota/camry|/path/to/raw.png" ["slug|path" ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate import V1, cutout, ensure_venv, qc, rebuild_manifest, to_webp  # noqa: E402


def main() -> int:
    jobs = []
    for spec in sys.argv[1:]:
        if "|" not in spec:
            sys.exit(f"error: bad spec (need slug|rawpath): {spec}")
        slug, raw = spec.split("|", 1)
        raw_path = Path(raw)
        if not raw_path.exists():
            sys.exit(f"error: raw file missing: {raw}")
        jobs.append((slug.strip().lower(), raw_path))
    if not jobs:
        sys.exit("error: no jobs given")

    py = ensure_venv()
    failed = []
    for slug, raw in jobs:
        cut = raw.with_suffix(".cut.png")
        cutout(py, raw, cut)
        reason = qc(py, cut)
        if reason:
            print(f"FAIL {slug}: QC rejected — {reason}")
            failed.append(slug)
            cut.unlink(missing_ok=True)
            continue
        dst = V1 / f"{slug}.webp"
        to_webp(cut, dst)
        cut.unlink(missing_ok=True)
        print(f"ok {slug} ({dst.stat().st_size // 1024}KB)")
    rebuild_manifest()
    if failed:
        print(f"{len(failed)} failed: {', '.join(failed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
