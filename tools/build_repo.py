"""Build the Kodi repository that GitHub Pages serves.

Kodi's add-on browser wants three things at a URL: an `addons.xml` listing
every add-on it offers, an `addons.xml.md5` beside it, and each add-on's zip
at `<datadir>/<addon.id>/<addon.id>-<version>.zip`. Users install the
repository add-on once and then get everything else -- and updates -- through
the normal add-on browser, with no zips and no typing a URL on a remote.

Discovers add-ons by looking for a directory whose name matches the `id` in
the `addon.xml` it contains, so adding a fourth add-on to the repo needs no
change here.

Add-ons that live in their own repositories are listed in
`external-addons.json` by release zip URL and sha256. Their zips are pulled
in as published, never rebuilt, so what Kodi installs is byte-for-byte the
release the other repo tagged.
"""

import hashlib
import io
import json
import pathlib
import shutil
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = REPO_ROOT / "docs" / "repo"
EXTERNAL = REPO_ROOT / "external-addons.json"

# Never ship these, whichever add-on they turn up in. The .otf is a build-time
# input to the glyph renderer; its licence files DO ship, because the rendered
# PNGs are derived from it.
EXCLUDE_NAMES = {"__pycache__", ".pytest_cache", "mutants", ".git"}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".otf", ".ttf"}


def find_addons() -> list[tuple[pathlib.Path, ET.Element]]:
    """Every directory that is an add-on, i.e. its name is its addon.xml id."""
    found = []
    for path in sorted(REPO_ROOT.iterdir()):
        manifest = path / "addon.xml"
        if not path.is_dir() or not manifest.is_file():
            continue
        root = ET.parse(manifest).getroot()
        if root.get("id") != path.name:
            print(f"skipping {path.name}: addon.xml id is {root.get('id')!r}")
            continue
        found.append((path, root))
    return found


def _wanted(path: pathlib.Path) -> bool:
    if any(part in EXCLUDE_NAMES for part in path.parts):
        return False
    return path.suffix.lower() not in EXCLUDE_SUFFIXES


def package(source: pathlib.Path, version: str) -> pathlib.Path:
    """Zip one add-on into the layout Kodi's datadir expects."""
    out_dir = DOCS / source.name
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{source.name}-{version}.zip"

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in sorted(source.rglob("*")):
            if not item.is_file() or not _wanted(item.relative_to(source)):
                continue
            # Kodi requires a single top-level directory named for the addon
            # id; a flat archive fails to install with no useful message.
            archive.write(item, pathlib.Path(source.name) / item.relative_to(source))
    return out


def fetch_external(entry: dict, docs: pathlib.Path) -> ET.Element:
    """Download one external add-on's release zip into the datadir.

    Refuses the zip unless its sha256 is the pinned one and the addon.xml
    inside names the expected id -- a moved tag or a wrong URL must fail the
    build, not ship something else under this repository's name.
    """
    addon_id = entry["id"]
    with urllib.request.urlopen(entry["zip_url"], timeout=60) as response:
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != entry["sha256"]:
        raise SystemExit(f"{addon_id}: sha256 {digest} != pinned {entry['sha256']}")

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        root = ET.fromstring(archive.read(f"{addon_id}/addon.xml"))
        if root.get("id") != addon_id:
            raise SystemExit(f"{addon_id}: zip's addon.xml id is {root.get('id')!r}")
        out_dir = docs / addon_id
        out_dir.mkdir(parents=True, exist_ok=True)
        version = root.get("version", "0.0.0")
        (out_dir / f"{addon_id}-{version}.zip").write_bytes(data)
        # Same reason as for local add-ons: Kodi reads these from the datadir.
        for asset in ("icon.png", "fanart.jpg"):
            if f"{addon_id}/{asset}" in archive.namelist():
                (out_dir / asset).write_bytes(archive.read(f"{addon_id}/{asset}"))
    return root


def write_listing(directory: pathlib.Path) -> None:
    """Write the directory page a Kodi HTTP source browses this tree by.

    GitHub Pages serves no directory listing -- a bare directory URL is a
    404 -- and Kodi's HTTP VFS navigates by parsing anchors out of the page
    at that URL. Without these files the repository is still installable by
    exact URL (which is all the repository ADD-ON ever requests), but
    "Add source" cannot list it, so the documented file-manager route
    dead-ends. Deliberately plain markup: it is parsed by a VFS, not read.
    """
    entries = sorted(p for p in directory.iterdir() if p.name != "index.html")
    rows = "\n".join(
        f'<li><a href="{p.name}/">{p.name}/</a></li>' if p.is_dir()
        else f'<li><a href="{p.name}">{p.name}</a></li>'
        for p in entries
    )
    (directory / "index.html").write_text(
        "<!DOCTYPE html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{directory.name}</title></head>\n"
        f"<body><h1>{directory.name}</h1>\n<ul>\n{rows}\n</ul></body></html>\n",
        encoding="utf-8",
    )


def main() -> int:
    addons = find_addons()
    if not addons:
        print("no add-ons found", file=sys.stderr)
        return 1

    if DOCS.exists():
        shutil.rmtree(DOCS)
    DOCS.mkdir(parents=True)

    index = ET.Element("addons")
    for source, manifest in addons:
        version = manifest.get("version", "0.0.0")
        archive = package(source, version)
        index.append(manifest)
        size = archive.stat().st_size
        print(f"{source.name:38} {version:8} {size:>9,} bytes")

        # Kodi shows the icon and fanart from the datadir, not from inside the
        # zip, so they are copied out alongside it.
        for asset in ("icon.png", "fanart.jpg"):
            if (source / asset).is_file():
                shutil.copy2(source / asset, DOCS / source.name / asset)

    external = json.loads(EXTERNAL.read_text()) if EXTERNAL.is_file() else []
    for entry in external:
        manifest = fetch_external(entry, DOCS)
        index.append(manifest)
        print(f"{entry['id']:38} {manifest.get('version'):8} (external)")
    ids = [m.get("id", "") for m in index]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"duplicate add-on ids: {ids}")

    xml = ET.tostring(index, encoding="utf-8", xml_declaration=True)
    (DOCS / "addons.xml").write_bytes(xml)
    # md5 because the Kodi repository FORMAT requires an addons.xml.md5
    # beside addons.xml -- it is a transport checksum Kodi itself verifies,
    # not a security control, and no other digest is accepted. The explicit
    # usedforsecurity=False says so to the interpreter and to scanners.
    digest = hashlib.md5(xml, usedforsecurity=False).hexdigest()
    (DOCS / "addons.xml.md5").write_text(digest, encoding="utf-8")
    print(f"\naddons.xml  {len(ids)} add-ons, md5 {digest}")

    # Last, so every zip, icon and checksum above is already in place to be
    # listed -- and the add-on directories before the root, which links them.
    for addon_id in ids:
        write_listing(DOCS / addon_id)
    write_listing(DOCS)
    print(f"index.html  {len(ids) + 1} directory listings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
