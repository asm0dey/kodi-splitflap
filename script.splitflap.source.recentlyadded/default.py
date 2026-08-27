"""Launched from the add-on browser: say what this add-on is for.

It exists to be discovered by the Split-Flap Board screensaver, not to be
run -- but an add-on Kodi will happily launch should answer when launched.
"""
import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon()

xbmcgui.Dialog().ok(ADDON.getAddonInfo("name"), ADDON.getLocalizedString(30020))
