from resources.lib.charset import BLANK, TOFU, bundled_charset


def test_blank_and_tofu_are_present():
    cs = set(bundled_charset())
    assert BLANK == " "
    assert TOFU == "□"
    assert BLANK in cs
    assert TOFU in cs


def test_is_capitals_only():
    cs = bundled_charset()
    assert not [c for c in cs if c.islower()]


def test_contains_ascii_digits_and_capitals():
    cs = set(bundled_charset())
    for c in "ABCXYZ0189":
        assert c in cs


def test_contains_degree_and_ellipsis():
    cs = set(bundled_charset())
    assert "°" in cs   # weather renders 17 deg RAIN
    assert "…" in cs   # layout ellipsises with this


def test_uppercase_closure_per_character():
    """Every character of c.upper() must itself be bundled.

    The per-character form matters: comparing c.upper() as a whole would
    wrongly fail the sharp s, whose 'SS' is fine, while missing the real
    gap, micro sign, which uppercases to a single Greek capital Mu.
    """
    cs = set(bundled_charset())
    for c in cs:
        for out in c.upper():
            assert out in cs, f"{c!r} uppercases to {out!r} which is not bundled"


def test_no_duplicates():
    cs = bundled_charset()
    assert len(cs) == len(set(cs))


def test_every_entry_is_a_single_character():
    for ch in bundled_charset():
        assert len(ch) == 1, f"{ch!r} is {len(ch)} characters, not 1"


def test_contains_curly_quotes():
    cs = set(bundled_charset())
    for ch in "''""":
        assert ch in cs
