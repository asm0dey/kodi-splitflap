"""Fetch a phrase list over HTTP, with a disk cache as the fallback.

Parsing is pure and tested; the network call is injected, so nothing here
touches a socket under test. The caller runs load() on a background thread
-- it must never sit on the render loop.
"""
import json
from collections.abc import Callable
from urllib.request import urlopen

from .phrases import parse_phrases

TIMEOUT_S = 10


def parse_remote(payload: str) -> list[str]:
    """Parse payload as plain text, JSON array, or JSON object with phrases key.

    Falls back to plain-text parsing when JSON is malformed.
    Non-string entries in JSON arrays are dropped.
    """
    text = (payload or "").strip()
    if not text:
        return []
    if text[0] in "[{":
        try:
            data = json.loads(text)
        except ValueError:
            return parse_phrases(payload)
        if isinstance(data, dict):
            data = data.get("phrases", [])
        if isinstance(data, list):
            return [
                item.strip()
                for item in data
                if isinstance(item, str) and item.strip()
            ]
        return []
    return parse_phrases(payload)


def http_get(url: str) -> str:
    """Real fetcher. Injected so tests never open a socket."""
    handle = urlopen(url, timeout=TIMEOUT_S)
    try:
        return handle.read().decode("utf-8", "replace")
    finally:
        handle.close()


class RemoteCache:
    """Fetch a phrase list from a URL with disk cache fallback.

    If fetch succeeds, parse it and write to cache. If fetch fails, read
    from cache. If both fail, return empty list.

    A cache write failure never discards good fetched content.
    """

    def __init__(
        self,
        read: Callable[[], str | None],
        write: Callable[[str], None],
    ) -> None:
        self._read = read
        self._write = write

    def load(self, fetch: Callable[[str], str], url: str) -> list[str]:
        """Fetch from URL, parse, cache, and return; fall back to cached content.

        Args:
            fetch: Function that takes URL and returns text (network call).
            url: URL to fetch.

        Returns:
            Parsed phrase list. Empty if fetch and cache both fail or are unavailable.
        """
        try:
            payload = fetch(url)
        except Exception:
            cached = self._read()
            return parse_remote(cached) if cached else []
        try:
            self._write(payload)
        except Exception:
            pass  # a stale cache is not worth losing a good fetch over
        return parse_remote(payload)
