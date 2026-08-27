import source as recent


def movie(title, year, added):
    return {"title": title, "year": year, "dateadded": added}


def episode(show, season, ep, title, added):
    return {"showtitle": show, "season": season, "episode": ep,
            "title": title, "dateadded": added}


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def source(items, dwell=10.0, limit=20, clock=None, fetches=None, calls=None):
    """A source over one fixed library snapshot, unless fetches is given.

    Pass `calls` to observe how often the library was queried.
    """
    calls = [] if calls is None else calls
    pages = fetches if fetches is not None else [items]

    def fetch(_limit):
        calls.append(_limit)
        return pages[min(len(calls) - 1, len(pages) - 1)]

    return recent.RecentlyAddedSource(
        fetch=fetch, clock=clock or Clock(), dwell=dwell, limit=limit)


# --- merge ---------------------------------------------------------------

def test_merge_orders_newest_first_across_both_types():
    movies = [movie("DUNE", 2024, "2024-03-02 10:00:00")]
    eps = [episode("THE BEAR", 3, 4, "HONEYDEW", "2024-03-03 09:00:00")]
    assert [i.get("title") for i in recent.merge(movies, eps, 10)] == [
        "HONEYDEW", "DUNE"]


def test_merge_keeps_only_the_top_n():
    eps = [episode("SHOW", 1, n, f"E{n}", f"2024-03-{n:02d} 00:00:00")
           for n in range(1, 6)]
    assert len(recent.merge([], eps, 3)) == 3


def test_merge_top_n_may_be_all_of_one_type():
    movies = [movie("OLD", 1999, "1999-01-01 00:00:00")]
    eps = [episode("SHOW", 1, n, f"E{n}", f"2024-03-{n:02d} 00:00:00")
           for n in range(1, 4)]
    assert all("showtitle" in i for i in recent.merge(movies, eps, 3))


def test_merge_tolerates_a_missing_dateadded():
    items = recent.merge([movie("NO DATE", 2024, "")], [], 5)
    assert items[0]["title"] == "NO DATE"


# --- formatting ----------------------------------------------------------

def test_movie_shows_title_then_year():
    assert recent.format_item(movie("DUNE PART TWO", 2024, "x"))["lines"] == [
        "DUNE PART TWO", "2024"]


def test_episode_shows_show_then_code_and_title():
    item = episode("THE BEAR", 3, 4, "HONEYDEW", "x")
    assert recent.format_item(item)["lines"] == ["THE BEAR", "S03E04 HONEYDEW"]


def test_episode_without_a_title_shows_just_the_code():
    assert recent.format_item(episode("THE BEAR", 3, 4, "", "x"))["lines"] == [
        "THE BEAR", "S03E04"]


def test_movie_without_a_year_shows_only_the_title():
    assert recent.format_item(movie("UNDATED", 0, "x"))["lines"] == ["UNDATED"]


def test_both_lines_are_marked():
    accents = recent.format_item(movie("DUNE", 2024, "x"))["accents"]
    assert accents == [{"before_line": 0}, {"before_line": 1}]


def test_a_single_line_is_marked_once():
    accents = recent.format_item(movie("UNDATED", 0, "x"))["accents"]
    assert accents == [{"before_line": 0}]


# --- cycling and dwell ---------------------------------------------------

def test_each_item_gets_its_own_board():
    src = source(([], [episode("SHOW", 1, n, f"E{n}",
                               f"2024-03-{n:02d} 00:00:00")
                       for n in (2, 1)]), dwell=0.0)
    first, second = src.next()["lines"][1], src.next()["lines"][1]
    assert (first, second) == ("S01E02 E2", "S01E01 E1")


def test_the_same_item_is_held_until_the_dwell_expires():
    clock = Clock()
    src = source(([movie("A", 1, "2024-01-02 00:00:00"),
                   movie("B", 2, "2024-01-01 00:00:00")], []),
                 dwell=10.0, clock=clock)
    assert src.next()["lines"][0] == "A"
    clock.now = 9.0
    assert src.next()["lines"][0] == "A"
    clock.now = 10.0
    assert src.next()["lines"][0] == "B"


def test_refresh_in_is_the_time_left_of_the_dwell():
    clock = Clock()
    src = source(([movie("A", 1, "x")], []), dwell=10.0, clock=clock)
    assert src.next()["refresh_in"] == 10.0
    clock.now = 4.0
    assert src.next()["refresh_in"] == 6.0


def test_wrapping_past_the_last_item_refetches():
    first = ([movie("A", 1, "x")], [])
    second = ([movie("B", 2, "x")], [])
    calls = []
    src = source(None, fetches=[first, second], dwell=0.0, calls=calls)
    assert [src.next()["lines"][0] for _ in range(2)] == ["A", "B"]
    assert len(calls) == 2


def test_the_fetch_asks_for_the_configured_count():
    calls = []
    source(([], []), limit=7, calls=calls).next()
    assert calls == [7]


# --- degenerate libraries ------------------------------------------------

def test_an_empty_library_says_so():
    assert source(([], [])).next()["lines"] == ["NO RECENT ADDITIONS"]


def test_a_failing_fetch_does_not_raise():
    def boom(_limit):
        raise RuntimeError("no library")

    src = recent.RecentlyAddedSource(
        fetch=boom, clock=Clock(), dwell=1.0, limit=5)
    assert src.next()["lines"] == ["NO RECENT ADDITIONS"]


def test_a_failing_refetch_keeps_showing_the_last_known_items():
    calls = []

    def flaky(_limit):
        calls.append(1)
        if len(calls) == 1:
            return ([movie("A", 1, "x")], [])
        raise RuntimeError("library went away")

    src = recent.RecentlyAddedSource(
        fetch=flaky, clock=Clock(), dwell=0.0, limit=5)
    assert src.next()["lines"][0] == "A"
    assert src.next()["lines"][0] == "A"
