"""Create the tile controls and paint ops onto them. The only renderer.

Every cell is a tile of two ControlImage halves -- there is no background
layer, because a blank tile is just another glyph. Colour comes from
colorDiffuse multiplying over greyscale glyphs: a near-black card barely
moves under a tint while the light letterform takes it. That is why glyphs
are greyscale and tints are applied here rather than baked into the image.

Whether xbmcgui.ControlImage accepts colorDiffuse as a Python constructor
keyword is a question the Task 0 spike needs real hardware to answer, and a
hand-flipped constant is exactly the kind of thing that ships stale after
someone forgets to update it. Instead this module detects it once at
runtime: the first control built this session tries the kwarg form, and if
that raises TypeError every later control (including that first one) falls
back to constructing plain and tinting with setColorDiffuse().

Settings colours and the row/column -> tile index arithmetic are validated
and computed by the pure `colour` and `geometry` modules respectively, not
here -- this file only calls them and reacts to what they say.
"""

from collections.abc import Iterable

import xbmc
import xbmcgui

from .charset import BLANK
from .colour import FALLBACK_ARGB, to_argb
from .flap import PaintOp
from .geometry import HALVES, SKIN_H, SKIN_W, Cell, Geometry, Half
from .glyphs import GlyphIndex


class BoardView:
    """Owns the Kodi controls for one board layout and paints flap ops onto them."""

    def __init__(self, window: xbmcgui.Window, geometry: Geometry,
                 index: GlyphIndex, letter_colour: str, accent_colour: str) -> None:
        self._window = window
        self._geo = geometry
        self._index = index
        self._letter = self._resolve_colour("letter", letter_colour)
        self._accent = self._resolve_colour("accent", accent_colour)
        self._halves: dict[tuple[int, str], xbmcgui.ControlImage] = {}
        self._accent_cells: frozenset[int] = frozenset()
        # What character each half last displayed. Needed because an accent
        # change repaints a cell without a flap op to tell it what to show.
        self._face: dict[tuple[int, str], str] = {}
        # None = not yet probed. True/False memoise the result of the first
        # attempt so later builds don't pay for a repeated failing kwarg call.
        self._color_diffuse_kwarg: bool | None = None

    def _resolve_colour(self, name: str, hex_rgb: str) -> str:
        """Validate a settings colour via the pure `colour` module.

        `to_argb` can't log (it has no Kodi import); this is the boundary
        that can, so an invalid settings value is visible in the log rather
        than silently painting the whole board with a garbage tint.
        """
        argb = to_argb(hex_rgb)
        if argb is None:
            xbmc.log(
                f"splitflap: invalid {name} colour {hex_rgb!r}, "
                f"falling back to {FALLBACK_ARGB}",
                xbmc.LOGWARNING,
            )
            return FALLBACK_ARGB
        return argb

    def build(self) -> None:
        """Create one ControlImage per half of every cell, blank-faced."""
        # Reset in case build() is ever called a second time on a live view --
        # otherwise a tile accented by a previous board would stay tinted
        # under the new one until set_accents() next disagreed with it.
        self._accent_cells = frozenset()
        # Controls are freshly created blank, so the face cache must agree.
        self._face = {}
        self._build_frame()
        blank_top = self._index.path(BLANK, "top")
        blank_bottom = self._index.path(BLANK, "bottom")
        # Typed as the base Control: addControls takes List[Control], and
        # list is invariant, so the narrower element type is rejected.
        controls: list[xbmcgui.Control] = []
        for row in range(self._geo.rows):
            for col in range(self._geo.cols):
                cell = self._geo.cell_index(row, col)
                blanks: tuple[tuple[Half, str], ...] = (
                    ("top", blank_top), ("bottom", blank_bottom))
                for half, texture in blanks:
                    x, y, w, h = self._geo.half_rect(row, col, half)
                    control = self._make_control(x, y, w, h, texture, self._letter)
                    self._halves[(cell, half)] = control
                    controls.append(control)
        self._window.addControls(controls)
        xbmc.log(f"splitflap: built {len(controls)} controls", xbmc.LOGDEBUG)

    def _build_frame(self) -> None:
        """The housing the board is mounted in, drawn behind the tiles.

        Without it the letterboxed area is flat black and the board reads as
        a screen showing a departure board rather than as one hanging on a
        wall. Built from stretched solids rather than a single picture, so
        it tracks the geometry at any row count.
        """
        g = self._geo
        casing = self._index.asset_path("frame_casing.png")
        white = self._index.asset_path("white.png")

        pad = max(6, g.gap * 3)
        x0, y0 = g.origin_x - pad, g.origin_y - pad
        x1 = g.origin_x + g.cols * (g.tile_w + g.gap) - g.gap + pad
        y1 = g.origin_y + g.rows * (g.tile_h + g.gap) - g.gap + pad

        plain = to_argb("FFFFFF") or FALLBACK_ARGB
        recess = to_argb("0A0A0B") or FALLBACK_ARGB
        lip = to_argb("34343A") or FALLBACK_ARGB
        underside = to_argb("060607") or FALLBACK_ARGB

        parts: list[xbmcgui.Control] = [
            # the casing fills the frame and is lit from above
            self._make_control(0, 0, SKIN_W, SKIN_H, casing, plain),
            # the well the tile field is recessed into
            self._make_control(x0, y0, x1 - x0, y1 - y0, white, recess),
            # a lit lip along the top inner edge, a dark one along the bottom
            self._make_control(x0, y0, x1 - x0, 2, white, lip),
            self._make_control(x0, y1 - 2, x1 - x0, 2, white, underside),
        ]

        # The maker's plate, centred in the casing below the well. Skipped
        # rather than fatal if a pack ships no plate: it is decoration, not
        # the housing, and losing it should not cost the board.
        try:
            plate = self._index.asset_path("frame_plate.png")
        except LookupError:
            plate = ""
        if plate:
            plate_w = min(420, (x1 - x0) // 3)
            plate_h = max(12, plate_w * 64 // 420)
            below = SKIN_H - y1
            if below > plate_h + 8:
                parts.append(self._make_control(
                    (SKIN_W - plate_w) // 2,
                    y1 + (below - plate_h) // 2,
                    plate_w, plate_h, plate, plain,
                ))
        self._window.addControls(parts)

    def _make_control(self, x: int, y: int, w: int, h: int, texture: str,
                       colour: str) -> xbmcgui.ControlImage:
        """Construct one tinted ControlImage, probing the colorDiffuse kwarg once.

        Tries the kwarg constructor form first. On TypeError (this Kodi
        build's xbmcgui doesn't accept it), remembers that, logs why, and
        falls back to constructing plain then calling setColorDiffuse() --
        here and for every later control this session.
        """
        if self._color_diffuse_kwarg is not False:
            try:
                control = xbmcgui.ControlImage(x, y, w, h, texture, colorDiffuse=colour)
            except TypeError as exc:
                self._color_diffuse_kwarg = False
                xbmc.log(
                    f"splitflap: colorDiffuse kwarg rejected ({exc!r}); "
                    "falling back to setColorDiffuse() for the rest of this "
                    "session",
                    xbmc.LOGDEBUG,
                )
            else:
                self._color_diffuse_kwarg = True
                return control
        control = xbmcgui.ControlImage(x, y, w, h, texture)
        control.setColorDiffuse(colour)
        return control

    def set_accents(self, cells: Iterable[Cell]) -> None:
        """Record which cells are accented and repaint them.

        Only records: `paint()` is the single authority on what texture a
        control carries. An earlier version wrote the accent texture here
        directly, which the very next flap op overwrote with the ordinary
        dark blank glyph -- silently restoring the invisible-accent bug this
        light card exists to fix. Two writers to one control is the defect;
        one writer plus recorded state is the fix.
        """
        wanted = frozenset(
            self._geo.cell_index(c.row, c.col) for c in cells
        )
        changed = (wanted ^ self._accent_cells)
        self._accent_cells = wanted
        for cell in changed:
            self._repaint(cell)

    def _repaint(self, cell: int) -> None:
        """Re-apply both halves of one cell under the current accent state."""
        for half in HALVES:
            control = self._halves.get((cell, half))
            if control is None:
                continue
            control.setImage(self._texture(cell, half, self._face.get(
                (cell, half), BLANK)), useCache=True)
            control.setColorDiffuse(self._colour(cell))

    def _accent_texture(self, half: Half) -> str:
        """The light accent card, resolved through the glyph index."""
        return self._index.accent_path(half)

    def _recolour(self, cell: int, colour: str) -> None:
        for half in HALVES:
            control = self._halves.get((cell, half))
            if control is not None:
                control.setColorDiffuse(colour)

    def paint(self, ops: Iterable[PaintOp]) -> None:
        """Apply one batch of flap paint ops to their matching controls.

        The single writer of control textures. An accented cell takes the
        light accent card whatever character the flap machine asked for --
        an accent tile is a solid coloured face, not a tinted letter.
        """
        for op in ops:
            control = self._halves.get((op.cell, op.half))
            if control is None:
                continue
            self._face[(op.cell, op.half)] = op.char
            control.setImage(self._texture(op.cell, op.half, op.char),
                             useCache=True)
            control.setColorDiffuse(self._colour(op.cell))

    def _texture(self, cell: int, half: Half, char: str) -> str:
        if cell in self._accent_cells:
            return self._index.accent_path(half)
        return self._index.path(char, half)

    def _colour(self, cell: int) -> str:
        return self._accent if cell in self._accent_cells else self._letter
