"""Rasterise a font into split-flap tile halves.

One rasteriser, three callers: the bundled build, the pack builder, and the
guarded runtime path. Keeping it single-sourced is what stops the three
drifting apart visually.

Cards and their shading are baked into the greyscale image; a colordiffuse
tint is applied by Kodi at runtime.
"""
import os
from collections.abc import Iterable

CARD_VALUE = 24        # near-black card, so a tint barely moves it
LETTER_VALUE = 232     # light letterform, so a tint colours it
HINGE_VALUE = 8         # the seam between halves


def glyph_filename(ch: str, half: str) -> str:
    prefix = "t" if half == "top" else "b"
    return "%s_%04x.png" % (prefix, ord(ch))


def render_glyphs(
    chars: Iterable[str], font_path: str, out_dir: str, half_w: int, half_h: int
) -> list[str]:
    """Render each character as a top and a bottom half. Returns filenames."""
    from PIL import Image, ImageDraw, ImageFont

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    chars = list(chars)
    full_h = half_h * 2
    # Target a capital height of about 55% of the full card, then shrink
    # further if any character in this set would overflow the card width
    # at that size (W, M, @, and the em dash are all wider than their own
    # cap height, so the final size can land well under the 55% target).
    size = _fit_font_size(font_path, full_h, half_w, chars)
    font = ImageFont.truetype(font_path, size)

    written = []
    for ch in chars:
        card = Image.new("L", (half_w, full_h), CARD_VALUE)
        draw = ImageDraw.Draw(card)
        _draw_centred(draw, ch, font, half_w, full_h)
        draw.line([(0, half_h - 1), (half_w, half_h - 1)], fill=HINGE_VALUE, width=2)

        for half, box in (
            ("top", (0, 0, half_w, half_h)),
            ("bottom", (0, half_h, half_w, full_h)),
        ):
            name = glyph_filename(ch, half)
            card.crop(box).convert("L").save(os.path.join(out_dir, name), "PNG")
            written.append(name)
    return written


def _fit_font_size(font_path: str, full_h: int, half_w: int, chars: Iterable[str]) -> int:
    from PIL import ImageFont

    target = int(full_h * 0.55)
    size = target
    for _ in range(24):
        font = ImageFont.truetype(font_path, size)
        box = font.getbbox("H")
        cap = box[3] - box[1]
        if cap == 0:
            break
        if abs(cap - target) <= 1:
            break
        size = max(4, int(size * target / float(cap)))

    # A card is often narrower than it is tall, and some glyphs (W, M, @,
    # the em dash) are wider than their own cap height. Re-check every
    # character in this render's set and shrink further if the widest one
    # would overflow the card width, leaving a small margin either side.
    max_width_budget = half_w * 0.94
    font = ImageFont.truetype(font_path, size)
    widest = 0
    for ch in chars:
        box = font.getbbox(ch)
        widest = max(widest, box[2] - box[0])
    if widest > max_width_budget > 0:
        size = max(4, int(size * max_width_budget / float(widest)))
    return size


def _draw_centred(draw, ch: str, font, w: int, h: int) -> None:
    box = draw.textbbox((0, 0), ch, font=font)
    x = (w - (box[2] - box[0])) / 2.0 - box[0]
    y = (h - (box[3] - box[1])) / 2.0 - box[1]
    draw.text((x, y), ch, fill=LETTER_VALUE, font=font)
