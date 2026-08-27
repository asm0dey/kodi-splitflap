"""Render the bundled glyph set. Run on a desktop; output is committed."""
import os
import sys

# The add-on directory is an import root, not a package -- its name has dots
# in it. Putting it on the path is what lets these tools import
# `resources.lib.*` exactly as the add-on does at runtime.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "screensaver.splitflap"))

from resources.lib.charset import bundled_charset
from resources.lib.glyphgen import (
    render_accent,
    render_frame,
    render_glyphs,
    render_plate,
)

FONT = "assets/fonts/NimbusSans-Bold.otf"   # repo-relative; run from the root
OUT = "screensaver.splitflap/resources/media/glyphs"
# A half at default geometry is ~78x71; render at 2x so 4K stays crisp.
HALF_W, HALF_H = 156, 142

if __name__ == "__main__":
    written = render_glyphs(bundled_charset(), FONT, OUT, HALF_W, HALF_H)
    written += render_accent(OUT, HALF_W, HALF_H)
    written += render_frame(OUT)
    written += render_plate(OUT, FONT)
    print(f"wrote {len(written)} files to {OUT}")
