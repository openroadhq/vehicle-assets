#!/usr/bin/env python3
"""Vehicle asset generator: prompt -> ChatGPT image -> BiRefNet cutout -> webp + manifest.

Usage:
  tools/generate.py --car "audi/r8|silver Audi R8 V10 coupe"
  tools/generate.py --list cars.txt            # lines of slug|description
  tools/generate.py --rebuild-manifest

Free by design: generation uses the ChatGPT subscription CLI (no API key),
cutout runs locally (BiRefNet). Requires: tools/.venv with rembg (auto-created),
cwebp, and the chatgpt-imagegen CLI (env CIMG overrides the default path).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
V1 = REPO / "v1"
VENV = REPO / "tools" / ".venv"
CIMG = Path(os.environ.get(
    "CIMG", Path.home() / "Desktop/Galahad/tools/chatgpt-imagegen/chatgpt-imagegen"
))

# The locked style. One source of truth — realism changes happen HERE only.
PROMPT_TEMPLATE = (
    "Official press-style studio render of a {desc}. PERFECT flat side profile view, "
    "camera exactly perpendicular to the car, facing left, zero perspective angle, "
    "orthographic product-catalog look. Photorealistic, crisp studio lighting, clean "
    "reflections. Isolated on a plain solid light gray background, soft contact shadow "
    "directly under the tires only, no text, no watermark, car centered filling "
    "85 percent of frame width."
)
GEN_SIZE = "1536x1024"
WEBP_WIDTH = 1024
WEBP_QUALITY = 82


def die(msg: str) -> None:
    sys.exit(f"error: {msg}")


def ensure_venv() -> Path:
    py = VENV / "bin" / "python"
    if py.exists():
        return py
    print("-> creating venv with rembg (one-time)")
    subprocess.run([sys.executable, "-m", "venv", str(VENV)], check=True)
    subprocess.run([str(VENV / "bin" / "pip"), "-q", "install", "rembg[cpu]"], check=True)
    return py


def generate_raw(prompt: str, out: Path) -> None:
    subprocess.run(
        [str(CIMG), prompt, "-o", str(out), "--size", GEN_SIZE, "--timeout", "300", "--quiet"],
        check=True,
    )


def cutout(py: Path, src: Path, dst: Path) -> None:
    script = (
        "import sys\n"
        "from rembg import remove, new_session\n"
        "from PIL import Image\n"
        "out = remove(Image.open(sys.argv[1]), session=new_session('birefnet-general'),"
        " post_process_mask=True)\n"
        "out.save(sys.argv[2])\n"
    )
    subprocess.run([str(py), "-c", script, str(src), str(dst)], check=True)


def qc(py: Path, png: Path) -> str | None:
    """Heuristic gate. Returns a rejection reason or None if the image passes."""
    script = (
        "import sys\n"
        "from PIL import Image\n"
        "img = Image.open(sys.argv[1]).convert('RGBA')\n"
        "a = img.getchannel('A')\n"
        "box = a.getbbox()\n"
        "if not box: print('empty alpha'); sys.exit(0)\n"
        "w, h = img.size\n"
        "cov = (box[2]-box[0]) * (box[3]-box[1]) / (w*h)\n"
        "if cov < 0.15: print(f'subject too small ({cov:.0%})'); sys.exit(0)\n"
        "if box[0] <= 1 or box[2] >= w-1: print('subject clipped horizontally'); sys.exit(0)\n"
        "if (box[2]-box[0]) <= (box[3]-box[1]): print('not landscape — likely not a side profile')\n"
    )
    res = subprocess.run([str(py), "-c", script, str(png)], capture_output=True, text=True)
    reason = res.stdout.strip()
    return reason or None


def to_webp(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["cwebp", "-q", str(WEBP_QUALITY), "-resize", str(WEBP_WIDTH), "0", "-exact",
         str(src), "-o", str(dst)],
        check=True, capture_output=True,
    )


def rebuild_manifest() -> None:
    vehicles = {}
    for path in sorted(V1.rglob("*.webp")):
        slug = str(path.relative_to(V1))[: -len(".webp")]
        vehicles[slug] = {"bytes": path.stat().st_size}
    manifest = {
        "schemaVersion": 1,
        "basePath": "v1",
        "format": "webp",
        "view": "side-profile",
        "vehicles": vehicles,
    }
    aliases_file = REPO / "aliases.json"
    if aliases_file.exists():
        aliases = json.loads(aliases_file.read_text())
        manifest["aliases"] = {a: t for a, t in sorted(aliases.items()) if t in vehicles}
    (REPO / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(f"manifest: {len(vehicles)} vehicles")


def process(slug: str, desc: str, force: bool, py: Path) -> bool:
    slug = slug.strip().lower()
    dst = V1 / f"{slug}.webp"
    if dst.exists() and not force:
        print(f"skip {slug} (exists)")
        return True
    print(f"=== {slug} ===")
    with tempfile.TemporaryDirectory() as td:
        raw, cut = Path(td) / "raw.png", Path(td) / "cut.png"
        try:
            generate_raw(PROMPT_TEMPLATE.format(desc=desc.strip()), raw)
        except subprocess.CalledProcessError:
            print(f"FAIL {slug}: generation errored")
            return False
        cutout(py, raw, cut)
        reason = qc(py, cut)
        if reason:
            print(f"FAIL {slug}: QC rejected — {reason}")
            return False
        to_webp(cut, dst)
    print(f"ok {slug} ({dst.stat().st_size // 1024}KB)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--car", action="append", default=[], help="slug|description")
    ap.add_argument("--list", type=Path, help="file with slug|description lines")
    ap.add_argument("--force", action="store_true", help="regenerate even if the asset exists")
    ap.add_argument("--rebuild-manifest", action="store_true")
    args = ap.parse_args()

    jobs: list[tuple[str, str]] = []
    for spec in args.car:
        if "|" not in spec:
            die(f"bad --car spec (need slug|description): {spec}")
        slug, desc = spec.split("|", 1)
        jobs.append((slug, desc))
    if args.list:
        for line in args.list.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" not in line:
                die(f"bad line in {args.list}: {line}")
            slug, desc = line.split("|", 1)
            jobs.append((slug, desc))

    if not jobs and not args.rebuild_manifest:
        ap.print_help()
        return 1

    if jobs:
        if not CIMG.exists():
            die(f"chatgpt-imagegen not found at {CIMG} (set CIMG)")
        py = ensure_venv()
        failed = [slug for slug, desc in jobs if not process(slug, desc, args.force, py)]
        if failed:
            print(f"\n{len(failed)} failed: {', '.join(failed)}")
    rebuild_manifest()
    return 0


if __name__ == "__main__":
    main()
