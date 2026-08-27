"""Resolve a character and half to a glyph file.

Order: runtime cache, then the selected pack, then the bundled set, then
tofu. Tofu is bundled like any other glyph, so the fallback can never
itself be missing -- if it is, that is a packaging bug and we say so
loudly rather than recursing.
"""
from collections.abc import Callable, Iterable

from .charset import TOFU
from .glyphgen import glyph_filename


class GlyphIndex:
    def __init__(self, search_dirs: list[str], exists: Callable[[str], bool]) -> None:
        self._dirs = list(search_dirs)
        self._exists = exists

    def _find(self, ch: str, half: str) -> str | None:
        name = glyph_filename(ch, half)
        for d in self._dirs:
            path = f"{d}/{name}"
            if self._exists(path):
                return path
        return None

    def path(self, ch: str, half: str) -> str:
        found = self._find(ch, half)
        if found is not None:
            return found
        fallback = self._find(TOFU, half)
        if fallback is None:
            raise LookupError(
                f"tofu glyph {TOFU!r} is missing from every search dir {self._dirs!r} -- "
                "the bundled set is incomplete"
            )
        return fallback

    def charset(self, candidates: Iterable[str]) -> set[str]:
        """Characters with BOTH halves present, so a tile can render them."""
        out = set()
        for ch in candidates:
            if self._find(ch, "top") and self._find(ch, "bottom"):
                out.add(ch)
        return out
