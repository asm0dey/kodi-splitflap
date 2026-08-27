"""Animation state machine. Emits paint ops; never touches Kodi.

A step is one character advance -- one card falling -- rendered as two
half-steps: the top lands, then the bottom. That transient mismatch
between halves IS the hinge effect; it is the whole visual point of the
product.

Transitions retarget directly, with no clear-to-blank, so cells whose
character is unchanged never move. A settled board emits zero ops, which
is what keeps the cost confined to the ~1s transition between boards
rather than paid every frame forever.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from .charset import BLANK
from .drum import MAX_STEPS, Drum

STEP_MS = 200          # real hardware runs at five flaps per second
COL_DELAY_MS = 18      # left-to-right ripple
ROW_DELAY_MS = 40
JITTER_MS = 12


class PaintOp(NamedTuple):
    cell: int
    half: str          # "top" or "bottom", never a bool
    char: str


class _Cell:
    __slots__ = ("char", "seq", "step", "phase", "start_ms")

    def __init__(self, char: str) -> None:
        self.char = char
        self.seq: tuple[str, ...] = ()
        self.step = 0
        self.phase = 0          # 0 = top pending, 1 = bottom pending
        self.start_ms = 0

    @property
    def busy(self) -> bool:
        return self.step < len(self.seq)


class FlapMachine:
    def __init__(
        self,
        drum: Drum,
        rows: int,
        cols: int,
        max_steps: int = MAX_STEPS,
        step_ms: int = STEP_MS,
        col_delay_ms: int = COL_DELAY_MS,
        row_delay_ms: int = ROW_DELAY_MS,
        jitter_ms: int = JITTER_MS,
        blank: str = BLANK,
    ) -> None:
        self._drum = drum
        self._rows = rows
        self._cols = cols
        self._max_steps = max_steps
        self._step_ms = step_ms
        self._col_delay = col_delay_ms
        self._row_delay = row_delay_ms
        self._jitter = jitter_ms
        self._cells = [_Cell(blank) for _ in range(rows * cols)]

    @property
    def settled(self) -> bool:
        return not any(cell.busy for cell in self._cells)

    def retarget(self, grid: Sequence[str], now_ms: int = 0) -> None:
        """Point every cell at a new target character.

        `now_ms` anchors each cell's `start_ms` to the caller's clock. It
        must be the same clock `tick` is later called with (e.g.
        `int(time.time() * 1000)`) -- if `start_ms` were left as a bare
        stagger offset (0..a few hundred ms) while `tick` compares it
        against a real wall-clock value in the billions, every cell would
        read as already overdue on the very first tick and dump its whole
        sequence at once instead of animating.
        """
        if len(grid) != self._rows:
            raise ValueError(f"expected {self._rows} rows, got {len(grid)}")
        for r, row in enumerate(grid):
            if len(row) != self._cols:
                raise ValueError(
                    f"row {r} has {len(row)} cells, expected {self._cols}"
                )
            for c, target in enumerate(row):
                idx = r * self._cols + c
                cell = self._cells[idx]
                # cell.char only updates when the BOTTOM half lands. In the
                # hinge state (phase 1: top landed, bottom still pending --
                # the whole point of the animation) the character actually
                # on screen is cell.seq[cell.step], not the stale cell.char.
                # Retargeting from the stale value can walk the drum
                # backward from what's visibly displayed.
                cur = cell.seq[cell.step] if cell.phase == 1 else cell.char
                seq = self._drum.sequence(cur, target, self._max_steps)
                if not seq:
                    if cell.phase == 1:
                        # Mid-hinge and already arrived: the top face shows
                        # `cur`, which is exactly the new target, so no
                        # further travel is needed. But the bottom half is
                        # still physically in flight for THIS step and must
                        # still land to sync the display -- truncate the
                        # sequence right after the current step instead of
                        # abandoning it, leaving start_ms/step/phase (and so
                        # the pending bottom's due time) untouched.
                        cell.seq = cell.seq[: cell.step + 1]
                    else:
                        cell.seq = ()
                        cell.step = 0
                    continue
                cell.seq = seq
                cell.step = 0
                cell.phase = 0
                stagger = (
                    c * self._col_delay
                    + r * self._row_delay
                    + (idx * 7919) % (self._jitter + 1)   # deterministic jitter
                )
                cell.start_ms = now_ms + stagger

    def tick(self, now_ms: int) -> list[PaintOp]:
        ops: list[PaintOp] = []
        half_ms = self._step_ms // 2
        for idx, cell in enumerate(self._cells):
            # Bounded by construction, not by the due-time comparison: each
            # pass through the loop either flips phase (top -> bottom pending)
            # or flips phase and advances step. Two passes retire one step,
            # and step is capped at len(cell.seq) (<= max_steps), so this
            # cannot spin forever even if step_ms is 0.
            while cell.busy:
                due = cell.start_ms + (cell.step * 2 + cell.phase) * half_ms
                if due > now_ms:
                    break
                char = cell.seq[cell.step]
                if cell.phase == 0:
                    ops.append(PaintOp(idx, "top", char))
                    cell.phase = 1
                else:
                    ops.append(PaintOp(idx, "bottom", char))
                    cell.phase = 0
                    cell.char = char
                    cell.step += 1
        return ops

    def current_grid(self) -> tuple[str, ...]:
        return tuple(
            "".join(self._cells[r * self._cols + c].char for c in range(self._cols))
            for r in range(self._rows)
        )
