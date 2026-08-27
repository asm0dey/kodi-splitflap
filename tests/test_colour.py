from resources.lib.colour import FALLBACK_ARGB, to_argb


def test_plain_rrggbb_gets_opaque_alpha_prefixed():
    assert to_argb("E8E8E8") == "FFE8E8E8"


def test_hash_prefixed_rrggbb_is_accepted():
    assert to_argb("#2B5CE6") == "FF2B5CE6"


def test_lowercase_hex_is_upper_cased():
    assert to_argb("e8e8e8") == "FFE8E8E8"


def test_empty_string_is_invalid():
    assert to_argb("") is None


def test_short_value_is_invalid():
    assert to_argb("E8E8") is None


def test_long_value_is_invalid():
    assert to_argb("E8E8E8E8") is None


def test_non_hex_characters_are_invalid():
    assert to_argb("GGGGGG") is None


def test_doubled_hash_is_invalid():
    assert to_argb("##E8E8E8") is None


def test_surrounding_whitespace_is_invalid():
    assert to_argb(" E8E8E8") is None
    assert to_argb("E8E8E8 ") is None


def test_fallback_is_a_valid_opaque_argb_string():
    assert FALLBACK_ARGB == "FFFFFFFF"
    assert len(FALLBACK_ARGB) == 8
