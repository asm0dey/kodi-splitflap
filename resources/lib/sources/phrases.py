"""Phrases from a file and/or a remote URL, merged into one pool.

The file/URL distinction is plumbing, not content, so they merge -- which
also makes "my curated list plus a remote one" work for free.

Ordering is shuffled without repeat until the pool is exhausted. Plain
random visibly repeats within a few boards and reads as a bug.
"""
import random
from typing import List, Sequence

from .base import Content, Source

AUTHOR_SEP = "\\n"


def parse_phrases(text):
    # type: (str) -> List[str]
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def split_author(phrase):
    # type: (str) -> List[str]
    return [part.strip() for part in phrase.split(AUTHOR_SEP)]


class PhraseSource(Source):
    id = "phrases"

    def __init__(self, pools, rng=None):
        # type: (Sequence[Sequence[str]], random.Random) -> None
        self._pool = [p for pool in pools for p in pool]
        self._rng = rng or random.Random()
        self._order = []       # type: List[int]

    def _advance(self):
        # type: () -> str
        if not self._pool:
            return ""
        if not self._order:
            self._order = list(range(len(self._pool)))
            self._rng.shuffle(self._order)
        return self._pool[self._order.pop()]

    def next(self):
        # type: () -> Content
        phrase = self._advance()
        if not phrase:
            return Content(lines=(), accents=(), refresh_in=None)
        lines = split_author(phrase)
        accents = [{"corner": "top-left"}, {"corner": "top-right"}]
        if len(lines) > 1:
            accents.append({"before_line": len(lines) - 1})
        return Content(lines=lines, accents=accents, refresh_in=None)
