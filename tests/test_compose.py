from resources.lib.compose import compose, seconds_to_next_minute

VALUES = {
    "time": "12:45",
    "date": "MON 27 AUG",
    "weather_location": "SYDNEY",
    "weather_temp": "17°",
    "weather_conditions": "RAIN",
    "np_artist": "MILES DAVIS",
    "np_title": "SO WHAT",
}
ALL_OFF = {"time": False, "date": False, "weather": False, "nowplaying": False}


def flags(**kw):
    out = dict(ALL_OFF)
    out.update(kw)
    return out


def test_time_only():
    boards = compose(flags(time=True), VALUES, combine=True)
    assert len(boards) == 1
    assert boards[0].lines == ("12:45",)


def test_weather_only_is_two_lines():
    boards = compose(flags(weather=True), VALUES, combine=True)
    assert boards[0].lines == ("SYDNEY", "17° RAIN")


def test_time_and_weather_combined_on_one_board():
    boards = compose(flags(time=True, weather=True), VALUES, combine=True)
    assert len(boards) == 1
    assert boards[0].lines == ("12:45", "SYDNEY", "17° RAIN")


def test_time_and_weather_separate_boards():
    boards = compose(flags(time=True, weather=True), VALUES, combine=False)
    assert len(boards) == 2
    assert boards[0].lines == ("12:45",)
    assert boards[1].lines == ("SYDNEY", "17° RAIN")


def test_accent_sits_before_the_time_line():
    boards = compose(flags(time=True), VALUES, combine=True)
    assert {"before_line": 0} in boards[0].accents


def test_accent_sits_before_the_weather_line():
    boards = compose(flags(weather=True), VALUES, combine=True)
    assert {"before_line": 1} in boards[0].accents


def test_empty_value_drops_its_line():
    values = dict(VALUES, weather_location="")
    boards = compose(flags(weather=True), values, combine=True)
    assert boards[0].lines == ("17° RAIN",)


def test_wholly_empty_board_is_skipped():
    """No weather addon configured means the weather board never appears."""
    values = dict(VALUES, weather_location="", weather_temp="",
                  weather_conditions="")
    boards = compose(flags(weather=True), values, combine=False)
    assert boards == []


def test_nothing_ticked_yields_no_boards():
    assert compose(flags(), VALUES, combine=True) == []


def test_nowplaying_lines():
    boards = compose(flags(nowplaying=True), VALUES, combine=True)
    assert boards[0].lines == ("MILES DAVIS", "SO WHAT")


def test_refresh_in_counts_down_to_the_next_minute():
    boards = compose(flags(time=True), VALUES, combine=True)
    assert boards[0].refresh_in is not None
    assert 0 < boards[0].refresh_in <= 60


def test_no_time_shown_means_no_minute_refresh():
    boards = compose(flags(weather=True), VALUES, combine=True)
    assert boards[0].refresh_in is None or boards[0].refresh_in > 60


def test_seconds_to_next_minute():
    assert seconds_to_next_minute(0.0) == 60.0
    assert seconds_to_next_minute(59.0) == 1.0
    assert seconds_to_next_minute(120.5) == 59.5


def test_combined_time_and_weather_refresh_is_minute_derived():
    """Verify that time+weather combined board gets minute-level refresh.

    This pins the `ticks = ticks or section["ticks"]` fold, which ORs across
    sections. Without this OR, refactoring to `ticks = section["ticks"]`
    would silently change the refresh to 900s (STATIC_REFRESH_S), making
    the clock update every 15 minutes instead of every minute -- visibly
    broken but undetected without this assertion.
    """
    from resources.lib.compose import STATIC_REFRESH_S

    boards = compose(flags(time=True, weather=True), VALUES, combine=True)
    assert len(boards) == 1
    assert boards[0].refresh_in is not None
    # Must be minute-derived (0 < x <= 60), NOT STATIC_REFRESH_S
    assert 0 < boards[0].refresh_in <= 60
    assert boards[0].refresh_in != STATIC_REFRESH_S


def test_accent_index_shifts_in_combined_board():
    """Verify accent arithmetic when weather section follows time section.

    _to_content computes `{"before_line": len(lines) + len(kept) - 1}`,
    offsetting by accumulated lines. The time section contributes 1 line,
    so the weather accent should land at index 2 (weather's last line),
    not index 1.
    """
    boards = compose(flags(time=True, weather=True), VALUES, combine=True)
    assert len(boards) == 1
    # Time accent at index 0 (time is the only line in its section)
    assert {"before_line": 0} in boards[0].accents
    # Weather accent at index 2 (time line + weather's two lines - 1)
    assert {"before_line": 2} in boards[0].accents
