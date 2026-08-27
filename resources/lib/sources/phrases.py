"""Phrases from a file and/or a remote URL, merged into one pool.

The file/URL distinction is plumbing, not content, so they merge -- which
also makes "my curated list plus a remote one" work for free.

Ordering is shuffled without repeat until the pool is exhausted. Plain
random visibly repeats within a few boards and reads as a bug.
"""
import random
from collections.abc import Sequence
from typing import Any

from .base import Content, Source

AUTHOR_SEP = "\\n"


def parse_phrases(text: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def split_author(phrase: str) -> list[str]:
    return [part.strip() for part in phrase.split(AUTHOR_SEP)]


class PhraseSource(Source):
    id = "phrases"

    def __init__(
        self,
        pools: Sequence[Sequence[str]],
        rng: random.Random | None = None,
    ) -> None:
        self._pool = [p for pool in pools for p in pool]
        self._rng = rng or random.Random()
        self._order: list[int] = []

    def _advance(self) -> str:
        if not self._pool:
            return ""
        if not self._order:
            self._order = list(range(len(self._pool)))
            self._rng.shuffle(self._order)
        return self._pool[self._order.pop()]

    def next(self) -> Content:
        phrase = self._advance()
        if not phrase:
            return Content(lines=(), accents=(), refresh_in=None)
        lines = split_author(phrase)
        accents: list[dict[str, Any]] = [
            {"corner": "top-left"},
            {"corner": "top-right"},
        ]
        if len(lines) > 1:
            accents.append({"before_line": len(lines) - 1})
        return Content(lines=lines, accents=accents, refresh_in=None)
