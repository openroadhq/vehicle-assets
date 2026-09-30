"""Measure see-through windows on four-wheel cutouts.
The background remover sometimes treats pale glass as background and cuts the window out.
A transparent region fully enclosed by the vehicle is a hole; the image check rejects cars that have them."""
from pathlib import Path
from PIL import Image, ImageDraw


def enclosed(alpha):
    """Mask (L, 255 = hole) of transparent regions that do not touch the image border."""
    clear = alpha.point(lambda v: 255 if v < 128 else 0)
    padded = Image.new('L', (clear.width + 2, clear.height + 2), 255)
    padded.paste(clear, (1, 1))
    ImageDraw.floodfill(padded, (0, 0), 0)
    return padded.crop((1, 1, clear.width + 1, clear.height + 1))


def hole_pct(path):
    """Enclosed transparent area as a percent of the vehicle's solid area."""
    alpha = Image.open(path).convert('RGBA').getchannel('A')
    solid = sum(1 for v in alpha.getdata() if v >= 128)
    holes = enclosed(alpha).histogram()[255]
    return 100 * holes / solid if solid else 0.0


