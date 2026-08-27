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

    # 2-3. Wrap, recording where each source line starts among wrapped lines
    #      so that {"before_line": n} accents can be resolved later.
    wrapped: list[str] = []
    line_start: list[int] = []
    for line in upper:
        line_start.append(len(wrapped))
        pieces = _wrap(line, cols)
        wrapped.extend(pieces if pieces else [""])

    # 5. Overflow ellipsises rather than paginating -- but only when text is
    #    genuinely lost. Merging the tail into one row often makes it fit, and
    #    an ellipsis on a row that dropped nothing tells the viewer a lie.
    truncated = False
    if len(wrapped) > rows:
        remainder = " ".join(wrapped[rows - 1:])
        if len(remainder) > cols:
            last = remainder[:cols - 1] + ELLIPSIS
            truncated = True          # hard-fills the row, ellipsis in the last cell
        else:
            last = remainder          # everything survived; centre it normally
        wrapped = wrapped[:rows - 1] + [last]

    # 4. Size the block to its line count and centre it vertically.
    top = (rows - len(wrapped)) // 2

    grid: list[str] = []
    offsets: list[int] = []
    for r in range(rows):
        i = r - top
        if 0 <= i < len(wrapped):
            text = wrapped[i]
            is_filled_last = truncated and i == len(wrapped) - 1
            if rtl:
                text = text[::-1]
            if is_filled_last:
                pad = 0
                row = text.ljust(cols, BLANK)[:cols]
            else:
                pad = (cols - len(text)) // 2
                row = (BLANK * pad + text).ljust(cols, BLANK)[:cols]
            offsets.append(pad)
            grid.append(row)
        else:
            offsets.append(0)
            grid.append(BLANK * cols)

    resolved = _resolve_accents(accents, rows, cols, top, line_start,
                                offsets, wrapped)
    return Board(tuple(grid), frozenset(resolved))


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
    if len(items) == 0: return result
    long = False
    while len(items) != 0:
        cur_result = items.pop(0)
        while True:
            if len(cur_result) > cols:
                long = True
                result.append(cur_result[0:cols])
                cur_result = cur_result[cols:]
            else:
                if long: result.append(cur_result)
                break
        if not long:
            while len(cur_result) <= cols:
                if len(items) == 0:
                    result.append(cur_result)
                    break
                tmp = f"{cur_result} {items[0]}"
                if len(tmp) <= cols:
                    cur_result = tmp
                    items.pop(0)
                else:
                    result.append(cur_result)
                    break

        long = False
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
        cell: tuple[int, int] | None = None
        if "cell" in spec:
            cell = (int(spec["cell"][0]), int(spec["cell"][1]))
        elif "corner" in spec:
            cell = {
                "top-left": (0, 0),
                "top-right": (0, cols - 1),
                "bottom-left": (rows - 1, 0),
                "bottom-right": (rows - 1, cols - 1),
            }.get(spec["corner"])
        elif "before_line" in spec:
            idx = int(spec["before_line"])
            if 0 <= idx < len(line_start):
                wrapped_idx = line_start[idx]
                if wrapped_idx < len(wrapped):
                    row = top + wrapped_idx
                    if 0 <= row < rows:
                        cell = (row, offsets[row] - 1)
        if cell and 0 <= cell[0] < rows and 0 <= cell[1] < cols:
            out.append(cell)
    return out
