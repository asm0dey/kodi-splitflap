

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


def _addon():
    """The add-on directory. Everything shipped lives under it."""
    return _repo() / "screensaver.splitflap"


def _settings_root():
    import xml.etree.ElementTree as ET
    return ET.parse(_addon() / "resources" / "settings.xml").getroot()


def test_source_specific_settings_are_hidden_for_other_sources():
    """The settings screen must reflect the chosen source.

    Live-info checkboxes have no meaning while Phrases is selected, and a
    phrase file has none under Live info. Each conditional setting declares
    a visible-dependency on `source`.
    """
    expected = {
        "source_addon_id": "contributor",
        "configure_source": "contributor",
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
        cond = setting.find(
            "./dependencies/dependency[@type='visible']/condition"
        )
        if cond is not None and cond.get("setting") == "source":
            found[setting.get("id")] = (cond.text or "").strip()
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
        why = (f"{setting.get('id')} has an empty default but no "
               "allowempty; Kodi will drop the setting")
        assert allow is not None, why
        assert allow.text == "true", why


def test_lint_and_type_tools_are_pinned():
    """CI installs the pinned versions; a local checkout must match.

    ruff's rule set changes between releases, so an unpinned local install
    reports different findings than CI does -- which is how an E402 failure
    reached a pull request while the local gate said "All checks passed".
    """
    import re
    text = (_repo() / "pyproject.toml").read_text(encoding="utf-8")
    dev = re.search(r"^dev\s*=\s*\[([^\]]*)\]", text, re.MULTILINE)
    assert dev, "dev extra missing from pyproject.toml"
    for tool in ("ruff", "pytest", "pyright"):
        assert re.search(rf'"{tool}==\d', dev.group(1)), (
            f"{tool} must be pinned with == so local and CI agree"
        )


def test_readme_download_links_point_at_files_that_exist():
    """A dead download link is this README's most user-visible failure.

    The repository zip is linked by exact version, so bumping
    repository.splitflap without rebuilding docs/repo would leave the
    front-page install button pointing at nothing.
    """
    import re
    readme = (_repo() / "README.md").read_text(encoding="utf-8")
    base = "https://asm0dey.github.io/kodi-splitflap/repo/"
    served = _repo() / "docs" / "repo"
    missing = []
    for url in re.findall(rf"{re.escape(base)}([^)\s]+)", readme):
        target = served / url
        # a bare directory link is a listing, not a file
        if url.endswith("/"):
            if not target.is_dir():
                missing.append(url)
        elif not target.is_file():
            missing.append(url)
    assert not missing, f"README links to files not in docs/repo: {missing}"


def test_served_repository_zips_are_tracked_by_git():
    """Existing on disk is not enough -- Pages serves what git holds.

    .gitignore carries a blanket *.zip, which silently excluded every zip
    under docs/repo. The result was a repository whose addons.xml listed
    three add-ons and served none of them: metadata and icons resolved,
    downloads 404'd.
    """
    import subprocess
    served = _repo() / "docs" / "repo"
    zips = sorted(served.rglob("*.zip"))
    assert zips, "docs/repo has no zips; run tools/build_repo.py"
    ignored = subprocess.run(
        ["git", "check-ignore", *[str(z) for z in zips]],
        cwd=_repo(), capture_output=True, text=True,
    ).stdout.split()
    assert not ignored, (
        f"served zips are gitignored, so Pages cannot serve them: {ignored}"
    )


def test_landing_page_links_resolve():
    """Every relative link on the Pages index must point at a real file.

    The install links are version-stamped, so a release renames the zip they
    point at and the page keeps serving a 404 -- silently, because GitHub
    Pages has no directory listing to fall back on. This is the check that
    turns that into a build failure.
    """
    import re
    docs = _repo() / "docs"
    text = (docs / "index.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)]+)\)", text)
    relative = [x for x in links if not x.startswith(("http://", "https://", "#"))]
    assert relative, "no relative links found -- the regex stopped matching"
    missing = [x for x in relative if not (docs / x).exists()]
    assert not missing, f"landing page links to missing files: {missing}"


def test_landing_page_links_no_directories():
    """A link to a directory 404s on GitHub Pages -- there is no index."""
    import re
    docs = _repo() / "docs"
    text = (docs / "index.md").read_text(encoding="utf-8")
    dirs = [x for x in re.findall(r"\]\(([^)]+)\)", text)
            if not x.startswith(("http://", "https://", "#"))
            and (docs / x).is_dir()]
    assert not dirs, f"landing page links to directories, which 404: {dirs}"


def test_landing_page_offers_every_addon():
    """Each add-on in the repository index is reachable from the page."""
    import xml.etree.ElementTree as ET
    docs = _repo() / "docs"
    text = (docs / "index.md").read_text(encoding="utf-8")
    root = ET.parse(docs / "repo" / "addons.xml").getroot()
    ids = [a.get("id") for a in root.findall("addon")]
    assert all(ids), "an addon in addons.xml has no id"
    missing = [i for i in ids if i and i not in text]
    assert not missing, f"add-ons in the repo but absent from the page: {missing}"
