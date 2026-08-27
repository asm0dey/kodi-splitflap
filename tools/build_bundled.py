"""Render the bundled glyph set. Run on a desktop; output is committed."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resources.lib.charset import bundled_charset
from resources.lib.glyphgen import render_glyphs

FONT = "assets/fonts/NimbusSans-Regular.otf"
OUT = "resources/media/glyphs"
# A half at default geometry is ~78x71; render at 2x so 4K stays crisp.
HALF_W, HALF_H = 156, 142

if __name__ == "__main__":
    written = render_glyphs(bundled_charset(), FONT, OUT, HALF_W, HALF_H)
    print(f"wrote {len(written)} files to {OUT}")
