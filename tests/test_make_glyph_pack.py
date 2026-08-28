import zipfile

import pytest

from tools.make_glyph_pack import build_pack, charset_for

PIL = pytest.importorskip("PIL")
FONT = "assets/fonts/NimbusSans-Regular.otf"


def test_named_charsets_resolve():
    assert "A" in charset_for(["ascii"])
    assert "А" in charset_for(["cyrillic"])
    assert "Α" in charset_for(["greek"])


def test_unknown_charset_name_raises():
    with pytest.raises(ValueError):
        charset_for(["klingon"])


def test_pack_zip_contains_addon_xml_and_glyphs(tmp_path):
    out = str(tmp_path / "pack.zip")
    build_pack(FONT, "AB", "resource.images.splitflap.test", "Test Pack",
               out, 40, 36)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert "resource.images.splitflap.test/addon.xml" in names
    assert "resource.images.splitflap.test/t_0041.png" in names
    assert "resource.images.splitflap.test/pack.json" in names


def test_addon_xml_declares_the_resource_images_type(tmp_path):
    out = str(tmp_path / "pack.zip")
    build_pack(FONT, "A", "resource.images.splitflap.test", "Test Pack",
               out, 40, 36)
    with zipfile.ZipFile(out) as zf:
        xml = zf.read("resource.images.splitflap.test/addon.xml").decode("utf-8")
    assert "kodi.resource.images" in xml


def test_addon_xml_declares_kodi_resource_dependency(tmp_path):
    """A resource.images addon depends on kodi.resource, not a GUI API.

    Parses the manifest instead of substring-matching so a malformed
    <requires> block (missing element, wrong attribute name) fails the
    test rather than slipping through on a coincidental text match.
    """
    import xml.etree.ElementTree as ET

    out = str(tmp_path / "pack.zip")
    build_pack(FONT, "A", "resource.images.splitflap.test", "Test Pack",
               out, 40, 36)
    with zipfile.ZipFile(out) as zf:
        xml_bytes = zf.read("resource.images.splitflap.test/addon.xml")
    root = ET.fromstring(xml_bytes)
    imported = [imp.get("addon") for imp in root.findall("./requires/import")]
    assert "kodi.resource" in imported
    assert "xbmc.gui" not in imported


def test_pack_json_records_metrics(tmp_path):
    import json
    out = str(tmp_path / "pack.zip")
    build_pack(FONT, "A", "resource.images.splitflap.test", "Test Pack",
               out, 40, 36)
    with zipfile.ZipFile(out) as zf:
        meta = json.loads(
            zf.read("resource.images.splitflap.test/pack.json").decode("utf-8"))
    assert meta["half_w"] == 40
    assert meta["half_h"] == 36
    assert "NimbusSans" in meta["font"]


def test_warns_when_the_letterset_omits_ascii(tmp_path, capsys):
    out = str(tmp_path / "pack.zip")
    build_pack(FONT, "АБ", "resource.images.splitflap.ru", "RU",
               out, 40, 36)
    assert "ascii" in capsys.readouterr().out.lower()


def test_addon_id_must_be_a_plain_kodi_id():
    """`--id` is joined onto a temp root three times; traversal must fail."""
    from tools.make_glyph_pack import validate_addon_id

    assert validate_addon_id("resource.images.splitflap.nimbus-ru")
    for bad in ("../../etc", "a/b", "a\\b", ".hidden", "UPPER", "", "x..y"):
        with pytest.raises(ValueError):
            validate_addon_id(bad)


def test_build_pack_refuses_a_traversing_id(tmp_path):
    from tools.make_glyph_pack import build_pack

    with pytest.raises(ValueError):
        build_pack(font=FONT, chars="A", addon_id="../escape", name="x",
                   out_zip=str(tmp_path / "p.zip"), half_w=8, half_h=8)
    assert not (tmp_path / "p.zip").exists()


def test_chars_from_must_be_a_regular_file(tmp_path):
    from tools.make_glyph_pack import read_chars_file

    good = tmp_path / "chars.txt"
    good.write_text("AB", encoding="utf-8")
    assert read_chars_file(str(good)) == "AB"

    with pytest.raises(ValueError):
        read_chars_file(str(tmp_path))            # a directory
    with pytest.raises(ValueError):
        read_chars_file(str(tmp_path / "nope"))   # missing
