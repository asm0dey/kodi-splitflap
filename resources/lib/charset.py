"""The characters the bundled glyph set covers.

Capitals-only extended ASCII. Defined as an explicit codepoint list rather
than a range minus guesswork, so the uppercase-closure invariant in the
tests can be trusted.
"""
from typing import Tuple

BLANK = " "
TOFU = "□"

# ASCII printable, minus lowercase a-z.
_ASCII = tuple(
    chr(cp) for cp in range(0x20, 0x7F)
    if not (0x61 <= cp <= 0x7A)
)

# Latin-1 Supplement, minus lowercase. Keeps symbols (degree, plus-minus,
# multiplication, division, micro) and the accented capitals.
_LATIN1 = tuple(
    chr(cp) for cp in range(0xA0, 0x100)
    if not chr(cp).islower()
)

# CP1252 typographic extras that appear in real prose.
_TYPOGRAPHIC = (
    "€",  # euro
    "–",  # en dash
    "—",  # em dash
    "'", "'",  # single quotes
    """, """,  # double quotes
    "…",  # ellipsis
    "†", "‡",  # dagger, double dagger
)

# Greek capital Mu, retained because the design spec's bundled set names it.
# It also happens to be the uppercase target of the micro sign (µ), which
# helps satisfy the uppercase-closure invariant.
_CLOSURE = ("Μ",)

_SPECIAL = (TOFU,)


def bundled_charset():
    # type: () -> Tuple[str, ...]
    seen = []
    for group in (_ASCII, _LATIN1, _TYPOGRAPHIC, _CLOSURE, _SPECIAL):
        for ch in group:
            if ch not in seen:
                seen.append(ch)
    return tuple(seen)
