from resources.lib.charset import bundled_charset
from resources.lib.geometry import compute
from resources.lib.layout import ELLIPSIS, build
from resources.lib.sources.phrases import parse_phrases, split_author

PATH = "resources/data/phrases.txt"


def load():
    with open(PATH, encoding="utf-8") as handle:
        return parse_phrases(handle.read())


def test_file_exists_and_has_enough_phrases():
    phrases = load()
    assert 20 <= len(phrases) <= 40


def test_every_phrase_fits_at_default_geometry():
    """'Guaranteed to fit' is enforced, not hoped for."""
    g = compute(rows=6)
    for phrase in load():
        board = build(split_author(phrase), (), g.rows, g.cols)
        joined = "".join(board.grid)
        assert ELLIPSIS not in joined, (
            f"{phrase!r} ellipsises at {g.rows}x{g.cols}"
        )


def test_every_character_is_in_the_bundled_charset():
    cs = set(bundled_charset())
    for phrase in load():
        for part in split_author(phrase):
            for ch in part.upper():
                assert ch in cs, f"{ch!r} in {phrase!r} is not bundled"


def test_phrases_are_unique():
    phrases = load()
    assert len(phrases) == len(set(phrases))


def test_attributed_phrases_use_the_author_separator():
    for phrase in load():
        assert "|" not in phrase        # separator is \n, not a pipe
