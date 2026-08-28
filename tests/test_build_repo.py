"""The served repository is a static directory tree, so the only thing a
Kodi HTTP source can navigate it by is the anchors on each directory page.
GitHub Pages generates none, which is what these listings are for.
"""
from tools.build_repo import write_listing


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
