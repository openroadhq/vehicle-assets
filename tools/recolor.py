#!/usr/bin/env python3
"""Repaint a car cutout — PROTOTYPE / reference implementation.

This is proof-of-concept for doing it ON DEVICE (Core Image / Metal kernel):
the whole thing is per-pixel arithmetic, no model, ~ms on any iOS 18 device.
Shipping it here would mean 8x the images for no benefit; the app already has
the user's colorHex and the manifest already carries every car's real paint.

How it works: replace hue+saturation on paint pixels ONLY, keep each pixel's
own VALUE. Metallic falloff, highlights, reflections and shadows all live in V,
so they survive — the result is repainted, not filled in. Glass/tyres/chrome
are excluded by saturation, and anything whose hue is far from the source paint
is left alone (so black mirrors stay black; body-coloured mirrors recolour,
which is correct).

Usage: tools/recolor.py v1/bmw/m2.webp '#2A5CAA' out.png
"""
from __future__ import annotations

import colorsys
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
PAINT_SAT_MIN = 0.22   # below this it's glass, chrome, tyre or shadow
PAINT_VAL_MIN = 0.10   # below this there's no colour information to rotate
HUE_WINDOW = 0.12      # how far from the source paint hue still counts as body


def _hsv_planes(rgb: np.ndarray):
    mx, mn = rgb.max(2), rgb.min(2)
    d = mx - mn
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.zeros_like(mx)
    m = (mx == r) & (d > 1e-6); h[m] = ((g - b)[m] / d[m]) % 6
    m = (mx == g) & (d > 1e-6); h[m] = ((b - r)[m] / d[m]) + 2
    m = (mx == b) & (d > 1e-6); h[m] = ((r - g)[m] / d[m]) + 4
    return (h / 6.0) % 1.0, s, mx


def recolor(img: Image.Image, src_hex: str, dst_hex: str) -> Image.Image:
    a = np.array(img.convert("RGBA")).astype(np.float32)
    rgb, alpha = a[..., :3] / 255.0, a[..., 3]
    h, s, v = _hsv_planes(rgb)
    sh, ss, sv = colorsys.rgb_to_hsv(*(int(src_hex[i:i + 2], 16) / 255 for i in (1, 3, 5)))
    dr, dg, db = (int(dst_hex[i:i + 2], 16) / 255 for i in (1, 3, 5))
    dh, ds, dv = colorsys.rgb_to_hsv(dr, dg, db)

    hue_dist = np.minimum(np.abs(h - sh), 1 - np.abs(h - sh))
    paint = (alpha > 200) & (s > PAINT_SAT_MIN) & (v > PAINT_VAL_MIN) & (hue_dist < HUE_WINDOW)

    out = rgb.copy()
    vv = np.clip(v * (dv / max(sv, 1e-3)), 0, 1)
    if ds < 0.10:
        # White / black / silver have no hue to rotate to — drive value instead.
        mxc = max(dr, dg, db, 1e-3)
        for c, ch in enumerate((dr, dg, db)):
            out[..., c] = np.where(paint, vv * ch / mxc, out[..., c])
    else:
        ss2 = np.clip(s * (ds / max(ss, 1e-3)), 0, 1)
        i6 = int(dh * 6) % 6
        f = dh * 6 - int(dh * 6)
        p, q, t = vv * (1 - ss2), vv * (1 - f * ss2), vv * (1 - (1 - f) * ss2)
        rr, gg, bb = {0: (vv, t, p), 1: (q, vv, p), 2: (p, vv, t),
                      3: (p, q, vv), 4: (t, p, vv), 5: (vv, p, q)}[i6]
        for c, ch in enumerate((rr, gg, bb)):
            out[..., c] = np.where(paint, ch, out[..., c])
    return Image.fromarray(np.dstack([np.clip(out * 255, 0, 255), alpha]).astype(np.uint8), "RGBA")


def main() -> int:
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    src, dst_hex, out = Path(sys.argv[1]).resolve(), sys.argv[2], Path(sys.argv[3])
    slug = str(src.relative_to(REPO / "v1"))[:-len(src.suffix)]
    tint = json.loads((REPO / "manifest.json").read_text())["vehicles"][slug].get("tint")
    if not tint:
        sys.exit(f"no stored tint for {slug} — can't know its source paint")
    recolor(Image.open(src), tint, dst_hex).save(out)
    print(f"{slug}: {tint} -> {dst_hex} -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
