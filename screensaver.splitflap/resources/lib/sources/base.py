"""The contract every source implements, built-in or third-party.

Pull, not push: we ask, the source answers with content and a hint about
when to ask again. No callbacks, and no third-party code inside the render
loop.

One method suffices because identical content produces zero paint ops --
refreshing in place and advancing are indistinguishable at the render
layer. refresh_in is what stops a fast poll racing the phrase list.
"""
import dataclasses
from collections.abc import Sequence
from typing import Any


@dataclasses.dataclass(frozen=True, slots=True)
class Content:
    """One board's worth of content, plus when to ask for the next.

    Frozen because the render loop holds on to the last Content and compares
    the next one against it -- a source mutating what it already returned
    would make that comparison lie. Declared as Sequence because sources
    hand us lists; __post_init__ freezes them into tuples so equality and
    hashing hold. refresh_in is out of the comparison: two Contents that
    differ only in when to ask again are the same board.
    """

    lines: Sequence[str] = ()
    accents: Sequence[dict[str, Any]] = ()
    refresh_in: float | None = dataclasses.field(default=None, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "lines", tuple(self.lines))
        object.__setattr__(self, "accents", tuple(self.accents))


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
