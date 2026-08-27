"""Latest additions to Kodi's video library, one item per board.

A contributor add-on for the split-flap screensaver: it supplies content,
the screensaver renders it. Nothing here imports the screensaver -- the
contract is a next() returning lines, accents and refresh_in.

Movies and episodes are merged into one newest-first list and the top N
kept, with no per-type quota: if the last twenty things added were all
episodes, twenty episode boards is the honest answer.

Cadence is ours, not the screensaver's. Returning the same content again
paints nothing, so holding an item past the screensaver's own hold works;
refresh_in asks to be called back sooner when our dwell is shorter. The
screensaver never dictates how often a source changes.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

ADDON_ID = "script.splitflap.source.recentlyadded"
EMPTY_LINE = "NO RECENT ADDITIONS"
DEFAULT_DWELL = 15.0
DEFAULT_LIMIT = 20

Item = dict[str, Any]
Fetch = Callable[[int], tuple[list[Item], list[Item]]]


def merge(movies: list[Item], episodes: list[Item], limit: int) -> list[Item]:
    """Newest-first across both types, capped at limit.

    dateadded is Kodi's "YYYY-MM-DD HH:MM:SS", which sorts correctly as a
    string, so no parsing and nothing to raise on a malformed value -- a
    missing one sorts last rather than failing the whole board.
    """
    items = list(movies) + list(episodes)
    items.sort(key=lambda item: str(item.get("dateadded") or ""), reverse=True)
    return items[: max(int(limit), 1)]


def _episode_code(item: Item) -> str:
    return f"S{int(item.get('season') or 0):02d}E{int(item.get('episode') or 0):02d}"


def _lines_for(item: Item) -> list[str]:
    if item.get("showtitle"):
        detail = " ".join(part for part in (_episode_code(item),
                                            item.get("title") or "") if part)
        return [str(item["showtitle"]), detail]
    year = item.get("year") or 0
    lines = [str(item.get("title") or "")]
    if year:
        lines.append(str(year))
    return lines


def format_item(item: Item) -> dict[str, Any]:
    """One board: name, then year or episode code, each with a marker."""
    lines = _lines_for(item)
    return {
        "lines": lines,
        "accents": [{"before_line": n} for n in range(len(lines))],
        "refresh_in": None,
    }


class RecentlyAddedSource:
    id = ADDON_ID

    def __init__(
        self,
        fetch: Fetch,
        clock: Callable[[], float] | None = None,
        dwell: float = DEFAULT_DWELL,
        limit: int = DEFAULT_LIMIT,
    ) -> None:
        self._fetch = fetch
        self._clock = clock or time.time
        self._dwell = max(float(dwell), 0.0)
        self._limit = max(int(limit), 1)
        self._queue: list[Item] = []
        self._current: dict[str, Any] | None = None
        self._shown_at = 0.0

    def _refill(self) -> None:
        try:
            movies, episodes = self._fetch(self._limit)
        except Exception:
            # A library that went away (or a JSON-RPC hiccup) must not raise:
            # a source that raises is disabled for the whole session.
            return
        self._queue = merge(movies, episodes, self._limit)

    def _advance(self, now: float) -> None:
        if not self._queue:
            self._refill()
        item = self._queue.pop(0) if self._queue else None
        # A failed refetch leaves the queue empty; keep showing what we had
        # rather than blanking the board on a transient error.
        if item is not None:
            self._current = format_item(item)
        elif self._current is None:
            self._current = {"lines": [EMPTY_LINE],
                             "accents": [{"before_line": 0}],
                             "refresh_in": None}
        self._shown_at = now

    def next(self) -> dict[str, Any]:
        now = self._clock()
        if self._current is None or now - self._shown_at >= self._dwell:
            self._advance(now)
        content = dict(self._current or {})
        content["refresh_in"] = max(self._dwell - (now - self._shown_at), 0.0)
        return content


def kodi_fetch(limit: int) -> tuple[list[Item], list[Item]]:
    """Both recently-added lists in two JSON-RPC calls.

    Kodi already returns these newest-first; we ask for `limit` of each and
    let merge() decide how the two interleave.
    """
    import json

    import xbmc

    def call(method: str, properties: list[str], key: str) -> list[Item]:
        request = json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": method,
            "params": {"properties": properties,
                       "limits": {"start": 0, "end": limit}},
        })
        reply = json.loads(xbmc.executeJSONRPC(request))
        return reply.get("result", {}).get(key, []) or []

    movies = call("VideoLibrary.GetRecentlyAddedMovies",
                  ["title", "year", "dateadded"], "movies")
    episodes = call("VideoLibrary.GetRecentlyAddedEpisodes",
                    ["title", "showtitle", "season", "episode", "dateadded"],
                    "episodes")
    return movies, episodes


def create_source() -> RecentlyAddedSource:
    import xbmcaddon

    addon = xbmcaddon.Addon(ADDON_ID)
    try:
        dwell = float(addon.getSettingInt("hold_seconds"))
        limit = addon.getSettingInt("item_count")
    except Exception:
        dwell, limit = DEFAULT_DWELL, DEFAULT_LIMIT
    return RecentlyAddedSource(
        fetch=kodi_fetch,
        dwell=dwell or DEFAULT_DWELL,
        limit=limit or DEFAULT_LIMIT,
    )
