"""Turn one source line into exactly one board.

There is no pagination: a phrase never spills onto a second board just for
being long. The block grows to fit and centres; genuine overflow
ellipsises into the final cell of a full-width last row, where a board
running out of space would put it.
"""
import dataclasses
from collections.abc import Sequence
from typing import Literal, TypedDict

from .charset import BLANK
from .geometry import Cell

ELLIPSIS = "…"


class BeforeLineAccent(TypedDict):
    """Accent the padding cell left of where source line `n` starts."""

    before_line: int


class CornerAccent(TypedDict):
    """Accent a fixed corner of the grid."""

    corner: Literal["top-left", "top-right", "bottom-left", "bottom-right"]


class CellAccent(TypedDict):
    """Accent one exact cell. The only form that breaks when rows change.

    A Cell from our own sources; a plain [row, col] from a contributor's
    dict, which is how the README documents it and how JSON-ish data
    arrives. _accent_cell rebuilds either into a Cell.
    """

    cell: Cell | Sequence[int]


# What a source puts in Content.accents. A dict, not a class: contributors
# are other add-ons handing us plain JSON-ish data across an import
# boundary, so the runtime type has to stay a dict -- these just say which
# dicts mean something. An unrecognised one resolves to no cell and is
# dropped, never raised.
Accent = BeforeLineAccent | CornerAccent | CellAccent


@dataclasses.dataclass(frozen=True, slots=True)
class Board:
    """One laid-out board: every cell's character, and which are accented."""

    grid: tuple[str, ...]
    accents: frozenset[Cell]


def build(lines: Sequence[str], accents: Sequence[Accent],
          rows: int, cols: int, rtl: bool = False) -> Board:
    # 1. Uppercase the whole string first. Case expansion changes line
    #    length, so it must happen before wrapping.
    upper = [line.upper() for line in lines]
    board = _compose(upper, accents, rows, cols, cols, rtl)
    # An accent tile is a solid face with no glyph, so a letter under one is
    # simply lost. Give the text a narrower wrap and let it re-centre: the
    # accent keeps its cell and the block moves out from under it.
    if _collides(board):
        narrower = _compose(upper, accents, rows, cols, max(1, cols - 2), rtl)
        # Only take it if it actually clears them -- on a tiny board the
        # narrower wrap overflows and ellipsises, which is worse.
        if not _collides(narrower):
            board = narrower
    # A block that still cannot clear them (it fills the grid edge to edge)
    # loses the accent rather than the letter.
    if _collides(board):
        board = Board(board.grid, frozenset(
            c for c in board.accents if board.grid[c.row][c.col] == BLANK))
    return board


def _collides(board: Board) -> bool:
    """True if any accent cell has a letter under it."""
    return any(board.grid[c.row][c.col] != BLANK for c in board.accents)


def _compose(upper: list[str], accents: Sequence[Accent],
             rows: int, cols: int, width: int, rtl: bool) -> Board:
    """Lay the text out at `width`, still centred across all `cols`."""
    # 2-3. Wrap, recording where each source line starts among wrapped lines.
    wrapped, line_start = _wrap_lines(upper, width)
    # 5. Overflow ellipsises rather than paginating.
    wrapped, truncated = _fit_to_rows(wrapped, rows, width)
    # 4. Size the block to its line count and centre it vertically.
    top = (rows - len(wrapped)) // 2
    grid, offsets = _lay_rows(wrapped, rows, cols, top, truncated, rtl,
                              _marked_rows(accents, line_start))

    resolved = _resolve_accents(accents, rows, cols, top, line_start,
                                offsets, wrapped)
    return Board(tuple(grid), frozenset(resolved))


def _wrap_lines(upper: list[str], cols: int) -> tuple[list[str], list[int]]:
    """Wrap each source line, tracking where each one starts.

    `line_start` is what lets a `{"before_line": n}` accent find its row
    after wrapping has changed how many lines there are.
    """
    wrapped: list[str] = []
    line_start: list[int] = []
    for line in upper:
        line_start.append(len(wrapped))
        pieces = _wrap(line, cols)
        wrapped.extend(pieces or [""])
    return wrapped, line_start


def _fit_to_rows(wrapped: list[str], rows: int,
                 cols: int) -> tuple[list[str], bool]:
    """Squeeze overflow into the last row, ellipsising only if text is lost.

    Merging the tail into one row often makes it fit, and an ellipsis on a
    row that dropped nothing tells the viewer a lie. Returns the rows and
    whether the last one was hard-filled.
    """
    if len(wrapped) <= rows:
        return wrapped, False
    remainder = " ".join(wrapped[rows - 1:])
    if len(remainder) > cols:
        # hard-fills the row, ellipsis in the last cell
        return [*wrapped[:rows - 1], remainder[:cols - 1] + ELLIPSIS], True
    # everything survived; centre it normally
    return [*wrapped[:rows - 1], remainder], False


def _marked_rows(accents: Sequence[Accent],
                 line_start: list[int]) -> frozenset[int]:
    """Which wrapped lines a `before_line` accent wants a cell to the left of."""
    out = set()
    for spec in accents or ():
        if "before_line" not in spec:
            continue
        idx = int(spec["before_line"])
        if 0 <= idx < len(line_start):
            out.add(line_start[idx])
    return frozenset(out)


def _lay_rows(wrapped: list[str], rows: int, cols: int, top: int,
              truncated: bool, rtl: bool,
              marked: frozenset[int] = frozenset()) -> tuple[list[str], list[int]]:
    """Place the wrapped block into the grid, returning rows and their padding.

    A line that centres flush against the left edge leaves nowhere for its
    marker. Where the row has a spare cell on the right, it shifts one
    column right rather than losing the marker -- a cheaper answer than
    re-wrapping the whole block narrower, and the only one when the block
    reads better at its natural width.
    """
    grid: list[str] = []
    offsets: list[int] = []
    for r in range(rows):
        i = r - top
        if not 0 <= i < len(wrapped):
            offsets.append(0)
            grid.append(BLANK * cols)
            continue
        text = wrapped[i]
        if rtl:
            text = text[::-1]
        if truncated and i == len(wrapped) - 1:
            pad = 0
            row = text.ljust(cols, BLANK)[:cols]
        else:
            pad = (cols - len(text)) // 2
            if not pad and i in marked and len(text) < cols:
                pad = 1
            row = (BLANK * pad + text).ljust(cols, BLANK)[:cols]
        offsets.append(pad)
        grid.append(row)
    return grid, offsets


def _wrap(text: str, cols: int) -> list[str]:
    """Break text into lines of at most `cols` characters.

    Greedy word wrapping: fill each line with as many whole words as fit,
    joined by single spaces. A word longer than `cols` cannot fit on any
    line, so it is hard-split across as many lines as it needs.

    Returns [] for text with no words.
    """
    if cols < 1:
        return []
    items: list[str] = text.split()
    result: list[str] = []
    while items:
        was_split = False
        cur_item = items.pop(0)
        while len(cur_item) > cols:
            was_split = True
            result.append(cur_item[:cols])
            cur_item = cur_item[cols:]
        if not was_split:
            while items and len(f"{cur_item} {items[0]}") <= cols:
                cur_item = f"{cur_item} {items.pop(0)}"
        result.append(cur_item)
    return result


def _resolve_accents(accents: Sequence[Accent],
                     rows: int, cols: int, top: int,
                     line_start: list[int], offsets: list[int],
                     wrapped: list[str]) -> list[Cell]:
    """Turn relative accent specs into concrete (row, col) cells.

    A source has no idea where its lines land after uppercasing, wrapping
    and centring, so it expresses accents relatively and this resolves
    them. Anything landing outside the grid is dropped, not raised.
    """
    out: list[Cell] = []
    for spec in accents or ():
        cell = _accent_cell(spec, rows, cols, top, line_start, offsets, wrapped)
        if cell and 0 <= cell.row < rows and 0 <= cell.col < cols:
            out.append(cell)
    return out


def _accent_cell(spec: Accent, rows: int, cols: int, top: int,
                 line_start: list[int], offsets: list[int],
                 wrapped: list[str]) -> Cell | None:
    """Resolve one accent spec to a cell, or None if it does not name one.

    A contributor's `cell` arrives as whatever it put in its dict -- a list
    as often as a tuple -- so it is rebuilt into a Cell rather than trusted
    to be one.
    """
    if "cell" in spec:
        row, col = spec["cell"]
        return Cell(int(row), int(col))
    if "corner" in spec:
        return {
            "top-left": Cell(0, 0),
            "top-right": Cell(0, cols - 1),
            "bottom-left": Cell(rows - 1, 0),
            "bottom-right": Cell(rows - 1, cols - 1),
        }.get(spec["corner"])
    if "before_line" in spec:
        return _before_line_cell(spec, rows, top, line_start, offsets, wrapped)
    return None


def _before_line_cell(spec: BeforeLineAccent, rows: int, top: int,
                      line_start: list[int], offsets: list[int],
                      wrapped: list[str]) -> Cell | None:
    """The cell just left of where a given source line starts.

    A line wide enough to leave no padding has no cell to its left. Clamp
    to the first column rather than resolving off-grid: the accent then
    sits on a letter, which build() sees as a collision and answers with
    the narrower wrap -- an accent that silently fell off the edge would
    get no such second chance.
    """
    idx = int(spec["before_line"])
    if not 0 <= idx < len(line_start):
        return None
    wrapped_idx = line_start[idx]
    if wrapped_idx >= len(wrapped):
        return None
    row = top + wrapped_idx
    if not 0 <= row < rows:
        return None
    return Cell(row, max(0, offsets[row] - 1))
