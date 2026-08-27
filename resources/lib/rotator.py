"""Advance the active source and own display timing.

Exactly one source is active; there is no cross-source rotation. The
source owns data freshness via refresh_in, we own presentation via hold,
so a source can never override a user's display setting.

Hold counts from when the flap SETTLES, so raising it doubles reading
time rather than adding a variable flap on top.

A source that raises is disabled for the session and we fall back. A
source that HANGS freezes the screensaver -- accepted, since the built-in
sources cannot hang; revisit when contributor discovery ships.
"""
from collections.abc import Callable
from typing import Protocol

from .sources.base import Content


class Source(Protocol):
    """Duck-typed source interface."""

    def next(self) -> Content:
        ...


class Rotator:
    def __init__(
        self,
        source: Source,
        hold_s: float,
        fallback: Source | None = None,
        log: Callable[[str], None] | None = None,
    ) -> None:
        self._source = source
        self._hold = float(hold_s)
        self._fallback = fallback
        self._log = log or (lambda msg: None)
        self._current: Content | None = None
        self._settled_at: float | None = None
        self._polled_at: float | None = None
        self.failed = False

    def _call(self, now_s: float) -> Content:
        if not self.failed:
            try:
                return self._source.next()
            except Exception as exc:
                self.failed = True
                source_id = getattr(self._source, "id", "?")
                self._log(
                    f"source {source_id!r} raised {exc!r} -- disabled for this "
                    "session, falling back"
                )
        if self._fallback is not None:
            try:
                return self._fallback.next()
            except Exception as exc:
                self._log(f"fallback source also raised {exc!r}")
        return Content()

    def settled(self, now_s: float) -> None:
        """Tell the rotator the flap finished. Starts the hold clock."""
        self._settled_at = now_s

    def poll(self, now_s: float) -> Content | None:
        if self._current is None:
            self._current = self._call(now_s)
            self._polled_at = now_s
            self._settled_at = None
            return self._current

        refresh = self._current.refresh_in
        refresh_due = (
            refresh is not None
            and self._polled_at is not None
            and now_s - self._polled_at >= refresh
        )
        hold_due = (
            self._settled_at is not None
            and now_s - self._settled_at >= self._hold
        )
        if not (refresh_due or hold_due):
            return None

        self._current = self._call(now_s)
        self._polled_at = now_s
        self._settled_at = None
        return self._current
