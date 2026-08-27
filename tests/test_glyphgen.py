import os

import pytest
from resources.lib.glyphgen import glyph_filename, render_glyphs

PIL = pytest.importorskip("PIL")
FONT = "assets/fonts/NimbusSans-Regular.otf"


def test_filename_is_zero_padded_codepoint_hex():
    assert glyph_filename("A", "top") == "t_0041.png"
    assert glyph_filename("A", "bottom") == "b_0041.png"
    assert glyph_filename(" ", "top") == "t_0020.png"
    assert glyph_filename("□", "bottom") == "b_25a1.png"


def test_filename_distinguishes_case_insensitively_safe_names():
    """Names must not collide on a case-insensitive filesystem."""
    assert glyph_filename("A", "top").lower() != glyph_filename("a", "top").lower()


def test_render_writes_two_files_per_character(tmp_path):
    written = render_glyphs("AB", FONT, str(tmp_path), 78, 71)
    assert len(written) == 4
    for name in ("t_0041.png", "b_0041.png", "t_0042.png", "b_0042.png"):
        assert os.path.exists(os.path.join(str(tmp_path), name))


def test_rendered_halves_have_requested_size(tmp_path):
    from PIL import Image
    render_glyphs("A", FONT, str(tmp_path), 78, 71)
    with Image.open(os.path.join(str(tmp_path), "t_0041.png")) as im:
        assert im.size == (78, 71)


def _hinge_cropped_bytes(path):
    """The half's pixels excluding the hinge row nearest the seam.

    The hinge line (glyphgen.py:46, width 2) is drawn straddling the
    top/bottom boundary, so it leaves one row of hinge pixels in EACH
    crop -- the last row of the top half, the first row of the bottom
    half. Comparing raw bytes (hinge rows included) would pass even for
    two blank halves, since the hinge alone always differs in position
    between the two crops; cropping it off is what makes this comparison
    actually about the letterform.
    """
    from PIL import Image
    with Image.open(path) as im:
        w, h = im.size
        is_top = os.path.basename(path).startswith("t_")
        box = (0, 0, w, h - 1) if is_top else (0, 1, w, h)
        return im.crop(box).tobytes()


def test_top_and_bottom_halves_differ(tmp_path):
    render_glyphs("A", FONT, str(tmp_path), 78, 71)
    top = _hinge_cropped_bytes(os.path.join(str(tmp_path), "t_0041.png"))
    bot = _hinge_cropped_bytes(os.path.join(str(tmp_path), "b_0041.png"))
    assert top != bot


def test_letters_reach_both_halves(tmp_path):
    """Different letters must produce different top AND bottom halves.

    This is what the old byte comparison was reaching for. Comparing one
    card's two halves cannot show it: they differ anyway, first because of
    the hinge and now because of the baked depth cues. Comparing the SAME
    half across two letters isolates the letterform.
    """
    from PIL import Image

    render_glyphs("AB", FONT, str(tmp_path), 78, 71)

    def raw(name: str) -> bytes:
        with Image.open(os.path.join(str(tmp_path), name)) as im:
            return im.tobytes()

    assert raw("t_0041.png") != raw("t_0042.png")
    assert raw("b_0041.png") != raw("b_0042.png")


def test_upper_flap_casts_a_shadow_on_the_lower_half(tmp_path):
    """The depth cue that makes a tile read as two stacked cards.

    Without it the halves are one flat square with a line through it. The
    row just below the hinge must be darker than the equivalent row below
    the top half's own top edge, because the upper flap shades it.
    """
    from PIL import Image

    render_glyphs(" ", FONT, str(tmp_path), 78, 71)
    probe = 4
    with Image.open(os.path.join(str(tmp_path), "t_0020.png")) as top:
        top_row = sum(top.crop((0, probe, top.width, probe + 1)).getdata())
    with Image.open(os.path.join(str(tmp_path), "b_0020.png")) as bot:
        bot_row = sum(bot.crop((0, probe, bot.width, probe + 1)).getdata())
    assert bot_row < top_row, "the lower half should be shaded by the flap above"


def test_each_half_is_top_lit(tmp_path):
    """Each half is brightest at its own top edge and falls away downward."""
    from PIL import Image

    render_glyphs(" ", FONT, str(tmp_path), 78, 71)
    with Image.open(os.path.join(str(tmp_path), "t_0020.png")) as top:
        rows = [sum(top.crop((0, y, top.width, y + 1)).getdata())
                for y in (0, top.height // 2, top.height - 2)]
    assert rows[0] > rows[1] > rows[2], f"not top-lit: {rows}"
