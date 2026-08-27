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
from .geometry import Geometry
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
        blank_top = self._index.path(BLANK, "top")
        blank_bottom = self._index.path(BLANK, "bottom")
        # Typed as the base Control: addControls takes List[Control], and
        # list is invariant, so the narrower element type is rejected.
        controls: list[xbmcgui.Control] = []
        for row in range(self._geo.rows):
            for col in range(self._geo.cols):
                cell = self._geo.cell_index(row, col)
                for half, texture in (("top", blank_top), ("bottom", blank_bottom)):
                    x, y, w, h = self._geo.half_rect(row, col, half)
                    control = self._make_control(x, y, w, h, texture, self._letter)
                    self._halves[(cell, half)] = control
                    controls.append(control)
        self._window.addControls(controls)
        xbmc.log(f"splitflap: built {len(controls)} controls", xbmc.LOGDEBUG)

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

    def set_accents(self, cells: Iterable[tuple[int, int]]) -> None:
        """Recolour accent tiles to the accent colour, everything else to letter.

        Called once per board (a fresh grid), never per animation frame.
        Takes (row, col) pairs -- unlike PaintOp.cell, which is a row-major
        index -- because that's how accents are recorded upstream; the
        conversion to row-major happens here, once, at the boundary, via
        the same Geometry.cell_index() build() uses so the two can't drift.
        """
        wanted = frozenset(self._geo.cell_index(row, col) for row, col in cells)
        for cell in self._accent_cells - wanted:
            self._recolour(cell, self._letter)
        for cell in wanted - self._accent_cells:
            self._recolour(cell, self._accent)
        self._accent_cells = wanted

    def _recolour(self, cell: int, colour: str) -> None:
        for half in ("top", "bottom"):
            control = self._halves.get((cell, half))
            if control is not None:
                control.setColorDiffuse(colour)

    def paint(self, ops: Iterable[PaintOp]) -> None:
        """Apply one batch of flap paint ops to their matching controls."""
        for op in ops:
            control = self._halves.get((op.cell, op.half))
            if control is None:
                continue
            control.setImage(self._index.path(op.char, op.half), useCache=True)
