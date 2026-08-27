def test_package_importable():
    import resources.lib  # noqa: F401


def test_no_runtime_dependencies_are_declared():
    """The add-on ships as a plain Kodi zip with no pip at install time.

    Pillow is a build-time tool for rasterising glyphs and pytest is a test
    tool; neither may leak into the runtime dependency list. Package
    managers add entries here silently, so this is checked rather than
    trusted.
    """
    import re
    import pathlib
    text = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^dependencies\s*=\s*(\[[^\]]*\])", text, re.M)
    assert block, "dependencies key missing from pyproject.toml"
    assert block.group(1).strip() == "[]", (
        "runtime dependencies must stay empty, found %s" % block.group(1)
    )
