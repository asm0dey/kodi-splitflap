def test_package_importable():
    import resources.lib  # noqa: F401


def test_no_runtime_dependencies_are_declared():
    """The add-on ships as a plain Kodi zip with no pip at install time.

    Pillow is a build-time tool for rasterising glyphs and pytest is a test
    tool; neither may leak into the runtime dependency list. Package
    managers add entries here silently, so this is checked rather than
    trusted.
    """
    import pathlib
    import re
    text = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
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
    import pathlib
    import tomllib

    import pytest

    lock_path = pathlib.Path("uv.lock")
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
