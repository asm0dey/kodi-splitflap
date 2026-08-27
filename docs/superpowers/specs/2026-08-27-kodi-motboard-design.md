# Kodi Motboard Screensaver — Design

**Date:** 2026-08-27
**Status:** Approved design, pre-implementation
**Reference:** https://motboard.com/images/landing/motboard-at-home.png

## Goal

A Kodi screensaver rendering a split-flap (Solari) departure board that displays
motivational phrases, clock, weather, and now-playing information.

Primary target: Kodi 21+ on Amazon Fire TV (Android ARM). Secondary: webOS, Raspberry
Pi, x86. Design to the weakest realistic target — Fire TV Stick 4K, Cortex-A53-class.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Animation fidelity | Real flap cycle | Chosen over flutter/instant-swap |
| Tile rendering | Pre-rendered glyph half-images | Full control of typeface; a `ControlLabel` inherits the user's skin font |
| Layout | Centered message, blank tiles around | Matches reference |
| Case | Capitals only | Real boards are caps; halves the glyph set |
| Grid config | Columns settable, rows derived | One knob; derived rows keep cell aspect constant so glyphs never stretch |
| Bundled charset | Extended ASCII, caps | Covers Western European out of the box |
| Other scripts | Installable glyph pack addons | No filesystem access on Fire TV / webOS |
| Missing glyph | Tofu (□) | Honest — signals "install a pack" where a flat letter hides the gap |
| Runtime glyph generation | Opportunistic, guarded | `script.module.pil` is broken on Android/tvOS/webOS; never a hard dependency |

### Rejected

- **Binary C++ screensaver addon** (`xbmc.ui.screensaver` native). Real GL, 60fps, true
  3D flap. Rejected: cross-compile toolchain per platform, cannot install from a zip.
  10x the cost for polish invisible at couch distance.
- **`ControlLabel` tiles.** Cheaper, but typography is dictated by whatever skin the
  user runs, and a label cannot show two different half-characters mid-flip.
- **Sprite atlas.** Kodi's `ControlImage` has no source-rect, so sub-rect UVs are
  impossible. Loose per-glyph PNGs instead; Kodi texture-caches them.
- **Pre-baked grid background PNG.** Only worked while geometry was frozen. Settable
  column count killed it. A blank tile is just another glyph, so there is no
  background layer at all.
- **Glyph pack download-on-demand.** Machinery to avoid shipping a few hundred KB.
  Packs are installable addons instead.

## Architecture

Hard split: pure Python core (no `xbmc` imports, unit-testable on Linux CI) vs a thin
Kodi shell.

```
resources/lib/
  layout.py      PURE  text -> screens: uppercase, wrap, centre, paginate
  template.py    PURE  {InfoLabel} substitution, --- screen splitting
  flap.py        PURE  animation state machine -> (tile, half, char) paint ops
  glyphs.py      PURE  glyph index: resolution order, codepoint naming
  glyphgen.py    PURE  TTF -> tile-half PNGs (PIL; try-imported)
  rotator.py     PURE  cycles sources, honours dwell + refresh
  sources/
    base.py      PURE  Source protocol
    textfile.py  PURE  one phrase per line
    remote.py    PURE  parse; fetch on a background thread
    infolabel.py KODI  thin getInfoLabel getter; substitution lives in template.py
  board.py       KODI  geometry, control creation, paint(tile, half, char)
default.py       KODI  entry point, window, main loop, exit handling
tools/
  build_bundled.py     DEV  bundled glyphs -> resources/media/glyphs/
  make_glyph_pack.py   DEV  font + letterset -> installable pack zip
```

`flap.py` never imports Kodi and never touches a control — it emits
`(tile_index, half, char)` tuples. `board.py` turns those into `setImage()`. That seam
is why the animation is testable without a running Kodi.

### Data flow

```
Source -> list[str] -> layout.screens() -> target grid
                                              |
                                    flap.retarget(target)
                                              |
  loop @ flap_fps: flap.tick(dt) -> ops -> board.paint() -> setImage()
```

Runtime dependencies: **zero**. Stdlib `urllib` for the remote source. PIL only if it
happens to import.

### addon.xml

```xml
<extension point="xbmc.ui.screensaver" library="default.py"/>
```
Requires `xbmc.python` 3.0.0. Python 3.8+ syntax (Kodi 19 onward); Kodi 21+ primary.

## Rendering

### Geometry

Kodi's fixed 1920x1080 skin coordinate space (`resources/skins/default/1080i/`); Kodi
scales to the actual output.

```
tile_w = (1920 - 2*margin - (cols-1)*gap) / cols
tile_h = tile_w / CELL_ASPECT            # CELL_ASPECT = 1.276
rows   = floor((1080 - 2*margin + gap) / (tile_h + gap))
```

Worked default (`cols=22`, `margin=40`, `gap=6`): `tile_w=77`, `tile_h=60`, `rows=15`.
Vertical margin is then recomputed to centre the grid.

### Controls

```
cols x rows = 22 x 15 = 330 cells
  text rows (default 3, centred)   66 cells x 2 halves = 132 ControlImage
  static rows (the other 12)      264 cells x 1 blank  = 264 ControlImage
                                                 total  396 controls
```

Static cells get a single full-tile blank image — they never flap, so they need no
hinge. Costs ~10 lines to support both cell shapes and saves 264 controls.

Controls are created once via a batch `addControls()` at window init.

### Glyphs

Rendered at a fixed **160x64** per half; Kodi scales them into the computed cell rect.
Rendering at ~2x the default cell size keeps 4K output crisp.

Filenames by **codepoint, never character**: `t_0041.png` / `b_0041.png`. Case-
insensitive filesystems collide `A` with `a`, and pack zips get built on macOS and
Windows.

The accent cell from the reference image is a `colordiffuse` attribute on a blank
tile — Kodi tints the texture, no extra asset.

## Animation

### Flap sequence

The **drum** is the ordered, circular character sequence a cell cycles through: blank
first, then the active glyph set's codepoints ascending. Motion is always forward and
wraps, so `drum_distance` is the forward-wrapping distance, never negative.

Constant step duration, no easing. Steps sampled at a fixed stride across the drum,
always landing exactly on the target:

```
distance   = drum_distance(cur, target)          # forward, wrapping
stride     = ceil(distance / MAX_STEPS)          # MAX_STEPS = 12
sequence   = [drum[(cur + i*stride) % len(drum)]
              for i in range(1, ceil(distance/stride))] + [target]
```

Selecting a glyph pack changes the active glyph set and therefore the drum.

With the caps-only extended-ASCII drum (~143 chars) and `MAX_STEPS=12`, stride lands
in the 1-12 range; large strides only occur on a big pack charset.

### Half-step model

One `setImage()` per half-step. Top half leads, bottom half lands:

```
step k:  top    <- sequence[k+1]     (card face swings down)
         bottom <- sequence[k+1]     (card lands)
```

The transient mismatch between halves *is* the hinge effect.

### Stagger

`delay = col*COL_DELAY + row*ROW_DELAY + jitter` — ripples left-to-right like a real
board updating.

### Loop

Fixed-timestep accumulator so flap timing does not wobble with frame jitter. A settled
board emits **zero** paint ops, so cost is confined to the ~1s transition between
screens.

Exit on any of: `onAction`, `Monitor.abortRequested()`, `System.ScreenSaverActive`
going false. Belt and braces — the exact contract is a spike item.

## Glyph pipeline

### Resolution order

First hit wins; index built once at window init.

```
addon_data/glyphs/   ->   SELECTED PACK   ->   bundled   ->   tofu
```

`addon_data/glyphs/` is the runtime-PIL cache, and doubles as a manual drop directory
for desktop users.

### Bundled set

Capitals-only **extended ASCII**, defined as an explicit codepoint list (not a range
minus guesswork):

| set | chars |
|---|---|
| ASCII printable minus a-z | 69 |
| Latin-1 Supplement (U+00A0-00FF) minus lowercase | 64 |
| CP1252 typographic extras (`€ — – " " ' ' …`) | ~10 |
| U+039C, uppercase target of `µ` | 1 |
| tofu (□), the missing-glyph marker | 1 |
| **total** | **~145 chars, 290 files, ~290 KB** |

Tofu is a bundled glyph pair like any other, so it is always present regardless of
which pack is selected — the fallback can never itself be missing.

**Case expansion occupies multiple cells.** Uppercasing is applied to the whole
*string* in `layout.py` before the text is gridded, so a character that expands under
`str.upper()` naturally takes one cell per resulting character — `straße` becomes
`STRASSE`, seven cells, not six with a tofu. This is why step 1 of the layout pipeline
must precede step 2: expansion changes line length, so wrapping has to run on the
already-uppercased text.

**Invariant, unit-tested:** for every `c` in `BUNDLED`, every character of `c.upper()`
is also in `BUNDLED`. Note the per-character form — a set comparison against
`c.upper()` as a whole would wrongly fail `ß` (whose `'SS'` is fine) while the real
gap is elsewhere: `str.upper('µ')` is Greek capital Mu (U+039C), a single character
outside Latin-1. Resolution when this test fires is either to add the target glyph or
drop the source character; for `µ` the spec adds **U+039C**, two more files.

Since lowercase is absent from the bundle, `layout.py`'s `str.upper()` is load-bearing,
not cosmetic.

### Packs

A pack is a standard `kodi.resource.images` addon, addressed as
`resource://<addon.id>/<file>`. No custom loader; installable from zip on Android or
from a repo URL on webOS.

A pack carries **a font and a letterset**, so it serves two purposes: adding scripts,
and restyling the whole board in a different typeface. Settings exposes a single
`glyph pack` dropdown (installed `resource.images.motboard.*` addons, default *none*)
rather than a priority list. A pack whose letterset includes ASCII therefore overrides
the bundle completely and the board stays typographically consistent.

```
make_glyph_pack.py --font NotoSans.ttf \
                   --charset ascii,cyrillic \
                   --id resource.images.motboard.noto-ru \
                   --name "Motboard — Noto, Latin + Cyrillic" \
                   --out resource.images.motboard.noto-ru.zip
```

Emits `addon.xml`, glyph PNGs, `pack.json` (font name, charset, glyph pixel size), and
an icon. Named charset flags for the common sets; `--chars "..."` or
`--chars-from file.txt` for anything else, including a CJK subset built from a phrase
list. Warns when the letterset omits ASCII, since that is the mixed-typeface case.

`pack.json` metrics are a **warning, not a rejection** — glyphs scale into the cell, so
a size difference is harmless; only a wildly different aspect ratio is worth flagging.

### Runtime generation

Guarded `try: from PIL import Image`. Runs on a **background thread** — rasterising ~30
glyphs takes seconds and must never stall the flap loop. Missing characters show tofu
and land on the next flap once the thread finishes. Requires shipping one OFL-licensed
TTF (Inter or DejaVu), which is needed anyway to keep packs visually consistent with
the bundle.

Expected to be dead code on Fire TV and webOS, where `script.module.pil` does not
reliably import. Included because `glyphgen.py` exists regardless.

One rasteriser, three callers: `build_bundled.py`, `make_glyph_pack.py`, runtime.
No drift between the three.

## Sources

```python
class Source(Protocol):
    id: str
    enabled: bool
    def screens(self) -> list[list[str]]: ...
```

| source | impl | notes |
|---|---|---|
| `textfile` | pure | one phrase per line, `#` comments, blank lines dropped, mtime reload |
| `remote` | pure parse, threaded fetch | `urllib` with timeout. Plain text or JSON (`[...]` / `{"phrases":[...]}`). Caches to `addon_data` with TTL. Fail -> cache -> bundled defaults. Never on the render thread |
| `infolabel` | pure substitution, thin `xbmc.getInfoLabel` getter | template-driven; see below |

### The info source

One template-driven source replaces separate clock / weather / now-playing classes.
`{Token}` resolves through `xbmc.getInfoLabel('Token')`; `---` on its own line
separates screens.

```
{System.Time}
---
{Weather.Location}
{Weather.Temperature} {Weather.Conditions}
```

Settings exposes a **preset dropdown** that fills the template, plus the raw field for
custom use — editing a template with a TV remote is miserable, so the presets are the
real interface:

| preset | screens |
|---|---|
| Time | `{System.Time}` |
| Weather | location, then temperature + conditions |
| Time + Weather | both on one board |
| Time, then Weather | two screens, alternating |
| Now playing | `{MusicPlayer.Artist}` / `{MusicPlayer.Title}` |
| Custom | raw template field |

**Empty-token rule** (generalises what was previously per-source auto-disable): a token
resolving empty drops its line; a screen resolving wholly empty is skipped. So an
unconfigured weather addon means the weather screen never appears, rather than a board
of blanks.

Substitution is pure and unit-tested; only the getter touches Kodi. Weather comes from
Kodi's own weather service, so this addon needs no API keys, no HTTP, and no secrets.
It renders as the reference does: `SYDNEY` / `17° RAIN`.

Now-playing is music-only in practice — Kodi does not screensave over video.

`rotator.py` round-robins enabled sources, `dwell` seconds per screen, re-reading live
sources on each turn.

## Layout

`layout.py`, pure:

1. uppercase the whole string (case expansion such as `ß` -> `SS` yields extra cells)
2. greedy word-wrap to `cols`, on the already-uppercased text; over-long words
   hard-split
3. centre each line horizontally
4. centre the block vertically into the text rows
5. paginate to consecutive screens on overflow
6. pad with blank

Right-to-left scripts (Hebrew) get the line reversed. **Out of scope:** Arabic and
Devanagari — a cell grid cannot render connected scripts, and no amount of glyph
generation fixes it. Real split-flap hardware has the same limitation.

## Settings

```
Board     columns (22) | text rows (3) | flap fps (20) | max steps (12) | accent colour
Glyphs    glyph pack (none)
Sources   per-source enable | file path | remote URL | refresh mins | dwell secs | order
Info      preset (Time / Weather / Time + Weather / Time then Weather / Now playing /
          Custom) | template (Custom only)
```

## Distribution

Addon zip (`screensaver.motboard`) plus a static Kodi repository on GitHub Pages
(`addons.xml`, `addons.xml.md5`, zips). Installs and updates work on Fire TV and webOS
without touching a filesystem. Glyph packs ship through the same repo.

## Testing

Automated (`pytest` on Linux CI, no Kodi):

- `layout` — wrap, centre, paginate, uppercase including accented, **case expansion
  (`ß` -> two cells) measured after wrapping**, RTL reverse, over-long word
- `flap` — stride maths, step-count bounds, op ordering, stagger, **settled board emits
  zero ops**
- `sources` — JSON/text/comment parsing, malformed input, cache fallback chain
- `template` — token substitution, `---` splitting, empty-token line drop, wholly-empty
  screen skip, unknown token
- `glyphs` — resolution order, codepoint naming, uppercase-closure invariant,
  pack-metrics warning
- `glyphgen` — file count and codepoint naming; no pixel goldens

Manual only (platform-bound, cannot run in CI): window construction, control count,
`setImage` throughput, exit contract. Procedure:

1. Install on a Fire TV Stick 4K. Set Kodi's screensaver timeout below Fire OS's.
2. Confirm the board builds and the first screen flaps within 2s of activation.
3. Confirm any remote-control input dismisses it and returns to the previous window.
4. Confirm a settled board consumes no measurable CPU (`top` over ssh/adb).
5. Install a glyph pack, select it, confirm `resource://` glyphs resolve.
6. Select a pack lacking a character in the phrase list; confirm tofu, not a crash.

## Spike — run before implementation

Approximately one hour. Any outcome invalidates a constant, none invalidates the
structure.

1. **Exit contract** — which of `onAction` / `System.ScreenSaverActive` /
   `abortRequested` actually fires for a Python screensaver, and in what order.
2. **Control budget** — 396 controls on a Fire TV Stick 4K: window init time, memory,
   `setImage` throughput at 20fps. Fallback if it bites: smaller default grid.
3. **`resource://` resolution** — reading glyph files from an installed
   `kodi.resource.images` pack from addon Python.

## Notes

- Fire OS runs its own screensaver. Kodi's timeout must be shorter or Amazon's photo
  screensaver wins. README note, not code.
- `str.upper()` on Turkish dotless-i is wrong. Known, ignored.
