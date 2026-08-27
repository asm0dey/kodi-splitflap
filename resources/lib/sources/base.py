"""The contract every source implements, built-in or third-party.

Pull, not push: we ask, the source answers with content and a hint about
when to ask again. No callbacks, and no third-party code inside the render
loop.

One method suffices because identical content produces zero paint ops --
refreshing in place and advancing are indistinguishable at the render
layer. refresh_in is what stops a fast poll racing the phrase list.
"""
from typing import Any, Dict, Optional, Sequence, Tuple


class Content(object):
    __slots__ = ("lines", "accents", "refresh_in")

    def __init__(self, lines=(), accents=(), refresh_in=None):
        # type: (Sequence[str], Sequence[Dict[str, Any]], Optional[float]) -> None
        self.lines = tuple(lines)      # type: Tuple[str, ...]
        self.accents = tuple(accents)
        self.refresh_in = refresh_in

    def __eq__(self, other):
        return (
            isinstance(other, Content)
            and self.lines == other.lines
            and self.accents == other.accents
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "Content(lines=%r, accents=%r, refresh_in=%r)" % (
            self.lines, self.accents, self.refresh_in
        )


class Source(object):
    """Duck-typed base. Subclasses set id and implement next()."""

    id = "source"

    def next(self):
        # type: () -> Content
        raise NotImplementedError
