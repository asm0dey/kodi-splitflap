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
