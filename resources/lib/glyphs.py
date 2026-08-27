"""Resolve a character and half to a glyph file.

Order: runtime cache, then the selected pack, then the bundled set, then
tofu. Tofu is bundled like any other glyph, so the fallback can never
itself be missing -- if it is, that is a packaging bug and we say so
loudly rather than recursing.
"""
from collections.abc import Callable, Iterable

from .charset import TOFU
from .glyphgen import glyph_filename


def glyph_dirs(profile: str, addon_path: str, glyph_pack: str) -> list[str]:
    """Search-dir order for glyph resolution: profile override, pack, bundled.

    Order is load-bearing: earlier directories win when a character exists
    in more than one, so a per-profile override always beats a configured
    glyph pack, which always beats the bundled set. `glyph_pack` empty means
    no pack is configured, so that entry is omitted rather than pointing at
    an empty `resource://` URI.
    """
    dirs = [f"{profile}/glyphs"]
    if glyph_pack:
        dirs.append(f"resource://{glyph_pack}")
    dirs.append(f"{addon_path}/resources/media/glyphs")
    return dirs


class GlyphIndex:
    def __init__(self, search_dirs: list[str], exists: Callable[[str], bool]) -> None:
        self._dirs = list(search_dirs)
        self._exists = exists
        # Resolved (ch, half) -> path, populated on first lookup. Safe
        # because the index is built once per screensaver activation and
        # the glyph files on disk can't change mid-session -- a stale cache
        # entry isn't a scenario that arises here.
        self._resolved: dict[tuple[str, str], str] = {}

    def _find(self, ch: str, half: str) -> str | None:
        name = glyph_filename(ch, half)
        for d in self._dirs:
            path = f"{d}/{name}"
            if self._exists(path):
                return path
        return None

    def path(self, ch: str, half: str) -> str:
        key = (ch, half)
        cached = self._resolved.get(key)
        if cached is not None:
            return cached

        found = self._find(ch, half)
        if found is None:
            found = self._find(TOFU, half)
            if found is None:
                raise LookupError(
                    f"tofu glyph {TOFU!r} is missing from every search dir "
                    f"{self._dirs!r} -- "
                    "the bundled set is incomplete"
                )
        self._resolved[key] = found
        return found

    def charset(self, candidates: Iterable[str]) -> set[str]:
        """Characters with BOTH halves present, so a tile can render them."""
        out = set()
        for ch in candidates:
            if self._find(ch, "top") and self._find(ch, "bottom"):
                out.add(ch)
        return out
