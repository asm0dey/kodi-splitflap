"""The ordered, circular sequence a tile cycles through.

Blank first, then codepoints ascending. Motion is forward-only and wraps,
exactly as a physical drum: a target below the current codepoint spins the
whole way round, which is why a clock's minutes digit spins on every
rollover while the tens digit ticks once.

Our drum is longer than any real board's -- Solari modules carried 40 to 64
flaps, extended ASCII gives us ~142 -- so a full wrap is stride-sampled
rather than contiguous. MAX_STEPS is a tuning constant, not a derived one.
"""
from collections.abc import Iterable

from .charset import BLANK

MAX_STEPS = 12


def _ceil_div(a: int, b: int) -> int:
    """Integer ceiling division, avoiding float rounding at large values."""
    return -(-a // b)


class Drum:
    def __init__(self, charset: Iterable[str]) -> None:
        rest = sorted(set(charset) - {BLANK})
        self.chars: tuple[str, ...] = (BLANK,) + tuple(rest)
        self._index: dict[str, int] = {c: i for i, c in enumerate(self.chars)}

    def _pos(self, ch: str) -> int:
        """Where a character currently sits.

        An unknown character reads as blank: after a mid-session glyph pack
        change the displayed character may no longer be on the drum, and
        flapping from blank is the sane recovery.
        """
        return self._index.get(ch, 0)

    def distance(self, cur: str, target: str) -> int:
        """Steps forward from cur to target, wrapping. Never negative."""
        n = len(self.chars)
        return (self._index[target] - self._pos(cur)) % n

    def sequence(self, cur: str, target: str,
                 max_steps: int = MAX_STEPS) -> tuple[str, ...]:
        """The characters to display in order, ending exactly on target.

        Motion is forward through the drum, wrapping past the end. When the
        distance exceeds max_steps the walk is sampled at a fixed stride so
        it still completes in at most max_steps flaps.
        """
        # TODO(human): implement the stride-sampled forward walk.
        #
        # Contract the flap machine relies on:
        #
        #   d = Drum("0123456789")        # chars == (BLANK,'0','1',...,'9')
        #   d.sequence("1", "2")   -> ("2",)          adjacent: one flap
        #   d.sequence("B", "B")   -> ()              already there: no flaps
        #   d.sequence("9", "0")   -> wraps the whole drum, len <= max_steps
        #
        # Rules:
        #   * the LAST element is always exactly `target`, whatever the stride
        #   * every element is a member of self.chars
        #   * len(result) <= max_steps
        #   * indices move forward only, wrapping modulo len(self.chars)
        #   * an unknown `target` raises KeyError (use self._index[target])
        #
        # You already have distance() for the forward-wrapping gap. The step
        # size is that distance spread over at most max_steps flaps -- and
        # _ceil_div is there because a stride that rounds DOWN overshoots the
        # target, while one that rounds up never does.
        #
        # The one to think about: with a stride > 1 the sampled indices will
        # generally not land on target exactly. Decide how the walk ends.
        raise NotImplementedError("Drum.sequence")
