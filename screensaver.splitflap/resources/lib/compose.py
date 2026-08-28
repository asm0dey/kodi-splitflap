"""Turn live-info checkbox state plus resolved values into boards.

Pure: the caller resolves Kodi infolabels and hands the strings in.

Empty-token rule: a value resolving empty drops its line, and a board
resolving wholly empty is skipped -- so an unconfigured weather addon
means the weather board never appears, rather than a board of blanks.
"""
from collections.abc import Sequence
from typing import NamedTuple

from .layout import Accent
from .sources.base import Content

STATIC_REFRESH_S = 900.0


def seconds_to_next_minute(now_seconds: float) -> float:
    """Calculate seconds remaining until the next minute boundary.

    At exactly 0 seconds past the minute, return 60.0 (wait a full minute).
    """
    return 60.0 - (now_seconds % 60.0)


def _nonempty(*parts: str) -> str:
    """Join non-empty strings with spaces."""
    return " ".join(p.strip() for p in parts if p and p.strip())


class Section(NamedTuple):
    """One block of related lines. `ticks` means it refreshes on the minute."""

    lines: list[str]
    ticks: bool


def _sections(
    flags: dict[str, bool],
    values: dict[str, str],
) -> list[Section]:
    """Build section list from flags and values."""
    out: list[Section] = []
    if flags.get("time"):
        out.append(Section([values.get("time", "")], ticks=True))
    if flags.get("date"):
        out.append(Section([values.get("date", "")], ticks=False))
    if flags.get("weather"):
        out.append(Section(
            [
                values.get("weather_location", ""),
                _nonempty(
                    values.get("weather_temp", ""),
                    values.get("weather_conditions", ""),
                ),
            ],
            ticks=False,
        ))
    if flags.get("nowplaying"):
        out.append(Section(
            [values.get("np_artist", ""), values.get("np_title", "")],
            ticks=False,
        ))
    return out


def _to_content(sections: Sequence[Section], now_seconds: float) -> Content:
    """Convert sections to a single Content board.

    Empty lines are dropped. If a section contributes no non-empty lines,
    it is skipped. If all sections resolve empty, returns empty Content.

    Accents are placed at the last line of each section.
    """
    lines: list[str] = []
    accents: list[Accent] = []
    ticks = False
    for section in sections:
        kept = [line.strip() for line in section.lines if line and line.strip()]
        if not kept:
            continue
        accents.append({"before_line": len(lines) + len(kept) - 1})
        lines.extend(kept)
        ticks = ticks or section.ticks
    if not lines:
        return Content()
    refresh = seconds_to_next_minute(now_seconds) if ticks else STATIC_REFRESH_S
    return Content(lines=lines, accents=accents, refresh_in=refresh)


def compose(
    flags: dict[str, bool],
    values: dict[str, str],
    combine: bool,
    now_seconds: float = 0.0,
) -> list[Content]:
    """Compose live-info boards from checkbox state and resolved values.

    Args:
        flags: Dict with bool flags: time, date, weather, nowplaying.
        values: Dict with infolabel values (time, date, weather_*, np_*).
        combine: If True, merge all into one board; if False, one board per section.
        now_seconds: Current time in seconds (for minute-boundary refresh calc).

    Returns:
        List of Content boards. Wholly-empty boards are skipped.
    """
    sections = _sections(flags, values)
    if not sections:
        return []
    if combine:
        content = _to_content(sections, now_seconds)
        return [content] if content.lines else []
    out: list[Content] = []
    for section in sections:
        content = _to_content([section], now_seconds)
        if content.lines:
            out.append(content)
    return out
