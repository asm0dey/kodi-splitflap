# Split-Flap Board — Kodi Screensaver Design

**Date:** 2026-08-27
**Status:** Approved design, pre-implementation
**Addon id:** `screensaver.splitflap` — display name "Split-Flap Board"
**Visual reference:** https://motboard.com/images/landing/motboard-at-home.png

## Goal

A Kodi screensaver rendering a mechanical split-flap (Solari) board that displays
phrases, the time, and weather.

Primary target: Kodi 21+ on Amazon Fire TV (Android ARM). Secondary: webOS, Raspberry
Pi, x86. Design to the weakest realistic target — Fire TV Stick 4K, Cortex-A53-class.

Vocabulary is defined in `CONTEXT.md` and used precisely throughout.

## Decisions

| Decision | Choice | Why |
|---|---|---|
| Animation fidelity | Real flap cycle | Chosen over flutter and instant-swap |
| Tile rendering | Pre-rendered glyph half-images | Full control of typeface; a `ControlLabel` inherits the user's skin font and cannot show two half-characters mid-flip |
| Glyph content | Card and shading baked in, greyscale | One image per half, and `colordiffuse` gives configurable colour for free |
| Layout | Centred block, blank tiles around | Matches reference |
| Case | Capitals only | Real boards are caps; halves the glyph set |
| Geometry | Rows settable, columns derived | One knob. Measured from the reference: 22x6 |
| Bundled charset | Extended ASCII, caps | Covers Western European out of the box |
| Other scripts | Installable glyph pack addons | No filesystem access on Fire TV or webOS |
| Missing glyph | Tofu | Honest — signals "install a pack" where a flat letter hides the gap |
| Sources | Exactly one active at a time | No interleaving |
| Distribution | Official Kodi repository | A self-hosted repo means typing a URL with a d-pad |
| Sound | Silent | A screensaver that clatters at 2am is a support ticket |

### Rejected

- **Binary C++ screensaver addon.** Real GL, 60fps, true 3D flap. Rejected: cross-compile
  toolchain per platform, cannot install from a zip. 10x the cost for polish invisible at
  couch distance.
- **`ControlLabel` tiles.** Typography dictated by the user's skin, and a label cannot
  show two different half-characters mid-flip.
- **Sprite atlas.** Kodi's `ControlImage` has no source-rect. Loose per-glyph PNGs
  instead; Kodi texture-caches them.
- **Pre-baked grid background.** Only worked while geometry was frozen. A blank tile is
  just another glyph, so there is no background layer at all.
- **Glyph pack download-on-demand.** Machinery to avoid shipping a few hundred KB.
- **Cross-source rotation.** Round-robin, weights, and interleave ratios all deleted: one
  source is active and the rotator only advances within it.
- **A separate `advance()` method.** Identical content produces zero paint ops, so
  refreshing in place and advancing are indistinguishable at the render layer.
- **Pagination.** One source line is always exactly one board.

## Architecture

Hard split: pure Python core (no `xbmc` imports, unit-testable on Linux CI) against a
thin Kodi shell.

```
resources/lib/
  layout.py      PURE  one line -> one board: uppercase, wrap, centre, ellipsise
  flap.py        PURE  drum + animation state machine -> paint ops
  glyphs.py      PURE  glyph index: resolution order, codepoint naming
  glyphgen.py    PURE  TTF -> tile-half PNGs (PIL, try-imported)
  rotator.py     PURE  advances the active source; owns hold timing
  compose.py     PURE  live-info checkbox state + values -> lines + accents
  sources/
    base.py      PURE  Source protocol, Content
    phrases.py   PURE  file + URL merged pool, shuffle without repeat
    remote.py    PURE  parse; fetch on a background thread
    liveinfo.py  KODI  infolabel getter; composition lives in compose.py
    discovery.py KODI  contributor addon discovery (v2)
  board.py       KODI  geometry, control creation, paint(cell, half, char)
default.py       KODI  entry point, window, main loop, exit handling
tools/
  build_bundled.py     DEV  bundled glyphs -> resources/media/glyphs/
  make_glyph_pack.py   DEV  font + letterset -> installable pack zip
```

`flap.py` never imports Kodi and never touches a control — it emits
`(cell_index, half, char)` tuples. `board.py` turns those into `setImage()`. That seam
is why the animation is testable without a running Kodi.

### Data flow

```
Source.next() -> Content -> layout.board() -> target grid
                                                 |
                                       flap.retarget(target)
                                                 |
     loop @ flap_fps: flap.tick(dt) -> ops -> board.paint() -> setImage()
```

Runtime dependencies: **zero**. Stdlib `urllib` for the remote fetch. PIL only if it
happens to import.

### addon.xml

```xml
<extension point="xbmc.ui.screensaver" library="default.py"/>
```

Requires `xbmc.python` 3.0.0. **Python 3.11 is the floor** — Kodi 21 (Omega) ships it,
and official-repo submission happens on per-Kodi-version branches, so Omega and Piers
are the targets. Kodi 19/20 (Python 3.8) are deliberately not supported: keeping them
would mean `typing.Tuple`/`List`/`Dict` throughout, deprecated since 3.9, to serve
versions this addon does not target.

## Geometry

Measured from the reference image by FFT of the tile field: **22 columns, 6 rows, cell
aspect w/h = 0.55**. Split-flap cards are portrait — taller than wide.

`rows` is the only geometry setting (default 6). The tile field's own aspect is
**2.0**, measured from the reference — wider than 16:9 — so the grid fills the width and
letterboxes vertically. That fixed board aspect is what makes columns derivable:

```
CELL_ASPECT  = 0.55                                  # width / height, portrait card
BOARD_ASPECT = 2.0                                   # tile field, measured
cols   = round(rows * BOARD_ASPECT / CELL_ASPECT)    # rows=6 -> 22
tile_w = (W - 2*margin - (cols-1)*gap) / cols
tile_h = tile_w / CELL_ASPECT
```

In Kodi's fixed 1920x1080 skin coordinate space (`resources/skins/default/1080i/`);
Kodi scales to the actual output. At `rows=6`: 22 columns, `tile_w` ~78, `tile_h` ~142,
board height ~881 of 1080 — matching the reference, with its letterboxing above and
below.

The grid is centred vertically in whatever height remains. Because `BOARD_ASPECT` (2.0)
always exceeds the frame's (1.78), the board fills width and fits vertically at every
row count, so no clamping is needed.

Deriving columns by instead filling the *height* — the largest tiles that fit both
dimensions — yields 18 columns at `rows=6` and does not match the reference. The board
is deliberately not height-filling.

`margin` defaults to ~2% of the frame to survive TV overscan.

### Controls

Every cell is a tile of two halves. There is no band, no static-cell class, no second
code path:

```
cols x rows = 22 x 6 = 132 cells
132 cells x 2 halves  = 264 ControlImage
```

Created once via a batch `addControls()` at window init.

### Glyphs

A half at default geometry is ~78x71, rendered at 2x (~156x142) so 4K output stays
crisp; Kodi scales them into the computed cell rect. The bundled set is roughly **1 MB**.

Greyscale, with the card and its shading baked in. Two `colordiffuse` tints are applied
at runtime: letters default `#E8E8E8`, accent cells default `#2B5CE6`.

A single tint multiplies over the whole half, card and letterform together. Because the
card is near-black it barely moves while the light letterform takes the colour — which
is why **a light board with dark letters is impossible via tint** and would ship as a
glyph pack instead.

Filenames by **codepoint, never character**: `t_0041.png` / `b_0041.png`. Case-
insensitive filesystems collide `A` with `a`, and pack zips get built on macOS and
Windows.

## Animation

### Drum

The ordered, circular sequence a tile cycles through: blank first, then the active glyph
set's codepoints ascending. Motion is always forward and wraps, so `drum_distance` is
the forward-wrapping distance, never negative. Selecting a glyph pack changes the active
glyph set and therefore the drum.

A character absent from the current drum — after a mid-session pack change — is treated
as blank and flaps from there.

**Our drum is longer than any real board's.** Solari modules carried 40 flaps (the
original Liege board) up to 64 (Changi T2); bundling extended ASCII gives us 142 in one
cycle. Hardware never mixed accented capitals into the letter drum.

This makes stride sampling visible rather than cosmetic: a real 40-flap revolution shows
40 contiguous characters, while 12 steps across 142 shows every ~12th, which reads as
scrambling rather than a drum spinning through the alphabet. `MAX_STEPS` is therefore a
**tuning constant, not a derived value** — raising it toward 40 buys contiguity at 200ms
each, so the trade is directly wall-clock time. Settle it on a TV during the spike.

Note that a physically accurate cell mixes the two: hardware is slower per step *and*
shows every character. We take its step rate and drop its step count.

### Flap sequence

Constant step duration, no easing. Steps sampled at a fixed stride across the drum,
always landing exactly on the target:

```
distance = drum_distance(cur, target)            # forward, wrapping
stride   = ceil(distance / MAX_STEPS)            # MAX_STEPS = 12
sequence = [drum[(cur + i*stride) % len(drum)]
            for i in range(1, ceil(distance/stride))] + [target]
```

### Half-step model

One `setImage()` per half-step. Top half leads, bottom half lands:

```
step k:  top    <- sequence[k+1]     (card face swings down)
         bottom <- sequence[k+1]     (card lands)
```

The transient mismatch between halves *is* the hinge effect.

**Timing.** A step is one character advance — one card falling — rendered as two
half-steps (top lands, then bottom). Real Solari modules run at a reported **5 flaps per
second, i.e. 200ms per character**, so a 40-flap revolution takes about 8 seconds.

We keep the hardware step rate and clamp the count instead:

| | real hardware | here |
|---|---|---|
| one character step | 200ms | **200ms** |
| full revolution | 8s (40 flaps) | **2.4s** (12 steps, clamped) |

A single-character change (`'1'` -> `'2'`, adjacent in the drum) therefore takes 200ms
and looks exactly like hardware — and that is the case on screen constantly, once per
clock tick. Only a full wrap is stylised, because a clock whose minutes digit takes
eight seconds to roll over is a broken clock. Fidelity where it shows, brevity only
where fidelity would hurt.

**Forward-only motion has a visible consequence.** The drum cannot reverse, so a target
whose codepoint is *below* the current one wraps the whole drum. `'9'` -> `'0'` is the
common case: U+0030 sits below U+0039, so a clock's minutes digit spins a full
revolution each time it rolls over while the tens digit ticks a single step. This
matches real hardware, where a physical drum has the same constraint.

### Transitions

**Direct retarget** — no clear-to-blank between boards. Cells whose character is
unchanged do not move at all, which reads as deliberate.

**Stagger:** `delay = col*COL_DELAY + row*ROW_DELAY + jitter`, rippling left-to-right
like a real board updating.

**A settled board emits zero paint ops**, so cost is confined to the transition.

### Loop

Fixed-timestep accumulator so flap timing does not wobble with frame jitter. `flap_fps`
defaults to 20.

Exit on any of `onAction`, `Monitor.abortRequested()`, or `System.ScreenSaverActive`
going false — belt and braces, since the exact contract is a spike item.

Settings are read at each screensaver activation, and geometry is rebuilt then. Nothing
needs to handle a live settings change, because settings cannot be edited while the
screensaver is running.

## Sources

Exactly one source is active at a time, chosen from a settings dropdown: **Phrases**,
**Live info**, or any installed contributor addon. There is no interleaving and no
cross-source rotation; `rotator.py` only advances within the active source.

If the selected contributor addon is uninstalled, the board falls back to Live info —
the one source that always resolves, since `System.Time` cannot be empty.

### Protocol

```python
class Source(Protocol):
    id: str
    def next(self) -> Content: ...

# Content = { lines: list[str], accents: list[dict], refresh_in: float | None }
```

`next()` is called when **hold expires**, or when the source's own **`refresh_in`**
fires, whichever comes first. Pull, not push: no callbacks, and no third-party code
inside the render loop.

One method suffices because identical content produces zero paint ops — refreshing in
place and advancing are indistinguishable at the render layer. `refresh_in` is what
prevents a fast poll from racing the phrase list: phrases return `None` and so advance
only on hold, while live info returns seconds-to-the-next-minute and re-flaps its clock
mid-hold.

**Timing ownership:** the source owns data freshness via `refresh_in`; we own
presentation via `hold`. A source can never override a user's display setting.

**Failure policy:** every call is wrapped; a source that raises is disabled for the
session and the board falls back to Live info, logged loudly. A source that *hangs*
freezes the screensaver — an accepted limitation, revisitable when contributor discovery
ships, since the two built-in sources cannot hang.

### Accents

Accent cells are part of a source's returned content, not global decoration. A source
hands us lines and has no idea where they land after uppercasing, wrapping and centring,
so positions are expressed relatively; `cell` exists as an escape hatch for contributors
wanting explicit control:

```python
accents = [
    {"before_line": 1},        # cell immediately left of line 1
    {"corner": "top-left"},    # grid corner
    {"cell": [3, 7]},          # explicit row/col — escape hatch
]
```

### Phrases

File path and remote URL feed **one merged pool** — the distinction is plumbing, not
content, and merging a curated list with a remote one falls out for free.

Ordering is **shuffled without repeat until the pool is exhausted**, then reshuffled.
Plain random visibly repeats and reads as a bug.

`\n` in a phrase splits the author onto its own line: `THE ONLY WAY OUT IS THROUGH\n
ROBERT FROST`. A real newline cannot serve, since one file line is one phrase. `#`
starts a comment; blank lines are dropped; the file is reloaded when its mtime changes.

Accents: `{"corner": "top-left"}`, `{"corner": "top-right"}`, and `{"before_line": n}`
for the author line.

**20-30 phrases ship with the addon**, and the path defaults to them so selecting
Phrases always shows something and the file doubles as format documentation. Quote
selection avoids copyright risk — well-known attributed lines from public-domain-era
authors.

`refresh_in` is `None`.

### Live info

Checkboxes select content — time, date, weather, now playing — and a **Combine** option
decides whether they join one board or rotate as separate boards. `compose.py` turns
that state plus resolved values into lines and accents.

Values come from Kodi's own infolabels (`System.Time`, `System.Date`, `Weather.Location`,
`Weather.Temperature`, `Weather.Conditions`, `MusicPlayer.Artist`, `MusicPlayer.Title`),
so this addon needs no API keys, no HTTP, and no secrets. It renders as the reference
does: `SYDNEY` / `17° RAIN`.

**Empty-token rule:** a value resolving empty drops its line; a board resolving wholly
empty is skipped. An unconfigured weather addon therefore means the weather board never
appears, rather than a board of blanks.

Accents sit immediately left of the time line and the weather line.

`refresh_in` is the seconds remaining to the next minute, so a displayed clock re-flaps
in place. Now playing is music-only in practice — Kodi does not screensave over video.

### Contributor addons (v2)

The protocol above is the contract, proven by the two built-in sources before anyone
external depends on it. Discovery ships in v2 and is roughly twenty lines: JSON-RPC
`Addons.GetAddons` filtered by a known id prefix, each path resolved with
`xbmcaddon.Addon(id).getAddonInfo('path')`, entry module loaded with `importlib`. No
dependency declaration is needed, which is the part that has to be right.

## Layout

`layout.py`, pure:

1. uppercase the whole string — case expansion such as `ß` -> `SS` yields extra cells
2. greedy word-wrap to `cols`, on the already-uppercased text; over-long words hard-split
3. centre each line horizontally
4. size the block to its wrapped line count and centre it vertically in the grid
5. on overflow past `rows`, keep the first rows and **ellipsise**: the last kept row is
   hard-filled to full width from the remaining text, its final cell replaced with `…`
6. pad with blank

Step 1 must precede step 2 because expansion changes line length. Step 5 hard-fills
rather than reusing the wrapped line, because a centred short final line would leave the
`…` floating mid-row; filling to full width puts it in the last cell, where a board
running out of space would put it.

**One source line is always one board.** There is no pagination — `layout.board()`
returns a single board, never a sequence.

Right-to-left scripts (Hebrew) get the line reversed, and the ellipsis goes at the
visual end — the left. **Out of scope:** Arabic and Devanagari. A cell grid cannot
render connected scripts, and no amount of glyph generation fixes it. Real split-flap
hardware has the same limitation.

`layout.build`'s `rtl` parameter implements this and is unit-tested, but nothing in
`default.py` passes it and there is no settings entry to control it, so RTL rendering
is not currently reachable at runtime.

## Glyph pipeline

### Resolution order

First hit wins; index built once at window init.

```
addon_data/glyphs/   ->   selected pack   ->   bundled   ->   tofu
```

`addon_data/glyphs/` is the runtime-PIL cache, and doubles as a manual drop directory
for desktop users.

### Bundled set

Capitals-only **extended ASCII**, defined as an explicit codepoint list rather than a
range minus guesswork:

| set | chars |
|---|---|
| ASCII printable minus a-z | 69 |
| Latin-1 Supplement (U+00A0-00FF) minus lowercase | 64 |
| CP1252 typographic extras (`€ — – " " ' ' …`) | ~10 |
| U+039C, uppercase target of `µ` | 1 |
| tofu, the missing-glyph marker | 1 |
| **total** | **142 chars, 284 files, ~1 MB** |

Tofu is a bundled glyph like any other, so it is always present regardless of which pack
is selected — the fallback can never itself be missing.

**Case expansion occupies multiple cells.** Uppercasing is applied to the whole string
in `layout.py` before gridding, so `straße` becomes `STRASSE` — seven cells, not six
with a tofu.

**Invariant, unit-tested:** for every `c` in the bundled set, every character of
`c.upper()` is also in the set. Note the per-character form — comparing against
`c.upper()` as a whole would wrongly fail `ß`, whose `SS` is fine, while the real gap is
`str.upper('µ')`, a single Greek capital Mu outside Latin-1.

Since lowercase is absent, `layout.py`'s `str.upper()` is load-bearing, not cosmetic.

### Font

**Nimbus Sans**, rendered at Light or Regular weight. There is no published name for the
Solari typeface; what is documented is that Massimo Vignelli chose the lettering for
Solari's Cifra 3, and Vignelli was the era's foremost Helvetica advocate — which is why
real Solari boards read as Helvetica-family neo-grotesque. Nimbus Sans is a true
Helvetica clone rather than merely metric-compatible, making it the closest freely
licensed match. Light weight matches the reference's thin letterforms; tracking comes
free from the cell grid.

Licensed AGPLv3 **with a font exception**. The exception covers embedding, and a font
file beside our code is aggregation rather than linking, so this should pass review. If
a Kodi reviewer objects — addons are commonly GPLv2+, which is not AGPLv3-compatible —
the contingency is **Liberation Sans** (OFL 1.1): one regeneration of the bundled
glyphs, zero code, because the font is only ever an input to `glyphgen.py`.

The font's licence ships with the addon.

### Packs

A pack is a standard `kodi.resource.images` addon, addressed as
`resource://<addon.id>/<file>`. No custom loader, and it installs from the official
repository — so packs need no URL typing either.

A pack carries **a font and a letterset**, serving two purposes: adding scripts, and
restyling the whole board. Settings exposes a single `glyph pack` dropdown listing
installed `resource.images.splitflap.*` addons, default *none*, rather than a priority
list. A pack whose letterset includes ASCII therefore overrides the bundle completely
and the board stays typographically consistent.

```
make_glyph_pack.py --font NotoSans.ttf \
                   --charset ascii,cyrillic \
                   --id resource.images.splitflap.noto-ru \
                   --name "Split-Flap — Noto, Latin + Cyrillic" \
                   --out resource.images.splitflap.noto-ru.zip
```

Emits `addon.xml`, glyph PNGs, `pack.json` (font name, charset, glyph pixel size), and
an icon. Named charset flags for the common sets; `--chars` or `--chars-from` for
anything else, including a CJK subset built from a phrase list. Warns when the letterset
omits ASCII, since that is the mixed-typeface case.

`pack.json` metrics are a **warning, not a rejection** — glyphs scale into the cell, so
a size difference is harmless; only a wildly different aspect ratio is worth flagging.

### Runtime generation

Guarded `try: from PIL import Image`. Runs on a **background thread** — rasterising ~30
glyphs takes seconds and must never stall the flap loop. Missing characters show tofu
and land on the next flap once the thread finishes.

Expected to be unavailable on Fire TV and webOS, where `script.module.pil` does not
reliably import. Kept because it costs little: `glyphgen.py` exists regardless.

One rasteriser, three callers — `build_bundled.py`, `make_glyph_pack.py`, runtime — so
there is no drift between them.

## Settings

```
Board     rows (6) | flap fps (20) | max steps (12) | letter colour | accent colour
Timing    seconds per board (15)
Content   source (Live info / Phrases / <contributor>)
          phrases: file path | remote URL | refresh mins
          live info: time | date | weather | now playing | combine
Glyphs    glyph pack (none)
```

`Hold` — "seconds per board" in the UI — counts from when the flap **finishes**, so
raising it from 5s to 10s doubles reading time rather than adding a variable flap on top.

Default source is Live info, so a fresh install shows time, date and weather with no
configuration and is never blank.

English-only strings for v1, via `strings.po`, so translation needs no code change.

## Distribution

Target the **official Kodi repository**. It is configured in every install, so the addon
appears under Screensavers with one click and auto-updates — where a self-hosted repo
would require typing a URL with a d-pad before the user sees a single tile. Glyph packs
ship the same way, which closes the last hole in the no-filesystem story.

Self-hosted zips remain for development and beta. Submission requires a
GPL-compatible licence, a code review, and their packaging rules; nothing in this design
conflicts.

## Testing

Automated (`pytest` on Linux CI, no Kodi):

- `layout` — wrap, centre, uppercase including accented, case expansion measured after
  wrapping, RTL reverse, over-long word, block grows and stays centred at every height,
  overflow ellipsises into the final cell of a full-width last row, one line always
  yields exactly one board
- `flap` — stride maths, wrapping drum distance, step-count bounds, op ordering,
  stagger, settled board emits zero ops, character absent from drum treated as blank
- `sources` — JSON/text/comment parsing, malformed input, cache fallback chain, merged
  pool, shuffle exhausts before repeating, `\n` author split, raising source disabled
  and falls back
- `compose` — checkbox state to lines and accents for every combination including
  none-ticked, empty-token line drop, wholly-empty board skip
- `glyphs` — resolution order, codepoint naming, uppercase-closure invariant,
  pack-metrics warning
- `phrases` — **every bundled phrase renders at default geometry without ellipsising**
- `glyphgen` — file count and codepoint naming; no pixel goldens

Manual only (platform-bound, cannot run in CI): window construction, control count,
`setImage` throughput, exit contract. Procedure:

1. Install on a Fire TV Stick 4K. Set Kodi's screensaver timeout below Fire OS's.
2. Confirm the board builds and the first board flaps within 2s of activation.
3. Confirm any remote input dismisses it and returns to the previous window.
4. Confirm a settled board consumes no measurable CPU (`top` over adb).
5. Confirm the clock re-flaps in place on the minute without advancing the board.
6. Install a glyph pack, select it, confirm `resource://` glyphs resolve.
7. Select a pack lacking a character in the phrase list; confirm tofu, not a crash.

## Spike — run before implementation

Roughly one hour. Any outcome moves a constant; none invalidates the structure.

0. **Flap feel** — watch a full-drum wrap (`'9'` -> `'0'`) on a TV and settle
   `MAX_STEPS` against the fixed 200ms step. Not a correctness question; the only one
   here that cannot be answered from a desk.
1. **Exit contract** — which of `onAction`, `System.ScreenSaverActive`, or
   `abortRequested` actually fires for a Python screensaver, and in what order.
2. **Control budget** — 264 controls on a Fire TV Stick 4K: window init time, memory,
   `setImage` throughput at 20fps. Fallback if it bites: fewer rows.
3. **`resource://` resolution** — reading glyph files from an installed
   `kodi.resource.images` pack from addon Python.
4. **`colordiffuse` from Python** — whether `xbmcgui.ControlImage` exposes it as a
   constructor argument or only via skin XML. Determines whether tints are applied at
   creation or need the controls defined in the window XML.

## Notes

- Fire OS runs its own screensaver. Kodi's timeout must be shorter, or Amazon's photo
  screensaver wins. README note, not code.
- `str.upper()` on Turkish dotless-i is wrong. Known, ignored.
