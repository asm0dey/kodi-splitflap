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
        self.chars: tuple[str, ...] = (BLANK, *tuple(rest))
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
        if max_steps < 1:
            raise ValueError(f"max_steps must be at least 1, got {max_steps}")

        distance = self.distance(cur, target)
        if distance == 0:
            return ()

        # Spread the gap over at most max_steps flaps, then work out how many
        # flaps that stride actually needs. The target is always appended
        # explicitly below, so the walk lands on it regardless of rounding.
        # Rounding the stride UP is what keeps `steps` within the max_steps
        # cap: a smaller (floor-rounded) stride would need more hops to
        # cover the same distance, so `steps` could exceed max_steps.
        stride = _ceil_div(distance, max_steps)
        steps = _ceil_div(distance, stride)

        # The sampled indices generally skip over the target, so the walk stops
        # one flap short and the target is placed explicitly. Under the cap the
        # stride is 1, which makes this the plain contiguous walk.
        start = self._pos(cur)
        n = len(self.chars)
        out = [self.chars[(start + k * stride) % n] for k in range(1, steps)]
        out.append(target)
        return tuple(out)
