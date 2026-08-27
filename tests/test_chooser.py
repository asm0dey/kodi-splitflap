"""The picker's pure parts. Kodistubs stands in for Kodi at import time."""
import chooser

CHOICES = [("script.splitflap.source.a", "Alpha"),
           ("script.splitflap.source.b", "Beta")]


def test_every_installed_contributor_is_a_row():
    assert chooser.menu(CHOICES, "") == ["Alpha", "Beta"]


def test_the_current_pick_is_marked():
    assert chooser.menu(CHOICES, "script.splitflap.source.b") == [
        "Alpha", "> Beta"]


def test_configure_opens_the_picked_add_on():
    assert chooser.target(CHOICES, "script.splitflap.source.b") == (
        "script.splitflap.source.b")


def test_configure_follows_the_only_installed_add_on_when_none_is_picked():
    assert chooser.target(CHOICES[:1], "") == "script.splitflap.source.a"


def test_configure_has_no_target_while_a_choice_is_still_open():
    assert chooser.target(CHOICES, "") == ""


def test_configure_has_no_target_with_nothing_installed():
    assert chooser.target([], "") == ""
