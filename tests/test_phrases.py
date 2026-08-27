import random

from resources.lib.sources.base import Content
from resources.lib.sources.phrases import PhraseSource, parse_phrases, split_author


def test_parse_drops_comments_and_blank_lines():
    text = "# a comment\n\nFIRST\n   \nSECOND\n# trailing\n"
    assert parse_phrases(text) == ["FIRST", "SECOND"]


def test_parse_keeps_hash_inside_a_phrase():
    assert parse_phrases("NUMBER # ONE") == ["NUMBER # ONE"]


def test_split_author_on_literal_backslash_n():
    """A real newline cannot serve: one file line is one phrase."""
    assert split_author("THE ONLY WAY OUT\\nROBERT FROST") == [
        "THE ONLY WAY OUT", "ROBERT FROST"
    ]


def test_split_author_without_author():
    assert split_author("JUST A PHRASE") == ["JUST A PHRASE"]


def test_next_returns_content():
    s = PhraseSource([["ONE"]], random.Random(0))
    c = s.next()
    assert isinstance(c, Content)
    assert c.lines == ("ONE",)


def test_refresh_in_is_none_so_phrases_only_advance_on_hold():
    s = PhraseSource([["ONE"]], random.Random(0))
    assert s.next().refresh_in is None


def test_pools_are_merged():
    s = PhraseSource([["A"], ["B"]], random.Random(0))
    seen = {s.next().lines[0] for _ in range(2)}
    assert seen == {"A", "B"}


def test_shuffle_exhausts_the_pool_before_repeating():
    pool = [str(i) for i in range(10)]
    s = PhraseSource([pool], random.Random(1))
    first = [s.next().lines[0] for _ in range(10)]
    assert sorted(first) == sorted(pool)


def test_reshuffles_after_exhaustion():
    pool = [str(i) for i in range(10)]
    s = PhraseSource([pool], random.Random(1))
    first = [s.next().lines[0] for _ in range(10)]
    second = [s.next().lines[0] for _ in range(10)]
    assert sorted(second) == sorted(pool)
    assert first != second


def test_accents_are_the_two_top_corners():
    s = PhraseSource([["ONE"]], random.Random(0))
    accents = s.next().accents
    assert {"corner": "top-left"} in accents
    assert {"corner": "top-right"} in accents


def test_author_line_gets_an_accent_before_it():
    s = PhraseSource([["PHRASE\\nAUTHOR"]], random.Random(0))
    c = s.next()
    assert c.lines == ("PHRASE", "AUTHOR")
    assert {"before_line": 1} in c.accents


def test_empty_pool_yields_a_blank_board_not_a_crash():
    s = PhraseSource([[]], random.Random(0))
    assert s.next().lines == ()
