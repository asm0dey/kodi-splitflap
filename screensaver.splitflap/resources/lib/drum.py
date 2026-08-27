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

from .charset import BLANK, core_drum

MAX_STEPS = 12


def _ceil_div(a: int, b: int) -> int:
    """Integer ceiling division, avoiding float rounding at large values."""
    return -(-a // b)


class Drum:
    def __init__(self, charset: Iterable[str],
                 initial: Iterable[str] | None = None) -> None:
        """`charset` is everything renderable; `initial` is what starts on the drum.

        The two differ on purpose. A real module carries 40-odd flaps, and
        our glyph set can render 142 characters plus whatever a pack adds.
        Putting all of them on the drum makes Z -> A a 117-step walk that
        stride-sampling scatters through accented forms and symbols. So the
        drum starts at core size and grows only when a board actually needs
        a character -- see ensure().
        """
        self._available = set(charset)
        start = set(initial if initial is not None else core_drum())
        self._build(start & self._available or self._available)

    def _build(self, chars: Iterable[str]) -> None:
        # Ordered like a real drum, not by codepoint: blank, then letters,
        # then digits, then everything else. Codepoint order puts the whole
        # ASCII punctuation block between blank and 'A', so starting a board
        # from empty spun every cell through !"#$%&'()*+,-./0-9:;<=>?@ -- 33
        # steps of symbol soup before reaching a letter. Hardware groups the
        # drum so the common moves are short: blank -> letter is one step.
        rest = sorted(set(chars) - {BLANK})
        letters = [c for c in rest if c.isalpha()]
        digits = [c for c in rest if c.isdigit()]
        symbols = [c for c in rest if not c.isalpha() and not c.isdigit()]
        self.chars: tuple[str, ...] = (BLANK, *letters, *digits, *symbols)
        self._index: dict[str, int] = {c: i for i, c in enumerate(self.chars)}

    def ensure(self, chars: Iterable[str]) -> bool:
        """Add any renderable characters that are not yet on the drum.

        Returns whether the drum changed. Safe to call between flaps: cells
        hold characters, never drum indices, so a rebuilt drum cannot
        corrupt an animation already in flight.

        Additions land at the end rather than in sorted position, so a rare
        character stays out of the way of the common walks -- and so the
        indices of everything already on the drum do not move.
        """
        missing = [c for c in dict.fromkeys(chars)
                   if c in self._available and c not in self._index]
        if not missing:
            return False
        self.chars = (*self.chars, *missing)
        self._index = {c: i for i, c in enumerate(self.chars)}
        return True

    def _pos(self, ch: str) -> int:
        """Where a character currently sits.

        An unknown character reads as blank: after a mid-session glyph pack
        change the displayed character may no longer be on the drum, and
        flapping from blank is the sane recovery.
        """
        return self._index.get(ch, 0)

    def contains(self, ch: str) -> bool:
        """Whether `ch` is a character this drum can flap to.

        Callers that hand this drum a TARGET character (as opposed to a
        currently-displayed one -- see `_pos` above) must check this first:
        `distance`/`sequence` require the target to be on the drum and raise
        otherwise.
        """
        return ch in self._index

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
