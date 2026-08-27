
from resources.lib.sources.remote import RemoteCache, parse_remote


def test_parses_plain_text():
    assert parse_remote("ONE\nTWO\n# skip\n") == ["ONE", "TWO"]


def test_parses_json_array():
    assert parse_remote('["ONE", "TWO"]') == ["ONE", "TWO"]


def test_parses_json_object_with_phrases_key():
    assert parse_remote('{"phrases": ["ONE", "TWO"]}') == ["ONE", "TWO"]


def test_json_non_string_entries_are_dropped():
    assert parse_remote('["ONE", 5, null, "TWO"]') == ["ONE", "TWO"]


def test_malformed_json_falls_back_to_plain_text():
    assert parse_remote('["ONE", "TWO"') == ['["ONE", "TWO"']


def test_empty_payload_yields_empty_list():
    assert parse_remote("") == []


def test_successful_fetch_is_written_to_cache():
    written = {}
    cache = RemoteCache(read=lambda: None, write=lambda t: written.setdefault("t", t))
    got = cache.load(lambda url: "ONE\nTWO", "http://example/x")
    assert got == ["ONE", "TWO"]
    assert written["t"] == "ONE\nTWO"


def test_failed_fetch_falls_back_to_cache():
    def boom(url):
        raise OSError("network down")

    cache = RemoteCache(read=lambda: "CACHED", write=lambda t: None)
    assert cache.load(boom, "http://example/x") == ["CACHED"]


def test_failed_fetch_with_no_cache_yields_empty_not_an_exception():
    def boom(url):
        raise OSError("network down")

    cache = RemoteCache(read=lambda: None, write=lambda t: None)
    assert cache.load(boom, "http://example/x") == []


def test_cache_write_failure_does_not_lose_the_fetched_content():
    def bad_write(text):
        raise OSError("read-only fs")

    cache = RemoteCache(read=lambda: None, write=bad_write)
    assert cache.load(lambda url: "ONE", "http://example/x") == ["ONE"]
