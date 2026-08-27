import itertools

import pytest

from resources.lib.charset import BLANK
from resources.lib.drum import MAX_STEPS, Drum


def test_blank_is_first_then_codepoints_ascending():
    d = Drum("CAB ")
    assert d.chars == (BLANK, "A", "B", "C")


def test_adjacent_characters_are_one_step():
    """'1' -> '2' is the common clock case and must be a single flap."""
    d = Drum("0123456789")
    assert d.distance("1", "2") == 1
    assert d.sequence("1", "2") == ("2",)


def test_letters_are_also_one_step_apart():
    d = Drum("ABCDEFGHIJ ")
    assert d.sequence("A", "B") == ("B",)


def test_motion_is_forward_only_and_wraps():
    """Distance is forward-only, so a lower target wraps past the end.

    On this toy drum ' 0123456789' the digit 9 sits last, so reaching 0
    costs two steps -- past blank, then onto 0. The point is that it wraps
    rather than stepping back one place.
    """
    d = Drum("0123456789")
    assert d.chars[-1] == "9"
    assert d.distance("9", "0") == 2
    assert d.distance("0", "9") == 9


def test_wrapping_a_long_drum_costs_nearly_a_revolution():
    """On a realistically sized drum, 9 -> 0 really does spin the long way."""
    d = Drum("".join(chr(c) for c in range(0x30, 0x30 + 100)))
    assert d.distance("9", "0") == len(d.chars) - 9


def test_wrap_is_clamped_to_max_steps():
    d = Drum("".join(chr(c) for c in range(0x41, 0x41 + 140)))
    seq = d.sequence("Z", "A")
    assert len(seq) <= MAX_STEPS


def test_sequence_always_lands_exactly_on_target():
    d = Drum("".join(chr(c) for c in range(0x41, 0x41 + 60)))
    for target in d.chars:
        if target == "A":
            continue          # zero distance yields no flaps at all
        assert d.sequence("A", target)[-1] == target


def test_full_drum_walk_at_the_step_cap():
    """Twelve flaps across a thirteen-character drum.

    distance 12 with max_steps 12 gives stride 1, so every character is
    shown and nothing is sampled out -- the boundary case where the cap is
    met exactly rather than exceeded.
    """
    d = Drum("ABCDEFGHIJKL ")
    assert len(d.chars) == 13
    seq = d.sequence(BLANK, "L")
    assert len(seq) == MAX_STEPS == 12
    assert seq == tuple("ABCDEFGHIJKL")


def test_one_past_the_cap_starts_sampling():
    """distance 13 over 12 flaps: stride 2, so the walk skips characters."""
    d = Drum("ABCDEFGHIJKLM ")
    assert len(d.chars) == 14
    seq = d.sequence(BLANK, "M")
    assert len(seq) <= MAX_STEPS
    assert seq[-1] == "M"
    assert len(seq) < 13          # genuinely sampled, not contiguous


def test_sequence_is_empty_for_same_character():
    d = Drum("ABC ")
    assert d.sequence("B", "B") == ()


def test_sequence_moves_forward_through_the_drum():
    d = Drum("".join(chr(c) for c in range(0x41, 0x41 + 40)))
    seq = d.sequence("A", d.chars[-1])
    idx = [d.chars.index(c) for c in seq]
    assert idx == sorted(idx)


def test_every_step_is_a_real_drum_character():
    d = Drum("".join(chr(c) for c in range(0x41, 0x41 + 100)))
    for ch in d.sequence("B", "A"):
        assert ch in d.chars


def test_no_step_repeats_the_previous_one():
    """A flap that shows the same character twice is a dropped frame."""
    d = Drum("".join(chr(c) for c in range(0x41, 0x41 + 100)))
    seq = d.sequence("B", "A")
    assert all(a != b for a, b in itertools.pairwise(seq))


def test_unknown_character_is_treated_as_blank():
    """After a mid-session pack change the displayed char may be gone."""
    d = Drum("AB ")
    assert d.distance("Ж", "A") == d.distance(BLANK, "A")


def test_unknown_target_raises():
    d = Drum("AB ")
    with pytest.raises(KeyError):
        d.sequence("A", "Ж")


def test_short_distances_are_contiguous_not_sampled():
    """Under the cap, every intermediate character is shown in order."""
    d = Drum("ABCDEFGHIJ ")
    assert d.sequence("A", "E") == ("B", "C", "D", "E")


def test_max_steps_zero_raises_instead_of_dividing_by_zero():
    """max_steps=0 must be rejected, not fall through to a ZeroDivisionError."""
    d = Drum("ABC ")
    with pytest.raises(ValueError):
        d.sequence("A", "C", max_steps=0)


def test_max_steps_negative_raises():
    d = Drum("ABC ")
    with pytest.raises(ValueError):
        d.sequence("A", "C", max_steps=-1)
