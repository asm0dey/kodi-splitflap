"""Split-Flap Board screensaver entry point."""
from __future__ import annotations

import os
import random
import threading
import time
import traceback
from typing import TYPE_CHECKING, Any

import xbmc
import xbmcgui
import xbmcvfs
from resources.lib import config
from resources.lib.board import BoardView
from resources.lib.charset import bundled_charset
from resources.lib.drum import Drum
from resources.lib.flap import FlapMachine
from resources.lib.geometry import compute
from resources.lib.glyphs import GlyphIndex, glyph_dirs, pack_letterset
from resources.lib.layout import build as build_board
from resources.lib.rotator import Rotator
from resources.lib.sources.liveinfo import LiveInfoSource
from resources.lib.sources.phrases import PhraseSource, parse_phrases
from resources.lib.sources.remote import RemoteCache, http_get

if TYPE_CHECKING:
    # Only for the _build_source return annotation below -- the real import
    # of discovery.py is lazy (inside _build_source), since it touches Kodi
    # only through function-body imports and has no reason to load when the
    # source is liveinfo or phrases.
    from resources.lib.sources.discovery import _SourceLike

FRAME_MS = 50
# A card falls in 100ms, so 50ms frames would show it at two positions and
# read as a stutter rather than a fall. Paid only while something is moving:
# a settled board is still ticked at FRAME_MS, and the whole transition is
# about a second.
FOLD_FRAME_MS = 25
# Bounded generously against the 50ms frame period: a join this long is
# imperceptible, but it still guarantees `del window` never races a thread
# still touching controls, without risking a hung shutdown if the thread is
# wedged (the thread is also a daemon, so a timed-out join can't keep the
# process alive either).
THREAD_JOIN_TIMEOUT_S = 2.0


def log(msg: str) -> None:
    xbmc.log(f"splitflap: {msg}", xbmc.LOGINFO)


def log_error(context: str) -> None:
    xbmc.log(f"splitflap: {context}:\n{traceback.format_exc()}", xbmc.LOGERROR)


def _read_text(path: str) -> str:
    # xbmcvfs, not a bare open(): phrases_file is a type="path" setting, so
    # the user can point it at an SMB/NFS share via Kodi's file picker --
    # only Kodi's own VFS (not the local libc open()) can read those.
    if not xbmcvfs.exists(path):
        return ""
    with xbmcvfs.File(path) as handle:
        return handle.read()


def _read_pack_text(path: str) -> str | None:
    """VFS text reader for `glyphs.pack_letterset`.

    Returns None on a missing file, matching that function's contract --
    it stays pure and Kodi-free, this is the Kodi-touching side effect
    injected into it (same pattern as `_read_text` above).
    """
    if not xbmcvfs.exists(path):
        return None
    with xbmcvfs.File(path) as handle:
        return handle.read()


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _build_source(cfg: dict[str, Any]) -> LiveInfoSource | PhraseSource | _SourceLike:
    if cfg["source"] == "contributor":
        from resources.lib.sources.discovery import (
            discover,
            kodi_list_addons,
            kodi_load_module,
        )
        wanted = cfg["source_addon_id"]
        for source in discover(kodi_list_addons, kodi_load_module, log):
            if not wanted or source.id == wanted:
                return source
        log(f"no contributor source {wanted!r} found, falling back to live info")
        return LiveInfoSource(cfg["info_flags"], cfg["info_combine"])
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
        self._was_settled = True
        self._cfg = config.read()

    def onInit(self) -> None:
        # Guarded end to end: an unhandled exception here would leave
        # self._thread never started, so nothing would ever call close()
        # and the modal screensaver would be stuck open with no way to
        # dismiss it short of force-quitting Kodi.
        try:
            cfg = self._cfg
            geo = compute(rows=cfg["rows"])
            dirs = glyph_dirs(cfg["profile"], cfg["addon_path"], cfg["glyph_pack"])

            # Only characters offered as CANDIDATES ever reach the drum --
            # a pack's glyph files existing on disk isn't enough on its own
            # (GlyphIndex.charset only probes what it's given). A pack can
            # ADD characters the bundle doesn't cover (e.g. Cyrillic), so
            # its declared letterset must be unioned in here.
            candidates = set(bundled_charset())
            pack = cfg["glyph_pack"]
            if pack:
                pack_chars, warning = pack_letterset(
                    f"resource://{pack}", _read_pack_text
                )
                if warning:
                    log(f"glyph pack {pack!r} letterset unavailable: {warning}")
                candidates.update(pack_chars)

            index = GlyphIndex(dirs, xbmcvfs.exists)
            available = index.charset(candidates)
            drum = Drum(available)

            self._geo = geo
            self._view = BoardView(self, geo, index,
                                    cfg["letter_colour"], cfg["accent_colour"])
            self._view.build()
            self._flap = FlapMachine(drum, geo.rows, geo.cols,
                                      max_steps=cfg["max_steps"])
            # daemon=True: if the join in __main__ times out on a wedged
            # thread, that must never keep the Kodi process alive.
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        except Exception:
            log_error("onInit failed")
            self.close()

    def _run(self) -> None:
        # Source construction happens here, on the background thread, not in
        # onInit -- a phrases_url fetch is a blocking network call, and
        # onInit runs on Kodi's GUI thread. Building the rotator on the GUI
        # thread would freeze the whole interface (not just this
        # screensaver) for up to remote.TIMEOUT_S seconds.
        # Guarded end to end: an unhandled exception here would otherwise
        # skip close() entirely (no try/finally), leaving doModal() blocked
        # forever -- onAction only flips self._stop, it never closes the
        # window itself. Live triggers include _read_text/_read_pack_text's
        # VFS reads, paint(), and source discover().
        try:
            cfg = self._cfg
            rotator = Rotator(
                _build_source(cfg), cfg["hold_seconds"],
                fallback=LiveInfoSource(cfg["info_flags"], cfg["info_combine"]),
                log=log,
            )
            self._loop(rotator, xbmc.Monitor(), cfg["animate_flaps"])
        except Exception:
            log_error("render loop failed")
        finally:
            # _run is the SOLE caller of close(), and only after the try
            # block above has fully exited (normally or via the except
            # above) -- so nothing ever calls a control method
            # (paint/retarget/tick/set_accents, all above) after close()
            # runs. onAction only flips self._stop; it must never call
            # close() itself, or the GUI thread could tear the window down
            # while this thread is still mid-paint.
            self.close()

    def _loop(self, rotator: Rotator, monitor: xbmc.Monitor,
              animate: bool) -> None:
        """Run frames until stopped, waiting out the rest of each one.

        Its own method so the frame loop reads without the one-time source
        construction and the shutdown guard _run wraps it in.
        """
        while not self._stop and not monitor.abortRequested():
            if not xbmc.getCondVisibility("System.ScreenSaverActive"):
                break
            # monotonic, not wall-clock time: an NTP step (e.g. a Fire TV
            # Stick with no RTC, stepping its clock just after boot --
            # exactly when a screensaver first runs) would otherwise
            # stall every flap on a backward step or dump a cell's whole
            # sequence in one tick on a forward step. Rotator and
            # FlapMachine only ever compare deltas of this clock, so
            # monotonic works for both. LiveInfoSource is unaffected --
            # it owns its own wall-clock (time.time by default) for
            # `seconds_to_next_minute`, independent of this loop's clock.
            now = time.monotonic()
            settled = self._frame(rotator, now, int(now * 1000), animate)
            period = FRAME_MS if settled or not animate else FOLD_FRAME_MS
            if monitor.waitForAbort(period / 1000.0):
                break

    def _frame(self, rotator: Rotator, now: float, now_ms: int,
               animate: bool) -> bool:
        """Draw one frame, answering whether the board is settled.

        _was_settled lives on the instance rather than in _loop because
        the edge it marks -- the tick a board finishes on -- is found
        here, and only the caller's period depends on the answer.
        """
        content = rotator.poll(now)
        if content is not None:
            board = build_board(content.lines, content.accents,
                                 self._geo.rows, self._geo.cols)
            self._view.set_accents(board.accents)
            # retarget and tick share one clock (now_ms) -- see
            # flap.FlapMachine.retarget's own docstring on why a
            # mismatched clock makes every cell dump its full
            # sequence on the first tick instead of animating.
            self._flap.retarget(board.grid, now_ms)
            self._was_settled = False
        ops = self._flap.tick(now_ms)
        if ops:
            self._view.paint(ops)
        # After paint, and on the same clock tick() just consumed:
        # folds() describes the gap between the landings tick()
        # reports, so a stale clock would draw a card that has
        # already arrived.
        if animate:
            self._view.fold(self._flap.folds(now_ms))
        settled = self._flap.settled
        if settled and not self._was_settled:
            rotator.settled(now)
            self._was_settled = True
        return settled

    def onAction(self, action: xbmcgui.Action) -> None:
        self._stop = True


if __name__ == "__main__":
    window = Screensaver("script-splitflap.xml",
                          xbmcvfs.translatePath(
                              config.ADDON.getAddonInfo("path")),
                          "default", "1080i")
    window.doModal()
    # doModal() returns once the window is closed (only _run's self.close()
    # call does that -- see above). Join before deleting the window object
    # so the background thread can never touch a control on a window that
    # is being torn down.
    thread = getattr(window, "_thread", None)
    if thread is not None:
        thread.join(timeout=THREAD_JOIN_TIMEOUT_S)
        if thread.is_alive():
            xbmc.log(
                "splitflap: background thread still running after "
                f"{THREAD_JOIN_TIMEOUT_S}s join timeout; leaking it rather "
                "than hanging shutdown",
                xbmc.LOGWARNING,
            )
    del window
