"""Kodi infolabels as a source. The only Kodi-touching source.

Values come from Kodi's own weather service, so this addon needs no API
keys, no HTTP, and no secrets. Composition is pure and lives in
compose.py; this file only reads labels.
"""
from __future__ import annotations

import time
from collections.abc import Callable

import xbmc

from ..compose import compose
from .base import Content, Source

LABELS = {
    "time": "System.Time",
    "date": "System.Date",
    "weather_location": "Weather.Location",
    "weather_temp": "Weather.Temperature",
    "weather_conditions": "Weather.Conditions",
    "np_artist": "MusicPlayer.Artist",
    "np_title": "MusicPlayer.Title",
}


def read_values() -> dict[str, str]:
    return {key: xbmc.getInfoLabel(label) or "" for key, label in LABELS.items()}


class LiveInfoSource(Source):
    id = "liveinfo"

    def __init__(
        self,
        flags: dict[str, bool],
        combine: bool,
        reader: Callable[[], dict[str, str]] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._flags = flags
        self._combine = combine
        self._reader = reader or read_values
        self._clock = clock or time.time
        self._queue: list[Content] = []

    def next(self) -> Content:
        if not self._queue:
            self._queue = compose(
                self._flags, self._reader(), self._combine, self._clock()
            )
        if not self._queue:
            return Content()
        return self._queue.pop(0)
