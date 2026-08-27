"""Board geometry in Kodi's fixed 1920x1080 skin coordinate space.

Rows is the only setting. Columns derive from the tile field's own aspect,
measured from the reference image at 2.0 -- wider than the 16:9 frame, so
the board fills the width and letterboxes vertically, exactly as the
reference does. Deriving columns by filling the HEIGHT instead yields 18
columns at six rows and does not match.
"""

CELL_ASPECT = 0.55    # tile width / tile height. Split-flap cards are portrait.
BOARD_ASPECT = 2.0    # tile field width / height, measured from the reference.
SKIN_W = 1920
SKIN_H = 1080


class Geometry:
    def __init__(self, rows: int, cols: int, tile_w: int, tile_h: int,
                 gap: int, origin_x: int, origin_y: int) -> None:
        self.rows = rows
        self.cols = cols
        self.tile_w = tile_w
        self.tile_h = tile_h
        self.gap = gap
        self.origin_x = origin_x
        self.origin_y = origin_y

    @property
    def cells(self) -> int:
        return self.rows * self.cols

    def cell_index(self, row: int, col: int) -> int:
        """Row-major flat index for (row, col), matching flap.FlapMachine's
        own cell numbering (`idx = r * cols + c`) so a PaintOp.cell and a
        board coordinate always agree on which tile they mean."""
        return row * self.cols + col

    def half_rect(self, row: int, col: int, half: str) -> tuple[int, int, int, int]:
        """Return (x, y, w, h) for one half of one tile."""
        x = self.origin_x + col * (self.tile_w + self.gap)
        y = self.origin_y + row * (self.tile_h + self.gap)
        top_h = self.tile_h // 2
        if half == "top":
            return (x, y, self.tile_w, top_h)
        return (x, y + top_h, self.tile_w, self.tile_h - top_h)


def compute(rows: int, skin_w: int = SKIN_W, skin_h: int = SKIN_H,
            margin_pct: float = 0.02, gap: int = 6) -> Geometry:
    if rows < 1:
        raise ValueError(f"rows must be >= 1, got {rows!r}")

    cols = round(rows * BOARD_ASPECT / CELL_ASPECT)
    cols = max(1, cols)

    margin_x = int(skin_w * margin_pct)
    tile_w = int((skin_w - 2 * margin_x - (cols - 1) * gap) / cols)
    tile_h = int(tile_w / CELL_ASPECT)

    # BOARD_ASPECT exceeds the frame aspect, so this normally has slack. Clamp
    # anyway: a non-default skin aspect can force the height limit lower than width.
    margin_y = int(skin_h * margin_pct)
    max_tile_h = int((skin_h - 2 * margin_y - (rows - 1) * gap) / rows)
    if tile_h > max_tile_h:
        tile_h = max_tile_h
        tile_w = int(tile_h * CELL_ASPECT)

    if tile_w <= 0 or tile_h <= 0:
        raise ValueError(
            f"cannot compute geometry with rows={rows}, margin_pct={margin_pct}: "
            f"tile dimensions degenerate to {tile_w}x{tile_h}. "
            f"Reduce rows or margin_pct."
        )

    width = cols * tile_w + (cols - 1) * gap
    height = rows * tile_h + (rows - 1) * gap
    return Geometry(
        rows=rows, cols=cols, tile_w=tile_w, tile_h=tile_h, gap=gap,
        origin_x=(skin_w - width) // 2,
        origin_y=(skin_h - height) // 2,
    )
