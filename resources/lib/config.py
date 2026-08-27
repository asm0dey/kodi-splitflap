"""Read settings once per activation.

Settings cannot be edited while the screensaver runs, so nothing needs to
handle a live change -- we read at activation and rebuild geometry then.
"""
from __future__ import annotations

from typing import Any

import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()


def _path(special: str) -> str:
    return xbmcvfs.translatePath(special)


def read() -> dict[str, Any]:
    get = ADDON.getSetting
    get_bool = ADDON.getSettingBool
    get_int = ADDON.getSettingInt
    addon_path = _path(ADDON.getAddonInfo("path"))
    profile = _path(ADDON.getAddonInfo("profile"))
    phrases_file = get("phrases_file") or (addon_path + "/resources/data/phrases.txt")
    return {
        "rows": get_int("rows"),
        "hold_seconds": get_int("hold_seconds"),
        "max_steps": get_int("max_steps"),
        "letter_colour": get("letter_colour") or "E8E8E8",
        "accent_colour": get("accent_colour") or "2B5CE6",
        "source": get("source") or "liveinfo",
        "info_flags": {
            "time": get_bool("info_time"),
            "date": get_bool("info_date"),
            "weather": get_bool("info_weather"),
            "nowplaying": get_bool("info_nowplaying"),
        },
        "info_combine": get_bool("info_combine"),
        "phrases_file": phrases_file,
        "phrases_url": get("phrases_url"),
        "glyph_pack": get("glyph_pack"),
        "addon_path": addon_path,
        "profile": profile,
    }
