#!/usr/bin/env python3
"""Vehicle asset generator: prompt -> ChatGPT image -> BiRefNet cutout -> webp + manifest.

Usage:
  tools/generate.py --car "audi/r8|silver Audi R8 V10 coupe"
  tools/generate.py --two-wheel --car "honda/cbr900rr|1998 Honda CBR900RR Fireblade sport motorcycle"
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
import re
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

# The locked style. One source of truth: realism changes happen HERE only.
PROMPT_TEMPLATE = (
    "Official press-style studio render of a {desc}. PERFECT flat side profile view, "
    "camera exactly perpendicular to the car, facing left, zero perspective angle, "
    "orthographic product-catalog look. Photorealistic, crisp studio lighting, clean "
    "reflections. Isolated on a plain solid light gray background, soft contact shadow "
    "directly under the tires only. No text, lettering, logos, badges, model names, "
    "decals, or watermark. Car centered filling "
    "85 percent of frame width."
)
CAR_STRICT_PROMPT_TEMPLATE = (
    "Official manufacturer press render of exactly one {desc}, shown as a PERFECT "
    "true left-facing side elevation. Camera exactly perpendicular to the vehicle, "
    "zero perspective, no three-quarter angle, no front view, no rear view. Include "
    "the complete vehicle in one coherent silhouette, fully inside the frame. "
    "Photorealistic catalog studio lighting and clean reflections on a plain light "
    "gray background. No text, lettering, logos, badges, model names, decals, "
    "watermark, ground, floor, or cast shadow. Centered and filling 85 percent of "
    "the frame width."
)
TWO_WHEEL_PROMPT_TEMPLATE = (
    "Official press-style studio render of a {desc}. PERFECT flat side profile view, "
    "camera exactly perpendicular to the motorcycle or scooter, facing left, zero "
    "perspective angle, orthographic product-catalog look. Photorealistic, crisp "
    "studio lighting, clean reflections. Show exactly one complete two-wheel vehicle, "
    "including both wheels, with no rider, no person, no kickstand, no luggage stand, "
    "and no extra parts. Isolated on a plain solid light gray background, soft contact "
    "shadows directly under the tires only. No text, lettering, logos, badges, model "
    "names, decals, or watermark. Vehicle centered "
    "filling 82 percent of frame width."
)
TWO_WHEEL_STRICT_PROMPT_TEMPLATE = (
    "Official manufacturer press render of exactly one {desc}, shown as a PERFECT "
    "true left-facing side elevation. Camera exactly perpendicular to the vehicle, "
    "zero perspective, no three-quarter angle, no front view, no rear view, no rider "
    "or person. Include the complete frame, handlebars, seat, engine or body, and "
    "both wheels in one coherent motorcycle or scooter silhouette. Photorealistic "
    "catalog studio lighting, crisp clean reflections, plain light gray background, "
    "subtle contact shadows under the tires only. No text, lettering, logos, badges, "
    "model names, decals, watermark, or extra "
    "vehicle, centered and fully inside the frame."
)
GEN_SIZE = "1536x1024"
WEBP_WIDTH = 1024
# Cutout model. Razpe's pick 2026-07-16: isnet is 8s/car vs birefnet's 68s and he
# judged the edges equal or better. Whole-list runtime: ~5h instead of ~8 days.
CUTOUT_MODEL = 'birefnet-general'
WEBP_QUALITY = 82


def _p(*a):
    print(*a, flush=True)


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


def wait_for_build_clear() -> None:
    """Block while any xcodebuild runs machine-wide.

    Master's swap-emergency rule (2026-07-16) is that this lane must not
    compete with another lane's build for memory. The memory cost here is
    rembg, not the HTTP render, so only the cutout waits. Suspending the
    render instead just times out its request and no car ever lands.
    """
    import time
    notified = False
    while subprocess.run(["pgrep", "-x", "xcodebuild"], capture_output=True).returncode == 0:
        if not notified:
            print("   waiting: xcodebuild active, holding cutout")
            notified = True
        time.sleep(20)


def cutout(py: Path, src: Path, dst: Path) -> None:
    # Downscale to WEBP_WIDTH before the cutout: the output is 1024px anyway, so
    # the extra source pixels cost ~30% runtime and change nothing we keep
    # (measured 2026-07-16: alpha differs on 0.23% of pixels, edge antialiasing only).
    script = (
        "import sys\n"
        "from rembg import remove, new_session\n"
        "from PIL import Image\n"
        f"W = {WEBP_WIDTH}\n"
        "img = Image.open(sys.argv[1]).convert('RGB')\n"
        "if img.width > W:\n"
        "    img.thumbnail((W, W), Image.LANCZOS)\n"
        f"out = remove(img, session=new_session('{CUTOUT_MODEL}'),"
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
        "if (box[2]-box[0]) <= (box[3]-box[1]): print('not landscape: likely not a side profile')\n"
        "bottom = a.crop((box[0], max(box[1], box[3]-12), box[2], box[3]))\n"
        "low = sum(1 for v in bottom.getdata() if 1 < v < 80)\n"
        "solid = sum(1 for v in bottom.getdata() if v >= 180)\n"
        "if low > max(20, solid * 2): print('ground shadow retained by cutout'); sys.exit(0)\n"
        "import shutil, subprocess, tempfile\n"
        "if shutil.which('tesseract'):\n"
        "    bg = Image.new('RGB', img.size, 'white'); bg.paste(img.convert('RGB'), mask=a)\n"
        "    with tempfile.NamedTemporaryFile(suffix='.png') as f:\n"
        "        bg.save(f.name)\n"
        "        ocr = subprocess.run(['tesseract', f.name, 'stdout', '--psm', '11'], capture_output=True, text=True)\n"
        "        words = [w for w in ocr.stdout.split() if sum(c.isalpha() for c in w) >= 3]\n"
        "        if words: print('text detected: ' + ' '.join(words[:4])); sys.exit(0)\n"
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


def car_tint(path: Path) -> str | None:
    """Dominant paint color of the cutout (saturation-weighted bucket of
    opaque pixels). Shipped in the manifest so the app can tint the card
    to the ACTUAL car in the image, not the user's chosen color."""
    from PIL import Image
    import collections
    im = Image.open(path).convert("RGBA").resize((128, 86))
    px = [(r, g, b) for r, g, b, a in im.getdata() if a > 200]
    if not px:
        return None
    buckets = collections.Counter((r // 32, g // 32, b // 32) for r, g, b in px)
    def score(item):
        (rb, gb, bb), n = item
        return n * (1 + (max(rb, gb, bb) - min(rb, gb, bb)) * 2)
    (rb, gb, bb), _ = max(buckets.items(), key=score)
    sel = [(r, g, b) for r, g, b in px if r // 32 == rb and g // 32 == gb and b // 32 == bb]
    r = sum(p[0] for p in sel) // len(sel)
    g = sum(p[1] for p in sel) // len(sel)
    b = sum(p[2] for p in sel) // len(sel)
    return "#%02X%02X%02X" % (r, g, b)


GEN_SUFFIX = re.compile(r"^(?P<base>.+)-(?P<year>(?:19|20)\d{2})$")


def build_generations(vehicles: dict) -> dict:
    """base slug -> [[firstModelYear, slug], ...] ascending.

    The slug scheme encodes generations: `honda/civic-2016` is the gen that
    started in 2016, and a bare `honda/civic` is the CURRENT gen. The app has
    the car's model year but no way to know when the current gen began, so it
    can't tell a 2018 Civic (gen 2016) from a 2023 one (current). We resolve
    that here and ship the answer, so the client just binary-searches a list.

    Current-gen start years come from `current-gen-years.txt` (slug|year).
    A base with no bare slug is a dead nameplate: historical gens only.
    """
    starts = {}
    f = REPO / "current-gen-years.txt"
    if f.exists():
        for line in f.read_text().splitlines():
            line = line.strip()
            if line and "|" in line and not line.startswith("#"):
                slug, year = line.split("|", 1)
                if year.strip().isdigit():
                    starts[slug.strip().lower()] = int(year.strip())

    gens: dict[str, list] = {}
    for slug in vehicles:
        m = GEN_SUFFIX.match(slug)
        if m:
            gens.setdefault(m.group("base"), []).append([int(m.group("year")), slug])
    for base in list(gens):
        if base in vehicles:  # bare slug = the current generation
            year = starts.get(base)
            if year is None:
                # No curated start year: place the current gen one year after the
                # newest historical one. Wrong-but-adjacent beats unreachable:
                # every car newer than the last known gen still lands on it.
                year = max(y for y, _ in gens[base]) + 1
            # A bare slug and a year-suffixed one can name the SAME generation
            # (e.g. audi/tt + audi/tt-2016 are both the 2016 car). Two entries
            # at one year makes the lookup ambiguous, so the bare slug, the
            # canonical "current" image, wins and the duplicate drops out.
            gens[base] = [e for e in gens[base] if e[0] != year]
            gens[base].append([year, base])
        gens[base].sort()
    return gens


def rebuild_manifest() -> None:
    vehicles = {}
    for path in sorted(V1.rglob("*.webp")):
        slug = str(path.relative_to(V1))[: -len(".webp")]
        entry = {"bytes": path.stat().st_size}
        tint = car_tint(path)
        if tint:
            entry["tint"] = tint
        vehicles[slug] = entry
    manifest = {
        "schemaVersion": 2,
        "basePath": "v1",
        "format": "webp",
        "view": "side-profile",
        "vehicles": vehicles,
        "generations": build_generations(vehicles),
    }
    existing_aliases = {}
    manifest_path = REPO / "manifest.json"
    if manifest_path.exists():
        try:
            existing_aliases = json.loads(manifest_path.read_text()).get("aliases", {})
        except (OSError, json.JSONDecodeError):
            existing_aliases = {}
    aliases = dict(existing_aliases)
    aliases_file = REPO / "aliases.json"
    if aliases_file.exists():
        proposed = json.loads(aliases_file.read_text())
        aliases.update({
            a: t for a, t in proposed.items()
            if t in vehicles or t in manifest["generations"] or t in aliases
        })
    manifest["aliases"] = dict(sorted(aliases.items()))
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    print(f"manifest: {len(vehicles)} vehicles")


def process(slug: str, desc: str, force: bool, py: Path, two_wheel: bool, strict: bool) -> bool:
    slug = slug.strip().lower()
    dst = V1 / f"{slug}.webp"
    if dst.exists() and not force:
        print(f"skip {slug} (exists)")
        return True
    _p(f"=== {slug} ===")
    with tempfile.TemporaryDirectory() as td:
        raw, cut = Path(td) / "raw.png", Path(td) / "cut.png"
        try:
            if strict:
                template = TWO_WHEEL_STRICT_PROMPT_TEMPLATE if two_wheel else CAR_STRICT_PROMPT_TEMPLATE
            else:
                template = TWO_WHEEL_PROMPT_TEMPLATE if two_wheel else PROMPT_TEMPLATE
            generate_raw(template.format(desc=desc.strip()), raw)
        except subprocess.CalledProcessError:
            _p(f"FAIL {slug}: generation errored")
            return False
        wait_for_build_clear()
        cutout(py, raw, cut)
        reason = qc(py, cut)
        if reason:
            _p(f"RETRY {slug}: QC rejected: {reason}")
            try:
                retry_template = TWO_WHEEL_STRICT_PROMPT_TEMPLATE if two_wheel else CAR_STRICT_PROMPT_TEMPLATE
                generate_raw(retry_template.format(desc=desc.strip()), raw)
                wait_for_build_clear()
                cutout(py, raw, cut)
                reason = qc(py, cut)
            except subprocess.CalledProcessError:
                _p(f"FAIL {slug}: regeneration errored")
                return False
        if reason:
            _p(f"FAIL {slug}: QC rejected: {reason}")
            return False
        to_webp(cut, dst)
    _p(f"ok {slug} ({dst.stat().st_size // 1024}KB)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--car", action="append", default=[], help="slug|description")
    ap.add_argument("--list", type=Path, help="file with slug|description lines")
    ap.add_argument("--force", action="store_true", help="regenerate even if the asset exists")
    ap.add_argument("--two-wheel", action="store_true", help="use the motorcycle or scooter side-profile prompt")
    ap.add_argument("--strict", action="store_true", help="use the no-branding strict prompt on the first attempt")
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
        failed = [slug for slug, desc in jobs if not process(slug, desc, args.force, py, args.two_wheel, args.strict)]
        if failed:
            print(f"\n{len(failed)} failed: {', '.join(failed)}")
    rebuild_manifest()
    return 0


if __name__ == "__main__":
    main()
