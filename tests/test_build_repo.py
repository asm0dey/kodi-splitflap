"""The served repository is a static directory tree, so the only thing a
Kodi HTTP source can navigate it by is the anchors on each directory page.
GitHub Pages generates none, which is what these listings are for.
"""
import hashlib
import zipfile

import pytest

from tools.build_repo import fetch_external, write_listing


def links(html):
    import re
    return re.findall(r'href="([^"]+)"', html)


def test_every_file_in_the_directory_gets_an_anchor(tmp_path):
    (tmp_path / "addons.xml").write_text("<addons/>")
    (tmp_path / "addons.xml.md5").write_text("d41d8")
    write_listing(tmp_path)
    assert set(links((tmp_path / "index.html").read_text())) == {
        "addons.xml", "addons.xml.md5"}


def test_subdirectories_are_linked_with_a_trailing_slash(tmp_path):
    """Kodi resolves a listing's links against the directory URL; without the
    slash it requests the add-on directory as a file and gets a 404."""
    (tmp_path / "screensaver.splitflap").mkdir()
    write_listing(tmp_path)
    assert links((tmp_path / "index.html").read_text()) == [
        "screensaver.splitflap/"]


def test_the_listing_does_not_link_to_itself(tmp_path):
    (tmp_path / "icon.png").write_bytes(b"")
    write_listing(tmp_path)
    write_listing(tmp_path)          # a rebuild must not accumulate entries
    assert links((tmp_path / "index.html").read_text()) == ["icon.png"]


def _release_zip(tmp_path, addon_id, xml_id=None):
    path = tmp_path / f"{addon_id}.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{addon_id}/addon.xml",
                         f'<addon id="{xml_id or addon_id}" version="0.1.0"/>')
        archive.writestr(f"{addon_id}/icon.png", b"png")
    return {"id": addon_id, "zip_url": path.as_uri(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def test_external_zip_lands_in_the_datadir_unchanged(tmp_path):
    entry = _release_zip(tmp_path, "script.floppy")
    docs = tmp_path / "repo"
    manifest = fetch_external(entry, docs)
    assert manifest.get("version") == "0.1.0"
    out = docs / "script.floppy" / "script.floppy-0.1.0.zip"
    assert out.read_bytes() == (tmp_path / "script.floppy.zip").read_bytes()
    assert (docs / "script.floppy" / "icon.png").read_bytes() == b"png"


def test_external_zip_with_the_wrong_checksum_fails_the_build(tmp_path):
    entry = _release_zip(tmp_path, "script.floppy") | {"sha256": "0" * 64}
    with pytest.raises(SystemExit, match="sha256"):
        fetch_external(entry, tmp_path / "repo")
    assert not (tmp_path / "repo").exists()


def test_external_zip_for_a_different_addon_fails_the_build(tmp_path):
    entry = _release_zip(tmp_path, "script.floppy", xml_id="script.other")
    with pytest.raises(SystemExit, match=r"script\.other"):
        fetch_external(entry, tmp_path / "repo")
