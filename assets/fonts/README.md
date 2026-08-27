# Bundled font: Nimbus Sans

- **Font:** Nimbus Sans, Regular weight.
- **Source:** URW Base 35 fonts, fetched from
  `https://raw.githubusercontent.com/ArtifexSoftware/urw-base35-fonts/master/fonts/NimbusSans-Regular.otf`.
- **Licence:** AGPLv3, with a font exception permitting embedding in
  documents regardless of the document's own licence.
  - `LICENSE-nimbus.txt` is the exception notice, fetched from the same
    repository's `LICENSE` file. It refers to "the file COPYING" for the
    licence text itself.
  - `COPYING-nimbus.txt` is that referenced licence text — the full GNU
    Affero General Public Licence, Version 3 — fetched from
    `https://www.gnu.org/licenses/agpl-3.0.txt`.
  - Both files must ship together with this font wherever it is
    redistributed.

## Build-time input only

This font file is consumed only by `resources/lib/glyphgen.py`
(via `tools/build_bundled.py` and the pack-builder tooling in later
tasks) to rasterise character glyphs into PNG tile halves ahead of time.
It is **not** loaded by the Kodi add-on at runtime — the shipped add-on
contains the rendered PNGs in `resources/media/glyphs/`, not the font
file itself. `assets/` is a build-time/dev directory, not part of the
add-on's runtime resource tree.
