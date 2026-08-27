# Split-Flap Board

A Kodi screensaver that renders a mechanical split-flap (Solari) departure
board showing phrases, the time, and the weather.

Characters flap forward through a drum exactly as the hardware does — at the
real 200ms-per-flap rate, so a clock's minutes digit spins on every rollover
while its neighbour ticks once.

## Install

**[⬇ repository.splitflap-1.0.0.zip](https://asm0dey.github.io/kodi-splitflap/repo/repository.splitflap/repository.splitflap-1.0.0.zip)**
— install this one file and everything else follows.

Settings → Add-ons → **Install from zip file** → pick that zip. Then
Settings → Add-ons → **Install from repository** → Split-Flap Repository →
Look and feel → Screensaver → **Split-Flap Board**.

Finally Settings → Interface → Screensaver → **Split-Flap Board**.

Installing the repository rather than the screensaver directly is worth the
extra step: the screensaver and any glyph packs then update themselves through
Kodi's normal add-on browser, which matters on a Fire TV or webOS box where
there is no comfortable way to copy a file onto the device again.

### Adding it as a source instead

If you would rather Kodi fetch the repository zip itself — Settings → File
manager → Add source:

```
https://asm0dey.github.io/kodi-splitflap/repo
```

Name it `splitflap`, then Install from zip file → splitflap →
`repository.splitflap/`.

### Just the screensaver

Direct downloads, no updates:

- **[screensaver.splitflap](https://asm0dey.github.io/kodi-splitflap/repo/screensaver.splitflap/)** — the screensaver
- **[resource.images.splitflap.nimbus-ru](https://asm0dey.github.io/kodi-splitflap/repo/resource.images.splitflap.nimbus-ru/)** — Cyrillic glyph pack
- **[script.splitflap.source.recentlyadded](https://asm0dey.github.io/kodi-splitflap/repo/script.splitflap.source.recentlyadded/)** — Recently Added source add-on

Or build one yourself with `tools/build_addon.sh` (see Development below).

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
| Show | What the board displays: live info, phrases, or an installed contributor add-on (see "Writing a source add-on" below). One at a time — they never interleave. |
| Time / Date / Weather / Now playing | Which live-info fields are shown, when Show is set to live info. |
| Combine onto one board | Whether the enabled live-info fields share one board, or rotate across separate boards. |
| Phrase file | One phrase per board. `#` comments and blank lines are ignored, `\n` puts the author on its own line. |
| Phrase URL | Optional remote phrase list, merged into the same pool as the phrase file. Fetched on a background thread; falls back to a disk cache if the fetch fails. |
| Glyph pack | Add-on id of an installed glyph pack, for non-Latin scripts or a different typeface. |
| Source add-on | When Show is set to Add-on, this button lists the installed source add-ons by name — pick one, nothing to type. Left unset, the screensaver uses whichever contributor it finds; an uninstalled or missing one falls back to live info. |
| Configure source add-on | Opens the picked add-on's own settings. |

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

## Recently Added

A bundled source add-on, `script.splitflap.source.recentlyadded`, boards the
newest additions to Kodi's video library — one item per board:

```
█ THE BEAR
█ S03E04 HONEYDEW
```

Movies and episodes are merged into one newest-first list and the top N kept,
with no per-type quota: if the last twenty things added were all episodes, you
get twenty episode boards. A movie's second line is its year, an episode's is
its season/episode code and title. Both lines carry an accent marker.

Install it from the repository, then set Show to **Add-on**. Its own settings
(Add-ons → My add-ons → ...) are:

| Setting | Meaning |
|---|---|
| Seconds per board | How long each item is held. Independent of the screensaver's own hold — it can be longer or shorter. |
| How many recent items to cycle | Top N, newest first. Re-queried when the cycle wraps. |

An empty library boards `NO RECENT ADDITIONS`; a library query that fails keeps
showing the last items it did get.

## Writing a source add-on

A source add-on supplies board content; this add-on renders it. Declare a
normal python module with an id under `script.splitflap.source.` and expose
`create_source()` from `source.py`:

```python
# script.splitflap.source.quotes/source.py
class QuoteSource:
    id = "script.splitflap.source.quotes"

    def next(self):
        return {
            "lines": ["THE ONLY WAY OUT", "IS THROUGH"],
            "accents": [{"corner": "top-left"}],
            "refresh_in": None,
        }


def create_source():
    return QuoteSource()
```

`next()` is called when the board's hold expires, or after `refresh_in`
seconds, whichever comes first. Return `refresh_in: None` if your content
only changes when asked.

Return any object with a `next()` method; a plain dict with `lines`,
`accents` and `refresh_in` works. Accents are positioned relatively —
`{"before_line": n}`, `{"corner": "top-left"}` — or explicitly with
`{"cell": [row, col]}`.

Keep `next()` fast. It runs on the render loop, and a source that raises is
disabled for the session while a source that **hangs** freezes the
screensaver.

No dependency declaration is needed on either side — this add-on discovers
any installed, enabled `xbmc.python.module` add-on whose id starts with
`script.splitflap.source.` and calls its `create_source()`. Set Show to
Add-on to use it (optionally naming the exact Source add-on id if more than
one contributor is installed). A contributor that fails to import, has no
`create_source()`, or whose `next()` raises is skipped and logged — one
broken contributor never hides the others, and an uninstalled or missing
contributor falls back to live info.

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

## Reinstalling during development

Kodi refuses an install-from-zip whose version is not newer than the one
already installed, so a rebuilt zip at the same version silently fails to
install. Build with `--bump` and each zip gets the next patch version, so it installs
over the previous one:

```bash
./tools/build_addon.sh --bump      # 0.1.1 -> 0.1.2 -> 0.1.3 ...
./tools/build_addon.sh             # rebuild at the current version
python3 tools/bump_version.py minor   # or major, when it is a real release
```

To reinstall the *same* version instead, remove the add-on first:

```bash

# or, to reinstall the same version
rm -rf ~/.kodi/addons/screensaver.splitflap    # desktop
adb shell pm clear org.xbmc.kodi               # Fire TV: nuclear, wipes settings
```

On a Fire TV the gentler route is Settings → Add-ons → My add-ons →
Screensavers → Split-Flap Board → Uninstall, then install the new zip.
