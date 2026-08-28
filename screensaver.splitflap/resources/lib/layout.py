"""Turn one source line into exactly one board.

There is no pagination: a phrase never spills onto a second board just for
being long. The block grows to fit and centres; genuine overflow
ellipsises into the final cell of a full-width last row, where a board
running out of space would put it.
"""
from typing import Any

from .charset import BLANK

ELLIPSIS = "…"


class Board:
    def __init__(self, grid: tuple[str, ...],
                 accents: frozenset[tuple[int, int]]) -> None:
        self.grid = grid
        self.accents = accents


def build(lines: list[str] | tuple[str, ...],
          accents: list[dict[str, Any]] | tuple[dict[str, Any], ...],
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
            c for c in board.accents if board.grid[c[0]][c[1]] == BLANK))
    return board


def _collides(board: Board) -> bool:
    """True if any accent cell has a letter under it."""
    return any(board.grid[r][c] != BLANK for r, c in board.accents)


def _compose(upper: list[str],
             accents: list[dict[str, Any]] | tuple[dict[str, Any], ...],
             rows: int, cols: int, width: int, rtl: bool) -> Board:
    """Lay the text out at `width`, still centred across all `cols`."""
    # 2-3. Wrap, recording where each source line starts among wrapped lines.
    wrapped, line_start = _wrap_lines(upper, width)
    # 5. Overflow ellipsises rather than paginating.
    wrapped, truncated = _fit_to_rows(wrapped, rows, width)
    # 4. Size the block to its line count and centre it vertically.
    top = (rows - len(wrapped)) // 2
    grid, offsets = _lay_rows(wrapped, rows, cols, top, truncated, rtl)

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


def _lay_rows(wrapped: list[str], rows: int, cols: int, top: int,
              truncated: bool, rtl: bool) -> tuple[list[str], list[int]]:
    """Place the wrapped block into the grid, returning rows and their padding."""
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


def _resolve_accents(accents: list[dict[str, Any]] | tuple[dict[str, Any], ...],
                     rows: int, cols: int, top: int,
                     line_start: list[int], offsets: list[int],
                     wrapped: list[str]) -> list[tuple[int, int]]:
    """Turn relative accent specs into concrete (row, col) cells.

    A source has no idea where its lines land after uppercasing, wrapping
    and centring, so it expresses accents relatively and this resolves
    them. Anything landing outside the grid is dropped, not raised.
    """
    out: list[tuple[int, int]] = []
    for spec in accents or ():
        cell = _accent_cell(spec, rows, cols, top, line_start, offsets, wrapped)
        if cell and 0 <= cell[0] < rows and 0 <= cell[1] < cols:
            out.append(cell)
    return out


def _accent_cell(spec: dict[str, Any], rows: int, cols: int, top: int,
                 line_start: list[int], offsets: list[int],
                 wrapped: list[str]) -> tuple[int, int] | None:
    """Resolve one accent spec to a cell, or None if it does not name one."""
    if "cell" in spec:
        return (int(spec["cell"][0]), int(spec["cell"][1]))
    if "corner" in spec:
        return {
            "top-left": (0, 0),
            "top-right": (0, cols - 1),
            "bottom-left": (rows - 1, 0),
            "bottom-right": (rows - 1, cols - 1),
        }.get(spec["corner"])
    if "before_line" in spec:
        return _before_line_cell(spec, rows, top, line_start, offsets, wrapped)
    return None


def _before_line_cell(spec: dict[str, Any], rows: int, top: int,
                      line_start: list[int], offsets: list[int],
                      wrapped: list[str]) -> tuple[int, int] | None:
    """The cell just left of where a given source line starts."""
    idx = int(spec["before_line"])
    if not 0 <= idx < len(line_start):
        return None
    wrapped_idx = line_start[idx]
    if wrapped_idx >= len(wrapped):
        return None
    row = top + wrapped_idx
    if not 0 <= row < rows:
        return None
    return (row, offsets[row] - 1)
