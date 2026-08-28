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

import dataclasses
from collections.abc import Sequence
from typing import NamedTuple

from .charset import BLANK, TOFU
from .drum import MAX_STEPS, Drum
from .geometry import Half

STEP_MS = 200          # real hardware runs at five flaps per second
COL_DELAY_MS = 18      # left-to-right ripple
ROW_DELAY_MS = 40
JITTER_MS = 12


class PaintOp(NamedTuple):
    cell: int
    half: Half         # never a bool
    char: str


@dataclasses.dataclass(slots=True)
class _Cell:
    """One tile's animation state. Mutable: it IS the state machine."""

    char: str
    # Not a field: a fresh cell shows the same character on both halves,
    # and after that the two diverge for exactly one half-step -- the hinge.
    top_char: str = dataclasses.field(init=False)
    seq: tuple[str, ...] = ()
    step: int = 0
    phase: int = 0              # 0 = top pending, 1 = bottom pending
    start_ms: int = 0

    def __post_init__(self) -> None:
        self.top_char = self.char

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

        # Grow the drum to cover this board before computing any walk. The
        # drum starts at hardware size (blank, A-Z, 0-9, common marks) so
        # ordinary text spins contiguously; a character outside that -- an
        # accented capital, a currency sign, another script -- joins the drum
        # the first time a board asks for it. Cells hold characters rather
        # than drum indices, so growing it here cannot disturb a flap already
        # in flight.
        self._drum.ensure("".join(grid))

        for r, row in enumerate(grid):
            if len(row) != self._cols:
                raise ValueError(
                    f"row {r} has {len(row)} cells, expected {self._cols}"
                )
            for c, raw_target in enumerate(row):
                idx = r * self._cols + c
                self._aim(self._cells[idx], raw_target, idx, r, c, now_ms)

    def _aim(self, cell: _Cell, raw_target: str, idx: int,
             r: int, c: int, now_ms: int) -> None:
        """Point one cell at one character, and set when its walk starts."""
        # A target absent from this drum (e.g. a glyph the source text
        # contains but the active charset/pack does not cover) would
        # otherwise raise KeyError deep in Drum.distance. Tofu is itself
        # always on the drum (glyphs.GlyphIndex guarantees the tofu glyph
        # is bundled), so substituting it here is the target-side
        # counterpart to `Drum._pos` treating an unknown CURRENT character
        # as blank.
        target = raw_target if self._drum.contains(raw_target) else TOFU
        # Walk from what is VISIBLY on the top half, not from cell.char --
        # which tracks the bottom and lags by one for the whole walk.
        # Starting from the stale bottom value would walk the drum backward
        # from what the viewer sees.
        seq = self._drum.sequence(cell.top_char, target, self._max_steps)
        if not seq:
            self._converge(cell)
            return
        # Padded with a repeat of the target: the bottom half trails the top
        # by one entry, so it needs one extra step to land on the same
        # character. The duplicated top op is suppressed in tick(), so this
        # costs no visible frame and no setImage.
        cell.seq = (*seq, seq[-1])
        cell.step = 0
        cell.phase = 0
        cell.start_ms = now_ms + (
            c * self._col_delay
            + r * self._row_delay
            + (idx * 7919) % (self._jitter + 1)   # deterministic jitter
        )

    @staticmethod
    def _converge(cell: _Cell) -> None:
        """The top already shows the target; let the bottom catch up.

        Abandoning the walk outright would strand the tile permanently
        mismatched -- top on the target, bottom on whatever it last landed
        -- so a bottom that still trails gets a one-entry sequence.
        """
        cell.step = 0
        if cell.char != cell.top_char:
            cell.seq = (cell.top_char, cell.top_char)
            cell.phase = 1
        else:
            cell.seq = ()
            cell.phase = 0

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
                self._half_step(ops, idx, cell)
        return ops

    @staticmethod
    def _half_step(ops: list[PaintOp], idx: int, cell: _Cell) -> None:
        """Retire one half-step: phase 0 paints the top, phase 1 the bottom."""
        if cell.phase == 0:
            # The top shows the incoming character. Skipped when it already
            # does -- the sequence's padded final entry repeats the target,
            # and repainting it would cost a setImage for no visible change.
            char = cell.seq[cell.step]
            if char != cell.top_char:
                ops.append(PaintOp(idx, "top", char))
                cell.top_char = char
            cell.phase = 1
            return
        # The bottom trails the top by one entry for the whole walk,
        # converging only on the last step. That sustained mismatch IS the
        # hinge: resolving it every step made the tile show a clean settled
        # letter between every pair of frames, which reads as letters
        # changing rather than a card falling.
        if cell.step > 0:
            trailing = cell.seq[cell.step - 1]
            ops.append(PaintOp(idx, "bottom", trailing))
            cell.char = trailing
        cell.phase = 0
        cell.step += 1

    def current_grid(self) -> tuple[str, ...]:
        return tuple(
            "".join(self._cells[r * self._cols + c].char for c in range(self._cols))
            for r in range(self._rows)
        )
