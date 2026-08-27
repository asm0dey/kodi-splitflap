"""The characters the bundled glyph set covers.

Capitals-only extended ASCII. Defined as an explicit codepoint list rather
than a range minus guesswork, so the uppercase-closure invariant in the
tests can be trusted.
"""
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
    chr(0x2018), chr(0x2019),  # single quotes ' '
    chr(0x201C), chr(0x201D),  # double quotes " "
    "…",  # ellipsis
    "†", "‡",  # dagger, double dagger
)

# Greek capital Mu, retained because the design spec's bundled set names it.
# Trivially closed under uppercase (Μ.upper() == Μ).
_CLOSURE = ("Μ",)

_SPECIAL = (TOFU,)


def bundled_charset() -> tuple[str, ...]:
    seen = []
    for group in (_ASCII, _LATIN1, _TYPOGRAPHIC, _CLOSURE, _SPECIAL):
        for ch in group:
            if ch not in seen:
                seen.append(ch)
    return tuple(seen)


# The drum a real board carries: blank, the alphabet, the digits, and the
# handful of marks that appear in ordinary prose. Everything else the glyph
# set can render -- accented capitals, currency, arrows, another script --
# is added to the drum on demand, the first time a board actually asks for
# it. See Drum.ensure.
#
# Keeping this small is what makes the animation read correctly. With the
# full 142-character set on the drum, Z -> A is 117 steps and gets sampled
# at stride 10, so the cell scatters through accented forms and symbols
# instead of spinning through the alphabet. At core size the same move is
# contiguous, every character shown, exactly as hardware behaves.
CORE_PUNCTUATION = " ,.:;!?-'\u2014\u00b0"


def core_drum() -> tuple[str, ...]:
    """The characters a freshly built drum starts with."""
    core = [BLANK, TOFU]
    core += [chr(c) for c in range(ord("A"), ord("Z") + 1)]
    core += [chr(c) for c in range(ord("0"), ord("9") + 1)]
    core += list(CORE_PUNCTUATION)
    seen: list[str] = []
    for ch in core:
        if ch not in seen:
            seen.append(ch)
    return tuple(seen)
