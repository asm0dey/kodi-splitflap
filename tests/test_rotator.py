from resources.lib.rotator import Rotator
from resources.lib.sources.base import Content


class Fake:
    id = "fake"

    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = 0

    def next(self):
        self.calls += 1
        return self.contents[(self.calls - 1) % len(self.contents)]


class Boom:
    id = "boom"

    def next(self):
        raise RuntimeError("third-party addon exploded")


def test_first_poll_returns_content_immediately():
    r = Rotator(Fake([Content(["A"])]), hold_s=10)
    content = r.poll(0.0)
    assert content is not None
    assert content.lines == ("A",)


def test_no_further_content_until_hold_expires():
    src = Fake([Content(["A"]), Content(["B"])])
    r = Rotator(src, hold_s=10)
    r.poll(0.0)
    r.settled(1.0)
    assert r.poll(5.0) is None
    assert src.calls == 1


def test_hold_counts_from_when_the_flap_settles():
    """Raising hold must double reading time, not add a variable flap."""
    src = Fake([Content(["A"]), Content(["B"])])
    r = Rotator(src, hold_s=10)
    r.poll(0.0)
    r.settled(3.0)              # flap took three seconds
    assert r.poll(12.0) is None  # would have fired at 10 if counted from poll
    content = r.poll(13.1)
    assert content is not None
    assert content.lines == ("B",)


def test_refresh_in_fires_before_hold():
    src = Fake([Content(["12:45"], refresh_in=5.0),
                Content(["12:46"], refresh_in=60.0)])
    r = Rotator(src, hold_s=100)
    r.poll(0.0)
    r.settled(0.5)
    content = r.poll(6.0)
    assert content is not None
    assert content.lines == ("12:46",)


def test_raising_source_is_disabled_and_falls_back():
    fallback = Fake([Content(["FALLBACK"])])
    logged = []
    r = Rotator(Boom(), hold_s=10, fallback=fallback, log=logged.append)
    content = r.poll(0.0)
    assert content is not None
    assert content.lines == ("FALLBACK",)
    assert r.failed
    assert logged and "boom" in logged[0].lower()


def test_disabled_source_is_not_retried_within_the_session():
    class CountingBoom:
        id = "boom"
        calls = 0

        def next(self):
            CountingBoom.calls += 1
            raise RuntimeError("nope")

    src = CountingBoom()
    r = Rotator(src, hold_s=1, fallback=Fake([Content(["F"])]))
    r.poll(0.0)
    r.settled(0.1)
    r.poll(5.0)
    assert CountingBoom.calls == 1


def test_raising_source_with_no_fallback_yields_empty_content():
    r = Rotator(Boom(), hold_s=10, fallback=None)
    content = r.poll(0.0)
    assert content is not None
    assert content.lines == ()
