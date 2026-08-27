from resources.lib.charset import TOFU
from resources.lib.glyphs import GlyphIndex


def fake_fs(*present):
    """present: sequence of (dir, filename) pairs that exist."""
    have = set(present)
    return lambda path: tuple(path.rsplit("/", 1)) in have


def test_first_hit_wins_in_order():
    exists = fake_fs(("cache", "t_0041.png"), ("pack", "t_0041.png"),
                     ("bundled", "t_0041.png"))
    idx = GlyphIndex(["cache", "pack", "bundled"], exists)
    assert idx.path("A", "top") == "cache/t_0041.png"


def test_falls_through_to_pack_then_bundled():
    exists = fake_fs(("pack", "t_0041.png"), ("bundled", "t_0041.png"))
    idx = GlyphIndex(["cache", "pack", "bundled"], exists)
    assert idx.path("A", "top") == "pack/t_0041.png"

    exists = fake_fs(("bundled", "t_0041.png"))
    idx = GlyphIndex(["cache", "pack", "bundled"], exists)
    assert idx.path("A", "top") == "bundled/t_0041.png"


def test_missing_character_resolves_to_tofu():
    exists = fake_fs(("bundled", "t_25a1.png"), ("bundled", "b_25a1.png"))
    idx = GlyphIndex(["bundled"], exists)
    assert idx.path("Ж", "top") == "bundled/t_25a1.png"


def test_tofu_itself_missing_raises_rather_than_looping():
    idx = GlyphIndex(["bundled"], lambda path: False)
    try:
        idx.path("A", "top")
    except LookupError as exc:
        assert TOFU in str(exc) or "tofu" in str(exc).lower()
    else:
        raise AssertionError("expected LookupError")


def test_charset_reports_characters_with_both_halves():
    exists = fake_fs(("bundled", "t_0041.png"), ("bundled", "b_0041.png"),
                     ("bundled", "t_0042.png"))  # B has no bottom half
    idx = GlyphIndex(["bundled"], exists)
    cs = idx.charset("AB")
    assert "A" in cs
    assert "B" not in cs
