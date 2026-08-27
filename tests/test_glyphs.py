from resources.lib.charset import TOFU
from resources.lib.glyphs import GlyphIndex, glyph_dirs


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


def test_repeated_lookups_probe_the_filesystem_only_once():
    """paint() calls path() for the same characters over and over across a
    board transition -- up to ~40 times per 200ms step. Without memoisation,
    N identical lookups over a chain of D search dirs cost N * D exists()
    probes (measured: 3 lookups over 3 dirs cost 9 calls). With memoisation
    only the first lookup should touch the filesystem; the rest are free.
    """
    calls = []

    def exists(path):
        calls.append(path)
        return path == "bundled/t_0041.png"

    idx = GlyphIndex(["cache", "pack", "bundled"], exists)
    for _ in range(3):
        idx.path("A", "top")
    assert len(calls) == 3, (
        f"expected 3 filesystem probes total (1 per search dir, once), "
        f"got {len(calls)}"
    )


def test_charset_reports_characters_with_both_halves():
    exists = fake_fs(("bundled", "t_0041.png"), ("bundled", "b_0041.png"),
                     ("bundled", "t_0042.png"))  # B has no bottom half
    idx = GlyphIndex(["bundled"], exists)
    cs = idx.charset("AB")
    assert "A" in cs
    assert "B" not in cs


def test_glyph_dirs_without_pack_omits_resource_entry():
    dirs = glyph_dirs("profile", "addon", "")
    assert dirs == ["profile/glyphs", "addon/resources/media/glyphs"]


def test_glyph_dirs_with_pack_orders_profile_pack_then_bundled():
    dirs = glyph_dirs("profile", "addon", "resource.images.splitflap.deco")
    assert dirs == [
        "profile/glyphs",
        "resource://resource.images.splitflap.deco",
        "addon/resources/media/glyphs",
    ]
