"""Settings-button entry point: pick a source add-on, or open its settings.

A Kodi settings button can only run a builtin, and the add-on we want to act
on is only known at runtime -- so the button runs this script, which does the
dynamic part. Two buttons: one picks among the installed contributors, one opens the
picked add-on's own settings.

Deliberately not an entry in Program add-ons: the xbmc.python.script
extension declares no <provides>, so RunScript reaches it while the add-on
browser does not offer it as something to launch.
"""
from __future__ import annotations

import sys
from typing import Any

import xbmc
import xbmcaddon
import xbmcgui
from resources.lib.sources.discovery import kodi_list_addons, list_choices

ADDON = xbmcaddon.Addon()
SETTING = "source_addon_id"


def log(message: str) -> None:
    # INFO, not DEBUG: this script exists to be clicked, and "did the button
    # even run?" is the first question when it appears to do nothing.
    xbmc.log(f"splitflap chooser: {message}", xbmc.LOGINFO)


def _name_of(addon_id: str) -> str:
    return xbmcaddon.Addon(addon_id).getAddonInfo("name")


def menu(choices: list[tuple[str, str]], current: str) -> list[Any]:
    """The dialog's rows: every contributor, the current one marked."""
    return [f"> {label}" if cid == current else label for cid, label in choices]


def target(choices: list[tuple[str, str]], current: str) -> str:
    """Whose settings the Configure button opens.

    Nothing picked but exactly one contributor installed is the same case
    the screensaver itself treats as "obviously that one", so Configure
    follows it rather than demanding a redundant pick.
    """
    if current:
        return current
    return choices[0][0] if len(choices) == 1 else ""


def _notify(string_id: int) -> None:
    xbmcgui.Dialog().notification(
        ADDON.getAddonInfo("name"), ADDON.getLocalizedString(string_id))


def open_settings(addon_id: str) -> None:
    # The add-on settings dialog we were launched from is modal; a second
    # settings dialog opened underneath it would be invisible. Close ours
    # first, then open theirs.
    xbmc.executebuiltin("Dialog.Close(addonsettings)")
    xbmc.executebuiltin(f"Addon.OpenSettings({addon_id})")


def pick() -> None:
    choices = list_choices(kodi_list_addons(), _name_of)
    log(f"{len(choices)} source add-on(s) installed")
    if not choices:
        _notify(30027)
        return
    current = ADDON.getSetting(SETTING)
    index = xbmcgui.Dialog().select(
        ADDON.getLocalizedString(30025), menu(choices, current))
    if index < 0:
        return
    ADDON.setSetting(SETTING, choices[index][0])
    log(f"picked {choices[index][0]}")


def configure() -> None:
    addon_id = target(list_choices(kodi_list_addons(), _name_of),
                      ADDON.getSetting(SETTING))
    log(f"configuring {addon_id!r}")
    if not addon_id:
        _notify(30028)
        return
    open_settings(addon_id)


ACTIONS = {"pick": pick, "configure": configure}


def main(argv: list[str]) -> None:
    log(f"started with {argv[1:]!r}")
    ACTIONS.get(argv[1] if len(argv) > 1 else "pick", pick)()


if __name__ == "__main__":
    main(sys.argv)
