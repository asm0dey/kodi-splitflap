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


def coerce(value: Any) -> Content:
    """Whatever a source answered, as a Content.

    Contributors are documented as being able to return "any object with a
    next() method" answering with a plain dict -- so the render loop must
    never assume attribute access. Anything missing defaults the way an
    omitted argument to Content() does, because a contributor that only
    fills in `lines` is the common case.
    """
    if isinstance(value, Content):
        return value
    read = value.get if isinstance(value, dict) else (
        lambda key, default=None: getattr(value, key, default))
    return Content(
        lines=read("lines", ()) or (),
        accents=read("accents", ()) or (),
        refresh_in=read("refresh_in", None),
    )


class Source:
    """Duck-typed base. Subclasses set id and implement next()."""

    id = "source"

    def next(self) -> Content:
        raise NotImplementedError
