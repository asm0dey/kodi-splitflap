"""Rasterise a font into split-flap tile halves.

One rasteriser, three callers: the bundled build, the pack builder, and the
guarded runtime path. Keeping it single-sourced is what stops the three
drifting apart visually.

Cards and their shading are baked into the greyscale image; a colordiffuse
tint is applied by Kodi at runtime.
"""
import os
from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # PIL is a build-time dependency, imported lazily at runtime
    from PIL.Image import Image

CARD_VALUE = 24        # near-black card, so a tint barely moves it
LETTER_VALUE = 232     # light letterform, so a tint colours it
HINGE_VALUE = 8         # the seam between halves

# Depth cues, baked in at build time so painting costs nothing at runtime.
# All three survive tinting: Kodi multiplies colorDiffuse over the greyscale,
# so shading rides along with the colour instead of fighting it.
EDGE_LIGHT = 14         # catch-light on each half's own top edge
FACE_FALLOFF = 10       # each half is top-lit and falls away downward
FACE_SHADE = 4          # ...and darkens slightly toward its own bottom
FLAP_SHADOW = 14        # the upper flap's shadow cast onto the lower half
FLAP_SHADOW_ROWS = 18   # how far that shadow reaches down

# The accent tile is a LIGHT card, and it has to be. colorDiffuse multiplies,
# so tinting the near-black card above can only ever darken it -- 24 x #2B5CE6
# is RGB(4, 8, 21), which is black. A light card gives the tint something to
# multiply into: 235 x #2B5CE6 is RGB(39, 84, 211), a solid blue tile like the
# one on a real board.
ACCENT_CARD_VALUE = 235

# The hardware that holds a flap on its axle, copied from a photograph of a
# real board: a retaining notch cut into the top edge, and lugs along both
# side edges clustered around the hinge. Without them the tiles read as
# free-floating rectangles -- there is nothing saying they are mounted on
# anything.
NOTCH_VALUE = 6         # cut into the card, so darker than the face
NOTCH_W_FRAC = 0.10     # of the tile width
NOTCH_H_FRAC = 0.15     # of one half's height
LUG_VALUE = 10
LUG_W_FRAC = 0.055
LUG_H_FRAC = 0.085
ACCENT_NAME = "accent"


def accent_filename(half: str) -> str:
    """The accent tile's texture name. Not a character, so not codepoint-named."""
    return f"{'t' if half == 'top' else 'b'}_{ACCENT_NAME}.png"


def render_accent(out_dir: str, half_w: int, half_h: int) -> list[str]:
    """Render the accent tile: a light, blank card carrying the hinge.

    Light because colorDiffuse multiplies -- see ACCENT_CARD_VALUE.
    """
    from PIL import Image, ImageDraw

    full_h = half_h * 2
    card = Image.new("L", (half_w, full_h), ACCENT_CARD_VALUE)
    draw = ImageDraw.Draw(card)
    for half_top in (0, half_h):
        for y in range(half_h):
            t = y / half_h
            draw.line([(0, half_top + y), (half_w, half_top + y)],
                      fill=max(0, ACCENT_CARD_VALUE - int(18 * t)))
    for y in range(min(FLAP_SHADOW_ROWS, half_h)):
        t = y / FLAP_SHADOW_ROWS
        draw.line([(0, half_h + y), (half_w, half_h + y)],
                  fill=max(0, ACCENT_CARD_VALUE - int(30 * (1 - t) ** 1.5)))
    draw.line([(0, half_h - 1), (half_w, half_h - 1)],
              fill=max(0, ACCENT_CARD_VALUE - 60), width=2)

    written = []
    for half, box in (("top", (0, 0, half_w, half_h)),
                      ("bottom", (0, half_h, half_w, full_h))):
        name = accent_filename(half)
        card.crop(box).convert("L").save(os.path.join(out_dir, name), "PNG")
        written.append(name)
    return written


CASING_TOP = 34         # the housing, lit from above
CASING_BOTTOM = 18
WELL_VALUE = 8          # the recess the tile field sits in


def render_frame(out_dir: str, height: int = 1080) -> list[str]:
    """Render the housing textures the board is mounted in.

    Two pieces, both stretchable without distortion so one set works at any
    row count: a vertical gradient for the casing, and a flat white pixel
    the renderer tints for the recessed well and its lip. Drawing the frame
    from stretched solids rather than one big picture is what keeps it
    independent of the geometry, which changes with the rows setting.
    """
    from PIL import Image, ImageDraw

    casing = Image.new("L", (4, height))
    draw = ImageDraw.Draw(casing)
    for y in range(height):
        t = y / height
        draw.line([(0, y), (4, y)],
                  fill=int(CASING_TOP + (CASING_BOTTOM - CASING_TOP) * t))
    casing.save(os.path.join(out_dir, "frame_casing.png"), "PNG")

    Image.new("L", (1, 1), 255).save(os.path.join(out_dir, "white.png"), "PNG")
    return ["frame_casing.png", "white.png"]


def render_plate(out_dir: str, font_path: str, text: str = "KODI",
                 width: int = 420, height: int = 64) -> list[str]:
    """The maker's plate on the casing, as a real board carries.

    Wide letter-spacing, all caps, dim against the housing -- the way a
    brand was screen-printed onto equipment in the era this board is from.
    The reference photograph carries its own plate in the same position.
    """
    from PIL import Image, ImageDraw, ImageFont

    plate = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(plate)
    size = int(height * 0.46)
    font = ImageFont.truetype(font_path, size)

    tracked = " ".join(text)            # 80s equipment lettering is airy
    box = draw.textbbox((0, 0), tracked, font=font)
    x = (width - (box[2] - box[0])) / 2 - box[0]
    y = (height - (box[3] - box[1])) / 2 - box[1]
    draw.text((x, y), tracked, fill=190, font=font)

    # a hairline rule either side, stopping short of the text
    rule_y = height // 2
    pad = (box[2] - box[0]) / 2 + size * 0.9
    draw.line([(width / 2 - pad - size * 1.6, rule_y),
               (width / 2 - pad, rule_y)], fill=90)
    draw.line([(width / 2 + pad, rule_y),
               (width / 2 + pad + size * 1.6, rule_y)], fill=90)

    plate.save(os.path.join(out_dir, "frame_plate.png"), "PNG")
    return ["frame_plate.png"]


def glyph_filename(ch: str, half: str) -> str:
    prefix = "t" if half == "top" else "b"
    return f"{prefix}_{ord(ch):04x}.png"


def render_glyphs(
    chars: Iterable[str], font_path: str, out_dir: str, half_w: int, half_h: int
) -> list[str]:
    """Render each character as a top and a bottom half. Returns filenames."""
    from PIL import ImageDraw, ImageFont

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
        card = _shaded_card(half_w, half_h, full_h)
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


def _shaded_card(half_w: int, half_h: int, full_h: int) -> "Image":
    """A two-half card with the depth cues a real split-flap board has.

    Three of them, in order of how much they matter:

    1. The upper flap casts a shadow onto the top of the lower half. This is
       the only cue that says one card sits in FRONT of another, which is
       what makes a tile read as stacked cards rather than one square with a
       line through it.
    2. Each half is top-lit -- brightest at its own top edge, falling away
       downward -- so the two halves read as two separate faces.
    3. A catch-light on each half's top edge gives the card an edge rather
       than a fade into the background.
    """
    from PIL import Image, ImageDraw

    card = Image.new("L", (half_w, full_h), CARD_VALUE)
    draw = ImageDraw.Draw(card)

    for half_top in (0, half_h):
        for y in range(half_h):
            t = y / half_h
            value = CARD_VALUE + int(FACE_FALLOFF * (1 - t) ** 1.6)
            value -= int(FACE_SHADE * t)
            draw.line([(0, half_top + y), (half_w, half_top + y)],
                      fill=max(0, value))

    for y in range(min(FLAP_SHADOW_ROWS, half_h)):
        t = y / FLAP_SHADOW_ROWS
        draw.line([(0, half_h + y), (half_w, half_h + y)],
                  fill=max(0, CARD_VALUE - int(FLAP_SHADOW * (1 - t) ** 1.5)))

    for half_top in (0, half_h):
        draw.line([(0, half_top), (half_w, half_top)], fill=CARD_VALUE + EDGE_LIGHT)

    _draw_mounting(draw, half_w, half_h, full_h, CARD_VALUE)
    return card


def _draw_mounting(draw, half_w: int, half_h: int, full_h: int,
                   card_value: int) -> None:
    """The notch and side lugs that mount a flap on its axle.

    Drawn on both halves so a tile reads as hardware from either face, and
    positioned around the hinge because that is where a real flap is held.
    """
    notch_w = max(2, int(half_w * NOTCH_W_FRAC))
    notch_h = max(2, int(half_h * NOTCH_H_FRAC))
    x0 = (half_w - notch_w) // 2
    for half_top in (0, half_h):
        draw.rectangle([x0, half_top, x0 + notch_w, half_top + notch_h],
                       fill=NOTCH_VALUE)

    lug_w = max(1, int(half_w * LUG_W_FRAC))
    lug_h = max(2, int(half_h * LUG_H_FRAC))
    # Two lugs per side per half, sitting either side of the hinge.
    for cy in (half_h - int(half_h * 0.34), half_h - int(half_h * 0.10),
               half_h + int(half_h * 0.10), half_h + int(half_h * 0.34)):
        top = max(0, min(full_h - lug_h, cy - lug_h // 2))
        draw.rectangle([0, top, lug_w, top + lug_h], fill=LUG_VALUE)
        draw.rectangle([half_w - lug_w, top, half_w, top + lug_h],
                       fill=LUG_VALUE)


def _fit_font_size(font_path: str, full_h: int, half_w: int,
                   chars: Iterable[str]) -> int:
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
