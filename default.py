"""Split-Flap Board screensaver entry point."""
from __future__ import annotations

import os
import random
import sys
import threading
import time
from typing import Any

import xbmc
import xbmcgui
import xbmcvfs

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 "resources", "lib"))

from resources.lib import config
from resources.lib.board import BoardView
from resources.lib.charset import bundled_charset
from resources.lib.drum import Drum
from resources.lib.flap import FlapMachine
from resources.lib.geometry import compute
from resources.lib.glyphs import GlyphIndex
from resources.lib.layout import build as build_board
from resources.lib.rotator import Rotator
from resources.lib.sources.liveinfo import LiveInfoSource
from resources.lib.sources.phrases import PhraseSource, parse_phrases
from resources.lib.sources.remote import RemoteCache, http_get

FRAME_MS = 50


def log(msg: str) -> None:
    xbmc.log(f"splitflap: {msg}", xbmc.LOGINFO)


def _read_text(path: str) -> str:
    if not xbmcvfs.exists(path):
        return ""
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _glyph_dirs(cfg: dict[str, Any]) -> list[str]:
    dirs = [os.path.join(cfg["profile"], "glyphs")]
    if cfg["glyph_pack"]:
        dirs.append(f"resource://{cfg['glyph_pack']}")
    dirs.append(os.path.join(cfg["addon_path"], "resources", "media", "glyphs"))
    return dirs


def _build_source(cfg: dict[str, Any]) -> LiveInfoSource | PhraseSource:
    if cfg["source"] == "phrases":
        pools = [parse_phrases(_read_text(cfg["phrases_file"]))]
        if cfg["phrases_url"]:
            cache_path = os.path.join(cfg["profile"], "remote.txt")
            cache = RemoteCache(
                read=lambda: _read_text(cache_path) or None,
                write=lambda text: _write_text(cache_path, text),
            )
            pools.append(cache.load(http_get, cfg["phrases_url"]))
        return PhraseSource(pools, random.Random())
    return LiveInfoSource(cfg["info_flags"], cfg["info_combine"])


class Screensaver(xbmcgui.WindowXMLDialog):
    def __init__(self, *args: object, **kwargs: object) -> None:
        self._stop = False
        self._cfg = config.read()

    def onInit(self) -> None:
        cfg = self._cfg
        geo = compute(rows=cfg["rows"])
        index = GlyphIndex(_glyph_dirs(cfg), xbmcvfs.exists)
        available = index.charset(bundled_charset())
        drum = Drum(available)

        self._geo = geo
        self._view = BoardView(self, geo, index,
                                cfg["letter_colour"], cfg["accent_colour"])
        self._view.build()
        self._flap = FlapMachine(drum, geo.rows, geo.cols,
                                  max_steps=cfg["max_steps"])
        threading.Thread(target=self._run).start()

    def _run(self) -> None:
        # Source construction happens here, on the background thread, not in
        # onInit -- a phrases_url fetch is a blocking network call, and
        # onInit runs on Kodi's GUI thread. Building the rotator on the GUI
        # thread would freeze the whole interface (not just this
        # screensaver) for up to remote.TIMEOUT_S seconds.
        cfg = self._cfg
        rotator = Rotator(
            _build_source(cfg), cfg["hold_seconds"],
            fallback=LiveInfoSource(cfg["info_flags"], cfg["info_combine"]),
            log=log,
        )
        monitor = xbmc.Monitor()
        was_settled = True
        while not self._stop and not monitor.abortRequested():
            if not xbmc.getCondVisibility("System.ScreenSaverActive"):
                break
            now = time.time()
            now_ms = int(now * 1000)
            content = rotator.poll(now)
            if content is not None:
                board = build_board(content.lines, content.accents,
                                     self._geo.rows, self._geo.cols)
                self._view.set_accents(board.accents)
                # retarget and tick share one clock (now_ms) -- see
                # flap.FlapMachine.retarget's own docstring on why a
                # mismatched clock makes every cell dump its full sequence
                # on the first tick instead of animating.
                self._flap.retarget(board.grid, now_ms)
                was_settled = False
            ops = self._flap.tick(now_ms)
            if ops:
                self._view.paint(ops)
            if self._flap.settled and not was_settled:
                rotator.settled(now)
                was_settled = True
            if monitor.waitForAbort(FRAME_MS / 1000.0):
                break
        self.close()

    def onAction(self, action: xbmcgui.Action) -> None:
        self._stop = True
        self.close()


if __name__ == "__main__":
    window = Screensaver("script-splitflap.xml",
                          xbmcvfs.translatePath(
                              config.ADDON.getAddonInfo("path")),
                          "default", "1080i")
    window.doModal()
    del window
