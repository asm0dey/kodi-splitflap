from resources.lib import layout
from resources.lib.charset import TOFU, bundled_charset
from resources.lib.drum import Drum
from resources.lib.flap import STEP_MS, FlapMachine


def machine(rows=1, cols=3, chars="AB C123"):
    return FlapMachine(Drum(chars), rows=rows, cols=cols,
                       col_delay_ms=0, row_delay_ms=0, jitter_ms=0)


def drain(m, start=0, limit=200):
    """Run the machine to completion, returning every op emitted."""
    ops, t = [], start
    for _ in range(limit):
        ops.extend(m.tick(t))
        if m.settled:
            break
        t += STEP_MS // 2
    return ops


def test_starts_settled_and_emits_nothing():
    m = machine()
    assert m.settled
    assert m.tick(0) == []


def test_settled_board_emits_zero_ops():
    """The whole perf argument rests on this."""
    m = machine()
    m.retarget(("   ",))
    drain(m)
    assert m.settled
    assert m.tick(10 ** 6) == []


def test_single_step_change_emits_two_half_ops():
    m = machine(cols=1, chars="12 ")
    m.retarget(("1",))
    drain(m)
    m.retarget(("2",))
    ops = drain(m)
    assert [(o.half, o.char) for o in ops] == [("top", "2"), ("bottom", "2")]


def test_top_half_leads_the_bottom_half():
    m = machine(cols=1, chars="12 ")
    m.retarget(("1",))
    drain(m)
    m.retarget(("2",))
    ops = drain(m)
    assert ops[0].half == "top"
    assert ops[1].half == "bottom"


def test_a_step_takes_STEP_MS():
    """200ms, the reported real-hardware rate of five flaps per second."""
    assert STEP_MS == 200


def test_unchanged_cells_do_not_move():
    m = machine(cols=3, chars="AB ")
    m.retarget(("AAA",))
    drain(m)
    m.retarget(("ABA",))
    ops = drain(m)
    assert {o.cell for o in ops} == {1}


def test_cell_index_is_row_major():
    m = FlapMachine(Drum("AB "), rows=2, cols=3,
                    col_delay_ms=0, row_delay_ms=0, jitter_ms=0)
    m.retarget(("   ", "  A"))
    ops = drain(m)
    assert {o.cell for o in ops} == {5}


def test_stagger_makes_later_columns_start_later():
    m = FlapMachine(Drum("AB "), rows=1, cols=3,
                    col_delay_ms=100, row_delay_ms=0, jitter_ms=0)
    m.retarget(("AAA",))
    first_tick = m.tick(0)
    assert {o.cell for o in first_tick} == {0}


def test_retarget_mid_flight_redirects_without_restarting_the_board():
    m = machine(cols=1, chars="123 ")
    m.retarget(("3",))
    m.tick(0)
    m.retarget(("1",))
    ops = drain(m, start=STEP_MS)
    assert ops[-1].char == "1"


def test_mid_flight_retarget_during_hinge_continues_from_the_displayed_char():
    """Retargeting while a cell is in the hinge state (top landed, bottom
    still pending -- phase 1) must continue forward from the character
    actually on screen (`cell.seq[cell.step]`), not from the stale
    `cell.char`, which only updates when the bottom half lands.

    Unit-distance sequences never exercise this: with distance 1 there is
    only one step, so the stale-vs-displayed distinction never has a chance
    to diverge. This needs a STRIDED sequence (distance > MAX_STEPS) so the
    displayed character sits several drum positions ahead of the stale
    `cell.char`.
    """
    chars = "".join(chr(c) for c in range(0x41, 0x41 + 26))  # A..Z
    d = Drum(chars)
    m = FlapMachine(d, rows=1, cols=1, col_delay_ms=0, row_delay_ms=0, jitter_ms=0)

    m.retarget(("Z",), now_ms=0)
    # distance blank->Z is 26, well over MAX_STEPS (12): this is strided.
    assert len(m._cells[0].seq) < 26

    # Drive to the hinge: top of the third step ('I') has landed, its
    # bottom has not.
    for t in (0, 100, 200, 300, 400):
        m.tick(t)
    cell = m._cells[0]
    assert cell.phase == 1
    displayed = cell.seq[cell.step]
    displayed_idx = d.chars.index(displayed)

    m.retarget(("Z",), now_ms=400)   # mid-flight retarget during the hinge
    ops = m.tick(400)

    top_ops = [o for o in ops if o.half == "top"]
    assert top_ops, "expected a top op to fire immediately after retarget"
    new_idx = d.chars.index(top_ops[0].char)
    assert new_idx > displayed_idx, (
        f"retarget moved backward through the drum: displayed {displayed!r} "
        f"(idx {displayed_idx}) -> next top {top_ops[0].char!r} (idx {new_idx})"
    )


def test_grid_shape_mismatch_raises():
    m = machine(rows=1, cols=3)
    try:
        m.retarget(("AB",))
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError on wrong-width grid")


def test_off_charset_text_renders_as_tofu_instead_of_crashing():
    """Real seam: layout.build -> FlapMachine.retarget -> tick.

    A phrases file, a localised Kodi infolabel, or a now-playing title can
    contain a character the active drum doesn't carry (nothing upstream of
    the drum filters to its charset). That must paint tofu, never raise --
    a unit test against Drum alone would not exercise the module boundary
    where this actually broke.
    """
    board = layout.build(["Облачно"], (), rows=3, cols=10)
    drum = Drum(bundled_charset())
    m = FlapMachine(drum, rows=3, cols=10, col_delay_ms=0, row_delay_ms=0,
                    jitter_ms=0)

    m.retarget(board.grid, now_ms=0)   # must not raise KeyError
    ops = drain(m)

    assert any(op.char == TOFU for op in ops), (
        "expected an off-drum character to be painted as tofu"
    )
    assert m.settled
    assert TOFU in "".join(m.current_grid())


# --- folds(): the card in the air, for the falling-flap overlay ------------
#
# tick() says what a half has LANDED on; folds() says what is between those
# landings. A card falls in one half-step -- the top op releases it, the
# bottom op a half-step later is it arriving -- and then rests until the
# next flap. Every case below calls folds() only after tick() on the same
# clock, which is the documented contract.

def folding(m, t):
    """tick then fold at one instant, as the render loop does."""
    m.tick(t)
    return m.folds(t)


def test_nothing_is_in_flight_before_a_retarget():
    assert folding(machine(), 0) == []


def test_a_settled_board_has_no_card_in_flight():
    m = machine(cols=1, chars="12 ")
    m.retarget(("1",))
    drain(m)
    assert m.settled
    assert m.folds(10 ** 6) == []


def test_the_falling_card_carries_the_face_it_takes_away():
    """A card falls face-out: what leaves the top half is what the eye
    follows, and its back is the same character's bottom half -- which is
    exactly what the bottom op paints when it lands."""
    m = machine(cols=1, chars="AB ")
    m.retarget(("B",), now_ms=0)
    folding(m, 0)                       # first card: blank leaving
    assert [(f.cell, f.half, f.char) for f in folding(m, 200)] == [(0, "top", "A")]
    assert [f.char for f in folding(m, 250)] == ["A"]
    assert [o.char for o in m.tick(300) if o.half == "bottom"] == ["A"]


def test_the_card_foreshortens_then_closes_over_the_bottom():
    m = machine(cols=1, chars="12 ")
    m.retarget(("1",), now_ms=0)
    assert [(f.half, f.progress) for f in folding(m, 0)] == [("top", 0.0)]
    assert [(f.half, f.progress) for f in folding(m, 25)] == [("top", 0.5)]
    assert [(f.half, f.progress) for f in folding(m, 50)] == [("bottom", 0.0)]
    assert [(f.half, f.progress) for f in folding(m, 75)] == [("bottom", 0.5)]


def test_the_card_rests_between_flaps():
    """It lands a half-step after it is released and stays down until the
    next flap. Painting it through the rest half-step would stretch a
    200ms-apart pair of flaps into one continuous smear."""
    m = machine(cols=1, chars="AB ")
    m.retarget(("B",), now_ms=0)
    assert folding(m, 100) == []
    assert folding(m, 150) == []


def test_the_last_card_of_a_walk_still_falls():
    m = machine(cols=1, chars="AB ")
    m.retarget(("B",), now_ms=0)
    for t in range(0, 250, 25):
        folding(m, t)
    assert [(f.half, f.char) for f in folding(m, 250)] == [("bottom", "A")]


def test_a_cell_that_has_not_started_yet_has_nothing_in_flight():
    """Staggered columns: cell 0 is already falling while cell 2 waits. A
    cell must never paint a card before its own start."""
    m = FlapMachine(Drum("AB "), rows=1, cols=3,
                    col_delay_ms=60, row_delay_ms=0, jitter_ms=0)
    m.retarget(("AAA",), now_ms=0)
    assert {f.cell for f in folding(m, 0)} == {0}


def test_progress_never_leaves_the_zero_to_one_range():
    m = machine(cols=3, chars="AB C123")
    m.retarget(("A1B",), now_ms=0)
    for t in range(0, 3000, 17):
        for f in folding(m, t):
            assert 0.0 <= f.progress <= 1.0, f


def test_unchanged_cells_keep_nothing_in_flight():
    m = machine(cols=3, chars="AB ")
    m.retarget(("AAA",), now_ms=0)
    drain(m)
    m.retarget(("ABA",), now_ms=1000)
    for t in range(1000, 2000, 25):
        assert {f.cell for f in folding(m, t)} <= {1}
