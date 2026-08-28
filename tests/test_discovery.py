from resources.lib.sources.base import Content
from resources.lib.sources.discovery import (
    SOURCE_PREFIX,
    discover,
    list_choices,
)


class Module:
    def __init__(self, factory):
        self.create_source = factory


class Good:
    id = "good"

    def next(self):
        return Content(["HI"])


def modules(mapping):
    return lambda addon_id, path: mapping[addon_id]


def test_ignores_addons_without_the_prefix():
    listed = [("script.something.else", "/a"), ("plugin.video.x", "/b")]
    assert discover(lambda: listed, modules({}), lambda m: None) == []


def test_loads_a_matching_addon():
    aid = SOURCE_PREFIX + "quotes"
    found = discover(
        lambda: [(aid, "/a")],
        modules({aid: Module(lambda: Good())}),
        lambda m: None,
    )
    assert len(found) == 1
    assert found[0].next().lines == ("HI",)


def test_addon_missing_create_source_is_skipped_and_logged():
    aid = SOURCE_PREFIX + "broken"
    logged = []
    found = discover(
        lambda: [(aid, "/a")],
        modules({aid: object()}),
        logged.append,
    )
    assert found == []
    assert logged
    assert aid in logged[0]


def test_addon_returning_a_non_source_is_skipped():
    aid = SOURCE_PREFIX + "wrong"
    logged = []
    found = discover(
        lambda: [(aid, "/a")],
        modules({aid: Module(lambda: "not a source")}),
        logged.append,
    )
    assert found == []
    assert logged


def test_raising_factory_does_not_abort_the_whole_scan():
    """One broken contributor must not hide the working ones."""
    bad, good = SOURCE_PREFIX + "bad", SOURCE_PREFIX + "good"

    def boom():
        raise RuntimeError("addon exploded at import")

    logged = []
    found = discover(
        lambda: [(bad, "/a"), (good, "/b")],
        modules({bad: Module(boom), good: Module(lambda: Good())}),
        logged.append,
    )
    assert len(found) == 1
    assert logged


def test_listing_failure_yields_no_sources_rather_than_raising():
    def boom():
        raise RuntimeError("json-rpc down")

    logged = []
    assert discover(boom, modules({}), logged.append) == []
    assert logged


def names(mapping):
    def name_of(addon_id):
        name = mapping[addon_id]
        if isinstance(name, Exception):
            raise name
        return name
    return name_of


def test_choices_label_contributors_by_their_add_on_name():
    listed = [(SOURCE_PREFIX + "recent", "/a")]
    name_of = names({SOURCE_PREFIX + "recent": "Recently Added"})
    assert list_choices(listed, name_of) == [
        (SOURCE_PREFIX + "recent", "Recently Added")]


def test_choices_ignore_add_ons_that_are_not_contributors():
    listed = [("script.module.requests", "/r"), (SOURCE_PREFIX + "a", "/a")]
    assert [i for i, _ in list_choices(listed, names({SOURCE_PREFIX + "a": "A"}))] == [
        SOURCE_PREFIX + "a"]


def test_choices_are_sorted_by_label():
    listed = [(SOURCE_PREFIX + "z", "/z"), (SOURCE_PREFIX + "a", "/a")]
    mapping = {SOURCE_PREFIX + "z": "Alpha", SOURCE_PREFIX + "a": "Zulu"}
    assert [n for _, n in list_choices(listed, names(mapping))] == ["Alpha", "Zulu"]


def test_a_contributor_whose_name_cannot_be_read_falls_back_to_its_id():
    listed = [(SOURCE_PREFIX + "broken", "/b")]
    mapping = {SOURCE_PREFIX + "broken": RuntimeError("gone")}
    assert list_choices(listed, names(mapping)) == [
        (SOURCE_PREFIX + "broken", SOURCE_PREFIX + "broken")]
