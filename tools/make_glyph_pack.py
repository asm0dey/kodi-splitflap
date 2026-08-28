"""Build an installable glyph pack from a font and a letterset.

A pack is a standard kodi.resource.images addon, so it installs from a zip
or from a repository -- no filesystem access needed on Fire TV or webOS,
and no custom loader on our side. The screensaver finds a pack's glyphs
through a `resource://<addon.id>/...` path that Kodi resolves.

A pack carries a font AND a letterset, so it serves two purposes: adding
scripts the bundle doesn't cover, and restyling the whole board in a
different typeface. A pack whose letterset includes ASCII overrides the
bundle completely and keeps the board typographically consistent, which is
why this builder warns when ASCII is left out.
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from collections.abc import Iterable

# The add-on directory is an import root, not a package -- its name has dots
# in it. Putting it on the path is what lets these tools import
# `resources.lib.*` exactly as the add-on does at runtime.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "screensaver.splitflap"))

from resources.lib.charset import bundled_charset
from resources.lib.glyphgen import render_glyphs

ADDON_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="{id}" name="{name}" version="1.0.0" provider-name="splitflap">
  <requires>
    <import addon="kodi.resource" version="1.0.0"/>
  </requires>
  <extension point="kodi.resource.images"/>
  <extension point="xbmc.addon.metadata">
    <summary lang="en_GB">Glyph pack for Split-Flap Board</summary>
    <description lang="en_GB">{name}</description>
    <platform>all</platform>
  </extension>
</addon>
"""


def _cyrillic_upper() -> str:
    # Cyrillic capital yo (U+0401) plus the uppercase run a-ya
    # (U+0410-U+042F) -- the Russian uppercase alphabet.
    return chr(0x401) + "".join(chr(cp) for cp in range(0x410, 0x430))


def _greek_upper() -> str:
    # Uppercase Greek alpha-omega (U+0391-U+03A9), skipping the unassigned
    # codepoint U+03A2.
    return "".join(chr(cp) for cp in range(0x391, 0x3AA) if chr(cp).isalpha())


def _hebrew_letters() -> str:
    # Hebrew aleph-tav (U+05D0-U+05EA). Hebrew has no case, so this is the
    # whole alphabet -- there is no separate uppercase subset to pick.
    return "".join(chr(cp) for cp in range(0x5D0, 0x5EB))


_NAMED_CHARSETS = {
    "ascii": lambda: "".join(bundled_charset()),
    "cyrillic": _cyrillic_upper,
    "greek": _greek_upper,
    "hebrew": _hebrew_letters,
}


def charset_for(names: Iterable[str]) -> str:
    """Resolve named charsets (ascii, cyrillic, greek, hebrew) to characters.

    Every named set is already uppercase-only (or, for Hebrew, caseless) at
    the source, so the result never needs a separate uppercase pass.
    """
    chars: list[str] = []
    seen: set[str] = set()
    for raw_name in names:
        key = raw_name.strip().lower()
        if key not in _NAMED_CHARSETS:
            known = ", ".join(sorted(_NAMED_CHARSETS))
            raise ValueError(f"unknown charset {raw_name!r}, known: {known}")
        for ch in _NAMED_CHARSETS[key]():
            if ch not in seen:
                seen.add(ch)
                chars.append(ch)
    return "".join(chars)


# Kodi add-on ids are dotted lowercase identifiers. Anchored, and with no
# separator or dot-dot admitted, so the id can never climb out of the
# staging directory it names -- every path in build_pack() is built by
# joining this value onto a temp root.
_ADDON_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(\.[a-z0-9][a-z0-9_-]*)*$")


def validate_addon_id(addon_id: str) -> str:
    """Reject anything that is not a plain Kodi add-on id.

    `--id` is joined onto a temp directory three times over, so a value
    like `../../x` would write outside it. Kodi would refuse such an id at
    install time anyway; failing here turns a silent traversal into an
    argument error.
    """
    if not _ADDON_ID_RE.match(addon_id):
        raise ValueError(
            f"invalid add-on id {addon_id!r}: expected a dotted lowercase "
            "identifier such as 'resource.images.splitflap.myfont'"
        )
    return addon_id


def read_chars_file(path: str, root: str | None = None) -> str:
    """Read a `--chars-from` file from under `root` (default: the cwd).

    Two restrictions, both deliberate:

    * The resolved path must sit under `root`. This builder is run from the
      repo root by convention (as `tools/build_bundled.py` is), so a
      letterset lives in the tree beside the font it will be rendered
      with. Containing the read keeps an unchecked CLI argument -- or an
      agent's faulty one -- from reaching an arbitrary file.
    * It must be a regular file. A directory or device node here is a
      mistake rather than an input, and a fifo would hang the build
      instead of failing it.

    Symlinks resolve before the check, so a link pointing out of the tree
    is rejected on its target rather than admitted on its name.
    """
    base = os.path.realpath(root if root is not None else os.getcwd())
    resolved = os.path.realpath(path)
    if os.path.commonpath([base, resolved]) != base:
        raise ValueError(
            f"--chars-from must name a file under {base!r}, got {path!r}; "
            "copy the letterset into the tree and point at it there"
        )
    if not os.path.isfile(resolved):
        raise ValueError(f"--chars-from must be a readable file: {path!r}")
    with open(resolved, encoding="utf-8") as handle:
        return handle.read()


def build_pack(
    font: str,
    chars: str,
    addon_id: str,
    name: str,
    out_zip: str,
    half_w: int,
    half_h: int,
) -> str:
    """Render `chars` in `font` into a kodi.resource.images addon zip.

    The zip's single top-level directory is `addon_id` -- Kodi's
    install-from-zip requires that shape, and a flat zip silently fails to
    install.
    """
    validate_addon_id(addon_id)

    ascii_set = set(charset_for(["ascii"]))
    if not ascii_set.issubset(set(chars)):
        print(
            "warning: this pack's letterset omits ascii -- the board will "
            "mix this pack's typeface with the bundled one for any "
            "character this pack doesn't cover. Add --charset ascii for a "
            "typographically consistent board."
        )

    staging = tempfile.mkdtemp()
    try:
        root = os.path.join(staging, addon_id)
        os.makedirs(root)
        render_glyphs(chars, font, root, half_w, half_h)

        with open(os.path.join(root, "addon.xml"), "w", encoding="utf-8") as handle:
            handle.write(ADDON_XML.format(id=addon_id, name=name))

        metrics = {
            "font": os.path.basename(font),
            "chars": chars,
            "half_w": half_w,
            "half_h": half_h,
        }
        with open(os.path.join(root, "pack.json"), "w", encoding="utf-8") as handle:
            json.dump(metrics, handle, indent=2)

        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for folder, _dirs, files in os.walk(root):
                for filename in files:
                    full = os.path.join(folder, filename)
                    zf.write(full, os.path.relpath(full, staging))
        return out_zip
    finally:
        shutil.rmtree(staging)


def _resolve_chars(args: argparse.Namespace) -> str:
    parts: list[str] = []
    if args.charset:
        parts.append(charset_for(args.charset.split(",")))
    if args.chars:
        parts.append(args.chars)
    if args.chars_from:
        parts.append(read_chars_file(args.chars_from))

    # str.upper() can expand one character into several (e.g. "SS" for
    # "ß"); upper-casing the combined text before splitting into
    # characters means every expanded character reaches the dedup loop
    # below like any other character, with no separate case to handle.
    combined = "".join(parts).upper()
    seen: set[str] = set()
    chars: list[str] = []
    for ch in combined:
        # Drop the line-ending/tab artifacts a --chars-from file read can
        # introduce. Don't use a generic "is whitespace" test here: that
        # would also drop meaningful glyphs like the regular space or
        # U+00A0 (non-breaking space), both of which are legitimately part
        # of the bundled ascii charset.
        if ch in "\r\n\t":
            continue
        if ch not in seen:
            seen.add(ch)
            chars.append(ch)
    return "".join(chars)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", required=True)
    parser.add_argument(
        "--charset", default="",
        help="comma-separated named sets: ascii,cyrillic,greek,hebrew",
    )
    parser.add_argument("--chars", default="", help="literal characters to add")
    parser.add_argument(
        "--chars-from", default="", help="path to a file of characters to add"
    )
    parser.add_argument("--id", required=True, dest="addon_id")
    parser.add_argument("--name", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--half-w", type=int, default=156)
    parser.add_argument("--half-h", type=int, default=142)
    args = parser.parse_args()

    chars = _resolve_chars(args)
    if not chars:
        parser.error(
            "no characters selected -- pass --charset, --chars, or --chars-from"
        )

    build_pack(
        args.font, chars, args.addon_id, args.name, args.out,
        args.half_w, args.half_h,
    )
    print(f"wrote {args.out} ({len(chars)} characters)")


if __name__ == "__main__":
    main()
