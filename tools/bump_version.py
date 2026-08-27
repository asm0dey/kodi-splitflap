"""Increment the add-on's patch version in addon.xml.

Kodi refuses an install-from-zip whose version is not newer than the one
already installed, so every test build during development needs a fresh
patch number. Rewrites the attribute in place rather than reserialising the
document, so comments, formatting and attribute order survive untouched.
"""
import argparse
import pathlib
import re
import sys

ADDON_XML = pathlib.Path(__file__).resolve().parent.parent / "addon.xml"
# Anchored to the <addon> element: the XML declaration also carries a
# version attribute, and matching that one is a classic way to bump the
# wrong number.
PATTERN = re.compile(
    r'(<addon\s+id="[^"]+"[^>]*?version=")(\d+)\.(\d+)\.(\d+)(")', re.DOTALL
)


def bump(text: str, part: str) -> tuple[str, str]:
    match = PATTERN.search(text)
    if not match:
        raise SystemExit("no <addon> version attribute found in addon.xml")
    major, minor, patch = (int(match.group(i)) for i in (2, 3, 4))
    if part == "major":
        major, minor, patch = major + 1, 0, 0
    elif part == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    new = f"{major}.{minor}.{patch}"
    rewritten = (
        text[: match.start()]
        + match.group(1) + new + match.group(5)
        + text[match.end():]
    )
    return rewritten, new


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", nargs="?", default="patch",
                        choices=("major", "minor", "patch"))
    args = parser.parse_args()
    text = ADDON_XML.read_text(encoding="utf-8")
    updated, version = bump(text, args.part)
    ADDON_XML.write_text(updated, encoding="utf-8")
    print(version)


if __name__ == "__main__":
    sys.exit(main())
