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


def test_top_and_bottom_halves_of_a_blank_card_are_identical(tmp_path):
    """Proves the comparison above is about the LETTERFORM, not the hinge.

    Without cropping the hinge off, this would pass too -- the hinge row
    alone guarantees raw bytes differ, even with no letter drawn at all.
    That was the bug in the un-cropped version of the test above.
    """
    render_glyphs(" ", FONT, str(tmp_path), 78, 71)
    top = _hinge_cropped_bytes(os.path.join(str(tmp_path), "t_0020.png"))
    bot = _hinge_cropped_bytes(os.path.join(str(tmp_path), "b_0020.png"))
    assert top == bot
