#!/usr/bin/env bash
# Package the addon exactly as Kodi expects: a single top-level directory
# named for the addon id, containing only the runtime files -- no tests,
# no build tooling, no build-time-only font inputs.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

ID="screensaver.splitflap"

# `grep -o 'version="[0-9.]*"' addon.xml | head -1` matches the XML
# declaration's version="1.0" first, not the addon's -- parse addon.xml
# properly instead and read the <addon> element's version attribute.
VERSION="$(python3 -c '
import xml.etree.ElementTree as ET
print(ET.parse("addon.xml").getroot().attrib["version"])
')"

OUT="build/${ID}-${VERSION}.zip"

rm -rf build/staging
mkdir -p "build/staging/${ID}" build

# Runtime files only. Deliberately excluded: tests/, tools/, the .otf font
# (build-time input to glyphgen.py only), mutants/, .venv/, __pycache__,
# .zed/, setup.cfg, pyrightconfig.json, uv.lock, pyproject.toml.
cp addon.xml default.py "build/staging/${ID}/"
cp LICENSE "build/staging/${ID}/" 2>/dev/null || true
for asset in icon.png fanart.jpg; do
  if [ -f "$asset" ]; then
    cp "$asset" "build/staging/${ID}/"
  else
    echo "warning: ${asset} not found -- shipping without it (addon.xml references it)" >&2
  fi
done
cp -r resources "build/staging/${ID}/"

# The rendered glyph PNGs are derived from Nimbus Sans (AGPLv3 with font
# exception); its licence must travel with them even though the .otf input
# itself does not ship.
mkdir -p "build/staging/${ID}/assets/fonts"
cp assets/fonts/LICENSE-nimbus.txt assets/fonts/COPYING-nimbus.txt \
   assets/fonts/README.md "build/staging/${ID}/assets/fonts/"

find "build/staging/${ID}" -name '__pycache__' -type d -exec rm -rf {} +
find "build/staging/${ID}" -name '*.pyc' -delete

( cd build/staging && zip -qr "../../${OUT}" "${ID}" )
echo "wrote ${OUT}"
