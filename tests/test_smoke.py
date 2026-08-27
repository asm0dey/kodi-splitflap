

def _repo():
    """The repo root, anchored to this file rather than the cwd."""
    import pathlib
    return pathlib.Path(__file__).resolve().parent.parent


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
    text = (_repo() / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^dependencies\s*=\s*(\[[^\]]*\])", text, re.MULTILINE)
    assert block, "dependencies key missing from pyproject.toml"
    assert block.group(1).strip() == "[]", (
        f"runtime dependencies must stay empty, found {block.group(1)}"
    )


def test_lockfile_also_declares_no_runtime_dependencies():
    """pyproject.toml alone isn't the whole truth: `uv sync --locked` installs
    from uv.lock, not from pyproject.toml's dependencies list. A `uv`
    invocation can silently promote packages into the lock's runtime
    `dependencies` for this project's own entry even while pyproject.toml
    stays clean (that happened once already -- pyproject.toml said `[]` but
    uv.lock still listed pillow and pytest as runtime deps, and `uv lock
    --check` failed). Regexing pyproject.toml text cannot catch that; this
    test parses the actual lock.
    """
    import tomllib

    import pytest

    lock_path = _repo() / "uv.lock"
    if not lock_path.exists():
        pytest.skip("uv.lock not present in this checkout")

    data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    packages = [p for p in data.get("package", [])
                if p.get("name") == "screensaver-splitflap"]
    assert packages, "screensaver-splitflap entry missing from uv.lock"
    pkg = packages[0]
    assert pkg.get("dependencies", []) == [], (
        "uv.lock declares runtime dependencies for "
        f"screensaver-splitflap: {pkg.get('dependencies')!r}"
    )


def _settings_root():
    import xml.etree.ElementTree as ET
    return ET.parse(_repo() / "resources" / "settings.xml").getroot()


def test_source_specific_settings_are_hidden_for_other_sources():
    """The settings screen must reflect the chosen source.

    Live-info checkboxes have no meaning while Phrases is selected, and a
    phrase file has none under Live info. Each conditional setting declares
    a visible-dependency on `source`.
    """
    expected = {
        "source_addon_id": "contributor",
        "info_time": "liveinfo",
        "info_date": "liveinfo",
        "info_weather": "liveinfo",
        "info_nowplaying": "liveinfo",
        "info_combine": "liveinfo",
        "phrases_file": "phrases",
        "phrases_url": "phrases",
    }
    found = {}
    for setting in _settings_root().iter("setting"):
        dep = setting.find("./dependencies/dependency[@type='visible']")
        if dep is not None and dep.get("setting") == "source":
            found[setting.get("id")] = (dep.text or "").strip()
    assert found == expected


def test_unconditional_settings_have_no_source_dependency():
    """Board geometry, timing, colours and the glyph pack apply to every source."""
    always = {"rows", "hold_seconds", "max_steps", "letter_colour",
              "accent_colour", "source", "glyph_pack"}
    for setting in _settings_root().iter("setting"):
        if setting.get("id") in always:
            assert setting.find("./dependencies") is None, setting.get("id")


def test_version_bump_targets_the_addon_element_not_the_xml_declaration():
    """The XML declaration also has a version attribute.

    Matching that one instead is a classic way to bump the wrong number --
    the plan's original packaging script did exactly that.
    """
    from tools.bump_version import bump

    text = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<addon id="screensaver.splitflap" name="X"'
        ' version="0.1.1" provider-name="p">\n'
        "</addon>\n"
    )
    updated, version = bump(text, "patch")
    assert version == "0.1.2"
    assert 'version="1.0" encoding' in updated      # declaration untouched
    assert 'name="X" version="0.1.2"' in updated


def test_version_bump_parts():
    from tools.bump_version import bump

    text = '<addon id="a" version="1.2.3">'
    assert bump(text, "patch")[1] == "1.2.4"
    assert bump(text, "minor")[1] == "1.3.0"
    assert bump(text, "major")[1] == "2.0.0"


def test_string_settings_with_an_empty_default_allow_empty():
    """Kodi refuses to construct a string setting with an empty default.

    Without <allowempty>, CSettingString logs "error reading the default
    value of ..." and the setting never appears in the UI at all -- which
    is how four settings silently went missing rather than misbehaving.
    """
    for setting in _settings_root().iter("setting"):
        if setting.get("type") not in ("string", "path"):
            continue
        default = setting.find("default")
        empty = default is not None and not (default.text or "").strip()
        if not empty:
            continue
        allow = setting.find("./constraints/allowempty")
        assert allow is not None and allow.text == "true", (
            f"{setting.get('id')} has an empty default but no allowempty; "
            "Kodi will drop the setting"
        )
