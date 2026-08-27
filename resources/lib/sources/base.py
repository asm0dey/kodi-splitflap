"""The contract every source implements, built-in or third-party.

Pull, not push: we ask, the source answers with content and a hint about
when to ask again. No callbacks, and no third-party code inside the render
loop.

One method suffices because identical content produces zero paint ops --
refreshing in place and advancing are indistinguishable at the render
layer. refresh_in is what stops a fast poll racing the phrase list.
"""
from collections.abc import Sequence
from typing import Any


class Content:
    __slots__ = ("accents", "lines", "refresh_in")

    def __init__(
        self,
        lines: Sequence[str] = (),
        accents: Sequence[dict[str, Any]] = (),
        refresh_in: float | None = None,
    ) -> None:
        self.lines: tuple[str, ...] = tuple(lines)
        self.accents: tuple[dict[str, Any], ...] = tuple(accents)
        self.refresh_in = refresh_in

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Content)
            and self.lines == other.lines
            and self.accents == other.accents
        )

    def __hash__(self) -> int:
        """Kept consistent with __eq__, which ignores refresh_in.

        Defining __eq__ without __hash__ silently makes the class
        unhashable, so a caller putting Content in a set or dict would get
        a TypeError far from the cause.
        """
        return hash((self.lines, self.accents))

    def __repr__(self) -> str:
        return (f"Content(lines={self.lines!r}, accents={self.accents!r}, "
                f"refresh_in={self.refresh_in!r})")


class Source:
    """Duck-typed base. Subclasses set id and implement next()."""

    id = "source"

    def next(self) -> Content:
        raise NotImplementedError
