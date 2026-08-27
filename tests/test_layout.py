from resources.lib.layout import ELLIPSIS, build


def grid(lines, rows=6, cols=22, accents=(), rtl=False):
    return build(lines, accents, rows, cols, rtl=rtl).grid


def test_board_is_exactly_rows_by_cols():
    g = grid(["HELLO"])
    assert len(g) == 6
    assert all(len(row) == 22 for row in g)


def test_text_is_uppercased():
    assert "HELLO" in "".join(grid(["hello"]))


def test_short_line_is_centred_horizontally():
    g = grid(["ABCD"], rows=1, cols=10)
    assert g[0] == "   ABCD   "


def test_block_is_centred_vertically_and_grows_to_fit():
    one = grid(["AB"], rows=5, cols=22)
    assert one[2].strip() == "AB"          # single line lands in the middle
    three = grid(["AAA BBB CCC DDD EEE FFF GGG HHH"], rows=5, cols=11)
    filled = [i for i, r in enumerate(three) if r.strip()]
    assert filled == [1, 2, 3]             # three lines, still centred


def test_wraps_on_words():
    """Greedy: each line takes as many whole words as fit.

    'THE ONLY WAY' is exactly 12 characters, so it fills line one exactly.
    Adding ' OUT' would need 16, so OUT starts line two.
    """
    g = grid(["THE ONLY WAY OUT IS THROUGH"], rows=6, cols=12)
    text = [r.strip() for r in g if r.strip()]
    assert text == ["THE ONLY WAY", "OUT IS", "THROUGH"]


def test_wrapped_lines_never_start_with_a_space():
    """A line built by joining words must not inherit a leading separator."""
    from resources.lib.layout import _wrap
    for line in _wrap("THE ONLY WAY OUT IS THROUGH", 12):
        assert line == line.lstrip(), f"leading space in {line!r}"


def test_words_after_a_full_line_still_wrap_on_words():
    """Only over-long WORDS get hard-split, never the remaining text."""
    from resources.lib.layout import _wrap
    assert _wrap("THE ONLY WAY OUT IS THROUGH", 12) == [
        "THE ONLY WAY", "OUT IS", "THROUGH",
    ]


def test_whitespace_only_input_yields_no_lines():
    from resources.lib.layout import _wrap
    assert _wrap("", 22) == []
    assert _wrap("   ", 22) == []
    assert _wrap("\t \n ", 22) == []


def test_runs_of_whitespace_collapse_to_one_separator():
    """Words are separated by any whitespace run, not a single space."""
    from resources.lib.layout import _wrap
    assert _wrap("A  B", 22) == ["A B"]
    assert _wrap("A\tB", 22) == ["A B"]
    assert _wrap("A \n B", 22) == ["A B"]


def test_packing_resumes_after_an_over_long_word():
    """An oversized word must not disable word-packing for the rest of the line.

    SUPERCALIFRAGILISTIC hard-splits into three lines, and the words that
    follow it should still share a line the way they normally would.
    """
    from resources.lib.layout import _wrap
    assert _wrap("SUPERCALIFRAGILISTIC AB CD", 8) == [
        "SUPERCAL", "IFRAGILI", "STIC", "AB CD",
    ]


def test_over_long_word_after_normal_words():
    """The mirror case: packing, then an oversized word arrives."""
    from resources.lib.layout import _wrap
    assert _wrap("AB CD SUPERCALIFRAGILISTIC", 8) == [
        "AB CD", "SUPERCAL", "IFRAGILI", "STIC",
    ]


def test_over_long_word_is_hard_split():
    g = grid(["SUPERCALIFRAGILISTIC"], rows=6, cols=8)
    text = [r.strip() for r in g if r.strip()]
    assert text[0] == "SUPERCAL"


def test_case_expansion_takes_extra_cells():
    """The sharp s uppercases to two characters, so it needs two cells."""
    g = grid(["straße"], rows=1, cols=22)
    assert "STRASSE" in g[0]


def test_case_expansion_is_measured_after_wrapping():
    """Uppercasing must precede wrapping, since it changes line length."""
    g = grid(["aßaßaßa"], rows=3, cols=5)
    for row in g:
        assert len(row) == 5


def test_overflow_ellipsises_into_the_final_cell():
    long = " ".join(["WORD"] * 40)
    g = grid([long], rows=2, cols=10)
    assert g[-1].endswith(ELLIPSIS)
    assert len(g[-1]) == 10
    assert g[-1] != " " * 9 + ELLIPSIS      # last row is filled, not padded


def test_one_line_always_yields_one_board():
    """build returns a Board, never a sequence. There is no pagination."""
    b = build([" ".join(["WORD"] * 200)], (), 6, 22)
    assert isinstance(b.grid, tuple)
    assert len(b.grid) == 6


def test_author_line_is_its_own_line():
    g = grid(["THE ONLY WAY OUT IS THROUGH", "ROBERT FROST"], rows=6, cols=22)
    text = [r.strip() for r in g if r.strip()]
    assert text[-1] == "ROBERT FROST"


def test_rtl_line_is_reversed():
    g = grid(["ABC"], rows=1, cols=5, rtl=True)
    assert g[0].strip() == "CBA"


def test_rtl_ellipsis_goes_to_the_visual_end():
    g = grid([" ".join(["WORD"] * 40)], rows=1, cols=10, rtl=True)
    assert g[0].startswith(ELLIPSIS)


def test_accent_before_line_resolves_to_the_cell_left_of_it():
    b = build(["AB", "CD"], [{"before_line": 1}], 4, 10)
    row = next(i for i, r in enumerate(b.grid) if r.strip() == "CD")
    col = b.grid[row].index("C")
    assert (row, col - 1) in b.accents


def test_accent_corners_resolve_to_grid_corners():
    b = build(["AB"], [{"corner": "top-left"}, {"corner": "top-right"}], 4, 10)
    assert (0, 0) in b.accents
    assert (0, 9) in b.accents


def test_accent_explicit_cell_passes_through():
    b = build(["AB"], [{"cell": [2, 3]}], 4, 10)
    assert (2, 3) in b.accents


def test_accent_outside_the_grid_is_dropped_not_raised():
    b = build(["AB"], [{"cell": [99, 99]}], 4, 10)
    assert b.accents == frozenset()


def test_empty_lines_give_a_blank_board():
    g = grid([])
    assert all(row.strip() == "" for row in g)


def test_remainder_that_fits_is_not_ellipsised():
    """Merging the tail into one row often makes it fit.

    An ellipsis on a row that dropped nothing tells the viewer text was
    lost when it was not. Only genuine overflow earns the ellipsis.
    """
    g = grid(["AAAAAAAAA", "X", "Y"], rows=2, cols=10)
    assert ELLIPSIS not in "".join(g)
    assert g[-1].strip() == "X Y"


def test_remainder_that_fits_is_centred_not_left_filled():
    g = grid(["AAAAAAAAA", "X", "Y"], rows=2, cols=10)
    assert g[-1] == "   X Y    "


def test_remainder_that_overflows_still_ellipsises():
    """The mirror case must keep working: real loss, real ellipsis."""
    g = grid(["AAAAAAAAA"] + ["WORD"] * 10, rows=2, cols=10)
    assert g[-1].endswith(ELLIPSIS)
    assert len(g[-1]) == 10
    assert g[-1] != " " * 9 + ELLIPSIS
