"""Validate and format Kodi ARGB colour strings.

colorDiffuse / setColorDiffuse take an opaque 'AARRGGBB' hex string. The
letter/accent colours are free-text settings a user can type anything into,
so this validates the 'RRGGBB' shape before formatting rather than trusting
the field -- a short string, stray characters, or a doubled '#' would
otherwise become a silently-wrong tint with no error and no log.

Pure: this module never imports xbmc, so it can't log a bad value itself.
`to_argb` returns None on anything invalid; the Kodi shell that calls it is
the one place with a logger, and decides the fallback.
"""
import re

_HEX6 = re.compile(r"^#?([0-9A-Fa-f]{6})$")

# Opaque white. Deliberately not a colour anywhere in the intended theme
# (near-black cards, muted letter/accent tints), so a fallback tile reads as
# obviously wrong on screen rather than blending in as "close enough".
FALLBACK_ARGB = "FFFFFFFF"


def to_argb(hex_rgb: str) -> str | None:
    """Convert 'RRGGBB' or '#RRGGBB' to opaque Kodi 'AARRGGBB'.

    Returns None for anything that isn't exactly 6 hex digits with at most
    one leading '#': empty, wrong length, non-hex characters, a doubled
    '#', surrounding whitespace, etc.
    """
    match = _HEX6.match(hex_rgb)
    if match is None:
        return None
    return "FF" + match.group(1).upper()
