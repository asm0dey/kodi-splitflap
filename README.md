# Split-Flap Board

A Kodi screensaver that renders a mechanical split-flap (Solari) departure
board showing phrases, the time, and the weather.

Characters flap forward through a drum exactly as the hardware does — at the
real 200ms-per-flap rate, so a clock's minutes digit spins on every rollover
while its neighbour ticks once.

## Install

Settings → Add-ons → Install from repository → Look and feel → Screensaver →
Split-Flap Board.

Then Settings → Interface → Screensaver → Split-Flap Board.

To install from a downloaded zip instead: Settings → Add-ons → Install from
zip file, and pick the `screensaver.splitflap-<version>.zip` built by
`tools/build_addon.sh` (see Development below).

**Fire TV users:** Fire OS runs its own screensaver on its own timer. If
Kodi's screensaver timeout is *longer* than Fire OS's, Amazon's photo
screensaver activates first and Kodi's never gets a turn. Set Kodi's
screensaver timeout (Settings → Interface → Screensaver → Wait time)
shorter than Fire OS's (Settings → Display → Screensaver → Start Time) so
Split-Flap Board actually wins the race.

## Settings

| Setting | Meaning |
|---|---|
| Rows | Board height. Columns derive from it — the default 6 gives 22 columns, matching a real board. |
| Seconds per board | How long a finished board is held. Counted from when the flap finishes. |
| Maximum flap steps | Caps how many drum positions a cell steps through per transition, so a long jump around the drum doesn't take forever to settle. |
| Letter colour (RRGGBB) | Tile lettering colour. |
| Accent colour (RRGGBB) | Colour used for accented cells (e.g. an author line, a corner marker). |
| Show | What the board displays: live info or phrases. One at a time — they never interleave. |
| Time / Date / Weather / Now playing | Which live-info fields are shown, when Show is set to live info. |
| Combine onto one board | Whether the enabled live-info fields share one board, or rotate across separate boards. |
| Phrase file | One phrase per board. `#` comments and blank lines are ignored, `\n` puts the author on its own line. |
| Phrase URL | Optional remote phrase list, merged into the same pool as the phrase file. Fetched on a background thread; falls back to a disk cache if the fetch fails. |
| Glyph pack | Add-on id of an installed glyph pack, for non-Latin scripts or a different typeface. |

## Phrase file format

```
# Lines starting with a hash are ignored.
THE ONLY WAY OUT IS THROUGH\nROBERT FROST
KEEP GOING
```

One phrase per line. A literal `\n` inside a line splits it onto multiple
board lines — used to put an attribution/author on its own line below the
quote, as in the first example above. Blank lines and lines starting with
`#` are skipped.

## Glyph packs

The bundled glyphs cover capitals-only extended ASCII — Western European out
of the box. Anything else shows as tofu (□) until you install a pack.

Build one on a desktop with Python and Pillow:

```bash
python tools/make_glyph_pack.py --font YourFont.ttf \
  --charset ascii,cyrillic \
  --id resource.images.splitflap.yourfont-ru \
  --name "Split-Flap — YourFont, Latin + Cyrillic" \
  --out pack.zip
```

Include `ascii` in the letterset unless you want the board mixing two
typefaces. Named charsets currently available: `ascii`, `cyrillic`,
`greek`, `hebrew`. You can also pass literal characters with `--chars` or
read them from a file with `--chars-from`.

The result is a standard `kodi.resource.images` addon zip — install it like
any other addon (Install from zip file), then set the Glyph pack setting to
its id.

Arabic and Devanagari are out of scope: a cell grid cannot render connected
scripts. Real split-flap hardware has the same limitation.

## Development

```bash
pip install -e ".[dev]"
python -m pytest
python tools/build_bundled.py     # regenerate bundled glyphs
./tools/build_addon.sh            # package
```

The core is pure Python with no Kodi imports and is fully unit-tested. The
Kodi shell (`board.py`, `liveinfo.py`, `config.py`, `default.py`) is verified
by hand on a device — see `docs/superpowers/spikes/`.

## Licence

GPL-2.0-or-later. Bundled glyphs are rendered from Nimbus Sans (AGPLv3 with
font exception) — see `assets/fonts/LICENSE-nimbus.txt`.
