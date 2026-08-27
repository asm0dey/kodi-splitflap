import pytest

from resources.lib.geometry import BOARD_ASPECT, CELL_ASPECT, compute


def test_reference_geometry_is_22_by_6():
    """Measured from the reference image by FFT of the tile field."""
    g = compute(rows=6)
    assert g.rows == 6
    assert g.cols == 22


def test_cells_are_portrait():
    g = compute(rows=6)
    assert g.tile_w < g.tile_h
    assert abs(g.tile_w / float(g.tile_h) - CELL_ASPECT) < 0.05


def test_board_fits_the_frame_at_every_row_count():
    for rows in range(2, 16):
        g = compute(rows=rows)
        width = g.cols * g.tile_w + (g.cols - 1) * g.gap
        height = g.rows * g.tile_h + (g.rows - 1) * g.gap
        assert width <= 1920, rows
        assert height <= 1080, rows


def test_board_letterboxes_rather_than_filling_height():
    """BOARD_ASPECT 2.0 exceeds the frame's 1.78, so there is vertical slack."""
    g = compute(rows=6)
    height = g.rows * g.tile_h + (g.rows - 1) * g.gap
    assert height < 1080 * 0.95
    assert BOARD_ASPECT > 1920 / 1080.0


def test_grid_is_centred():
    g = compute(rows=6)
    width = g.cols * g.tile_w + (g.cols - 1) * g.gap
    height = g.rows * g.tile_h + (g.rows - 1) * g.gap
    assert abs(g.origin_x - (1920 - width) / 2) <= 1
    assert abs(g.origin_y - (1080 - height) / 2) <= 1


def test_more_rows_means_more_columns():
    assert compute(rows=3).cols < compute(rows=6).cols < compute(rows=10).cols


def test_half_rects_stack_and_tile():
    g = compute(rows=6)
    top = g.half_rect(0, 0, "top")
    bottom = g.half_rect(0, 0, "bottom")
    assert top[1] + top[3] == bottom[1]
    assert top[3] + bottom[3] == g.tile_h
    assert top[2] == bottom[2] == g.tile_w


def test_adjacent_cells_are_a_pitch_apart():
    g = compute(rows=6)
    a = g.half_rect(0, 0, "top")
    b = g.half_rect(0, 1, "top")
    assert b[0] - a[0] == g.tile_w + g.gap


def test_too_many_rows_is_rejected_rather_than_returning_zero_tiles():
    with pytest.raises(ValueError):
        compute(rows=73)


def test_absurd_margin_is_rejected_rather_than_returning_negative_tiles():
    with pytest.raises(ValueError):
        compute(rows=6, margin_pct=0.6)


def test_rows_descend_the_screen():
    """Row n+1 sits BELOW row n, one pitch down.

    Mutation testing found that negating the row offset in half_rect left
    every test green while stacking the board upward off the top of the
    screen. Columns had this check; rows did not.
    """
    g = compute(rows=6)
    a = g.half_rect(0, 0, "top")
    b = g.half_rect(1, 0, "top")
    assert b[1] - a[1] == g.tile_h + g.gap
    assert b[1] > a[1]


def test_every_cell_lies_inside_the_frame():
    """No tile may be positioned off-screen in either axis."""
    g = compute(rows=6)
    for row in range(g.rows):
        for col in range(g.cols):
            for half in ("top", "bottom"):
                x, y, w, h = g.half_rect(row, col, half)
                assert x >= 0 and y >= 0, (row, col, half, x, y)
                assert x + w <= 1920, (row, col, half, x, w)
                assert y + h <= 1080, (row, col, half, y, h)
