# Split-Flap Board Screensaver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Kodi screensaver that renders a mechanical split-flap (Solari) departure board showing phrases, the time, and the weather.

**Architecture:** A pure-Python core (geometry, layout, drum, flap state machine, sources) with no `xbmc` imports, unit-tested on Linux CI, behind a thin Kodi shell that only creates controls and calls `setImage()`. Each board cell is a tile of two stacked `ControlImage` halves; characters are pre-rendered greyscale PNGs tinted at runtime with `colordiffuse`.

**Tech Stack:** Python 3.8+, Kodi 21+ (`xbmc.python` 3.0.0), pytest, Pillow (build-time only), Nimbus Sans.

**Spec:** `docs/superpowers/specs/2026-08-27-splitflap-screensaver-design.md`

**Glossary:** `CONTEXT.md` — use `board`, `cell`, `tile`, `half`, `glyph`, `drum`, `block`, `hold`, `source` precisely. Never write "screen" for board, or "band" at all.

## Global Constraints

- **Python 3.8 syntax.** Kodi 19 ships 3.8. Use `typing.Optional`, `typing.Tuple`, `typing.List`, `typing.Dict` — never `X | None` or builtin generics.
- **Zero runtime dependencies.** Stdlib only. `urllib.request` for fetching. Pillow is imported only in build tools and behind a guarded `try` at runtime.
- **No `xbmc` import outside the Kodi shell.** `board.py`, `liveinfo.py`, `discovery.py`, `default.py` may import Kodi. Nothing else may, ever — CI has no Kodi.
- **Addon id:** `screensaver.splitflap`. Display name "Split-Flap Board". Glyph packs: `resource.images.splitflap.*`.
- **Extension point:** `<extension point="xbmc.ui.screensaver" library="default.py"/>`.
- **Geometry constants:** `CELL_ASPECT = 0.55` (width/height, portrait), `BOARD_ASPECT = 2.0`, skin space 1920x1080, default `rows = 6`, margin 2% of frame, `gap = 6`.
- **Animation constants:** `STEP_MS = 200` (hardware rate), `MAX_STEPS = 12`, half-step = half a step.
- **Colours:** letter `#E8E8E8`, accent `#2B5CE6`.
- **Glyph filenames by codepoint, never character:** `t_0041.png`, `b_0041.png`. Zero-padded lowercase hex, minimum 4 digits.
- **Capitals only.** `layout` uppercases the whole string before gridding; case expansion (`ß` -> `SS`) yields extra cells.
- **Blank is the space character** `U+0020`, and it is a normal glyph with a normal PNG.
- **Tofu is `U+25A1`**, always bundled, never absent.
- **One source line is always one board.** No pagination anywhere.
- **Commit after every task.** Conventional Commits.

---

### Task 0: Spike — answer the four unknowns on real hardware

Not TDD. This is investigation whose output is a findings document. Every later task's constants depend on it, and three of the four questions cannot be answered without a device.

**Files:**
- Create: `docs/superpowers/spikes/2026-08-27-kodi-findings.md`
- Create: `spike/screensaver.splitflap.spike/addon.xml`
- Create: `spike/screensaver.splitflap.spike/default.py`

- [ ] **Step 1: Write the throwaway spike addon**

`spike/screensaver.splitflap.spike/addon.xml`:

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="screensaver.splitflap.spike" name="SplitFlap Spike" version="0.0.1" provider-name="spike">
  <requires>
    <import addon="xbmc.python" version="3.0.0"/>
  </requires>
  <extension point="xbmc.ui.screensaver" library="default.py"/>
  <extension point="xbmc.addon.metadata">
    <summary lang="en_GB">Throwaway spike</summary>
    <platform>all</platform>
  </extension>
</addon>
```

`spike/screensaver.splitflap.spike/default.py`:

```python
import time
import xbmc
import xbmcgui

N = 264  # the real control budget: 22 cols x 6 rows x 2 halves


class Spike(xbmcgui.WindowXMLDialog):
    def onInit(self):
        t0 = time.time()
        controls = []
        for i in range(N):
            c = xbmcgui.ControlImage(
                (i % 22) * 80, (i // 22) * 40, 78, 38,
                "DefaultAddonNone.png",
            )
            controls.append(c)
        self.addControls(controls)
        xbmc.log("SPIKE addControls %d took %.3fs" % (N, time.time() - t0), xbmc.LOGINFO)

        # setImage throughput
        t1 = time.time()
        for _ in range(20):
            for c in controls[:40]:
                c.setImage("DefaultAddonNone.png")
        xbmc.log("SPIKE 800 setImage took %.3fs" % (time.time() - t1), xbmc.LOGINFO)

        # colorDiffuse from Python?
        try:
            probe = xbmcgui.ControlImage(0, 0, 10, 10, "DefaultAddonNone.png",
                                         colorDiffuse="FF2B5CE6")
            self.addControl(probe)
            xbmc.log("SPIKE colorDiffuse kwarg OK", xbmc.LOGINFO)
        except Exception as exc:
            xbmc.log("SPIKE colorDiffuse kwarg FAILED: %r" % (exc,), xbmc.LOGINFO)

        # resource:// resolution from an installed resource.images pack
        import xbmcvfs
        p = "resource://resource.images.splitflap.probe/t_0041.png"
        xbmc.log("SPIKE resource exists=%s" % xbmcvfs.exists(p), xbmc.LOGINFO)

    def onAction(self, action):
        xbmc.log("SPIKE onAction id=%s" % action.getId(), xbmc.LOGINFO)
        self.close()


w = Spike("DialogBusy.xml", "")
w.doModal()
del w
```

- [ ] **Step 2: Install Kodi on the dev machine**

Three of the five questions do not need the Fire TV, and desktop Kodi gives a fast
crash-fix loop for the whole Kodi shell in Tasks 14-16.

```bash
sudo pacman -S --needed kodi
mkdir -p ~/.kodi/addons
cp -r spike/screensaver.splitflap.spike ~/.kodi/addons/
kodi &
# Settings > Interface > Screensaver > SplitFlap Spike > Preview
grep SPIKE ~/.kodi/temp/kodi.log
```

Answer questions 1, 3 and 4 here. Questions 0 and 2 need real hardware — an A53 core
and a couch — so they wait for Step 3.

- [ ] **Step 3: Install on a Fire TV Stick 4K and run it**

```bash
adb connect <firetv-ip>:5555
adb push spike /sdcard/
# Kodi: Settings > Add-ons > Install from zip / or copy into the addons dir
# Kodi: Settings > Interface > Screensaver > SplitFlap Spike > Preview
adb shell "run-as org.xbmc.kodi cat files/.kodi/temp/kodi.log" | grep SPIKE
```

- [ ] **Step 4: Answer question 0 — flap feel** (Fire TV only)

Watch a full-drum wrap. Record the `MAX_STEPS` value that looks right against the fixed 200ms step. This is a judgement, not a measurement.

- [ ] **Step 5: Answer question 1 — exit contract** (desktop Kodi is enough)

Press a remote key while the spike runs. Record which of `onAction`, `Monitor.abortRequested()`, or `System.ScreenSaverActive` going false fires, and in what order.

- [ ] **Step 6: Answer question 2 — control budget** (Fire TV only — desktop numbers prove nothing about an A53)

Record the logged `addControls` time and `setImage` throughput. Budget: init under 2s, and 40 `setImage` calls comfortably inside 200ms.

- [ ] **Step 7: Answer questions 3 and 4** (desktop Kodi is enough)

Record whether `colorDiffuse` works as a Python kwarg (determines whether tints are applied at creation or need window XML), and whether `resource://` paths resolve from addon Python.

- [ ] **Step 8: Write the findings document**

`docs/superpowers/spikes/2026-08-27-kodi-findings.md` with one section per question, each stating the answer and the constant or design consequence. If the control budget fails, state the reduced default `rows`.

- [ ] **Step 9: Commit**

```bash
git add docs/superpowers/spikes spike
git commit -m "spike: answer Kodi screensaver unknowns on Fire TV"
```

---

### Task 1: Project scaffold and CI

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `tests/test_smoke.py`, `.github/workflows/tests.yml`
- Create: `resources/lib/__init__.py`, `resources/lib/sources/__init__.py`

**Interfaces:**
- Consumes: nothing
- Produces: an importable `resources.lib` package; `pytest` runs from the repo root

- [ ] **Step 1: Write the failing test**

`tests/test_smoke.py`:

```python
def test_package_importable():
    import resources.lib  # noqa: F401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resources'`

- [ ] **Step 3: Create the package and config**

```bash
mkdir -p resources/lib/sources tests .github/workflows
touch resources/__init__.py resources/lib/__init__.py resources/lib/sources/__init__.py
```

`pyproject.toml`:

```toml
[project]
name = "screensaver-splitflap"
version = "0.1.0"
description = "Split-flap board screensaver for Kodi"
requires-python = ">=3.8"
dependencies = []

[project.optional-dependencies]
dev = ["pytest==8.3.4", "Pillow==11.1.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

`.gitignore`:

```
__pycache__/
*.pyc
.pytest_cache/
build/
dist/
*.zip
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 5: Add CI**

`.github/workflows/tests.yml`:

```yaml
name: tests
on: [push, pull_request]
jobs:
  test:
    # ubuntu-22.04, not latest: Python 3.8 is EOL and 24.04 images no longer
    # carry it. 3.8 is Kodi 19's interpreter and is the syntax floor; 3.11 is
    # what Kodi 21 actually ships, so both are tested.
    runs-on: ubuntu-22.04
    strategy:
      matrix:
        python-version: ["3.8", "3.11"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e ".[dev]"
      - run: python -m pytest -v
      - name: no kodi imports in pure modules
        run: |
          ! grep -rn "^import xbmc\|^from xbmc" \
            resources/lib/layout.py resources/lib/flap.py resources/lib/drum.py \
            resources/lib/geometry.py resources/lib/glyphs.py resources/lib/charset.py \
            resources/lib/compose.py resources/lib/rotator.py \
            resources/lib/sources/base.py resources/lib/sources/phrases.py \
            2>/dev/null
```

The grep guard fails the build if a pure module ever imports Kodi. It tolerates missing files (`2>/dev/null`) so it passes before those modules exist.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore tests resources .github
git commit -m "chore: scaffold package, pytest, and CI"
```

---

### Task 2: Bundled charset and the uppercase-closure invariant

**Files:**
- Create: `resources/lib/charset.py`
- Test: `tests/test_charset.py`

**Interfaces:**
- Consumes: nothing
- Produces: `BLANK: str`, `TOFU: str`, `bundled_charset() -> Tuple[str, ...]`

- [ ] **Step 1: Write the failing test**

`tests/test_charset.py`:

```python
from resources.lib.charset import BLANK, TOFU, bundled_charset


def test_blank_and_tofu_are_present():
    cs = set(bundled_charset())
    assert BLANK == " "
    assert TOFU == "□"
    assert BLANK in cs
    assert TOFU in cs


def test_is_capitals_only():
    cs = bundled_charset()
    assert not [c for c in cs if c.islower()]


def test_contains_ascii_digits_and_capitals():
    cs = set(bundled_charset())
    for c in "ABCXYZ0189":
        assert c in cs


def test_contains_degree_and_ellipsis():
    cs = set(bundled_charset())
    assert "°" in cs   # weather renders 17 deg RAIN
    assert "…" in cs   # layout ellipsises with this


def test_uppercase_closure_per_character():
    """Every character of c.upper() must itself be bundled.

    The per-character form matters: comparing c.upper() as a whole would
    wrongly fail the sharp s, whose 'SS' is fine, while missing the real
    gap, micro sign, which uppercases to a single Greek capital Mu.
    """
    cs = set(bundled_charset())
    for c in cs:
        for out in c.upper():
            assert out in cs, "%r uppercases to %r which is not bundled" % (c, out)


def test_no_duplicates():
    cs = bundled_charset()
    assert len(cs) == len(set(cs))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_charset.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resources.lib.charset'`

- [ ] **Step 3: Write the implementation**

`resources/lib/charset.py`:

```python
"""The characters the bundled glyph set covers.

Capitals-only extended ASCII. Defined as an explicit codepoint list rather
than a range minus guesswork, so the uppercase-closure invariant in the
tests can be trusted.
"""
from typing import Tuple

BLANK = " "
TOFU = "□"

# ASCII printable, minus lowercase a-z.
_ASCII = tuple(
    chr(cp) for cp in range(0x20, 0x7F)
    if not (0x61 <= cp <= 0x7A)
)

# Latin-1 Supplement, minus lowercase. Keeps symbols (degree, plus-minus,
# multiplication, division, micro) and the accented capitals.
_LATIN1 = tuple(
    chr(cp) for cp in range(0xA0, 0x100)
    if not chr(cp).islower()
)

# CP1252 typographic extras that appear in real prose.
_TYPOGRAPHIC = (
    "€",  # euro
    "–",  # en dash
    "—",  # em dash
    "‘", "’",  # single quotes
    "“", "”",  # double quotes
    "…",  # ellipsis
    "†", "‡",  # dagger, double dagger
)

# Uppercase target of the micro sign, which is a Greek capital Mu and would
# otherwise tofu. See test_uppercase_closure_per_character.
_CLOSURE = ("Μ",)

_SPECIAL = (TOFU,)


def bundled_charset():
    # type: () -> Tuple[str, ...]
    seen = []
    for group in (_ASCII, _LATIN1, _TYPOGRAPHIC, _CLOSURE, _SPECIAL):
        for ch in group:
            if ch not in seen:
                seen.append(ch)
    return tuple(seen)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_charset.py -v`
Expected: PASS, 6 tests

If `test_uppercase_closure_per_character` fails on a character you did not expect, the fix is to add its uppercase target to `_CLOSURE` or drop the source character — never to weaken the test.

- [ ] **Step 5: Commit**

```bash
git add resources/lib/charset.py tests/test_charset.py
git commit -m "feat: define bundled charset with uppercase-closure invariant"
```

---

### Task 3: Glyph rasteriser and the bundled glyph assets

**Files:**
- Create: `resources/lib/glyphgen.py`, `tools/build_bundled.py`
- Create: `resources/media/glyphs/` (generated PNGs, committed)
- Create: `assets/fonts/NimbusSans-Regular.otf`, `assets/fonts/LICENSE-nimbus.txt`
- Test: `tests/test_glyphgen.py`

**Interfaces:**
- Consumes: `charset.bundled_charset`, `charset.TOFU`
- Produces: `glyph_filename(ch, half) -> str`, `render_glyphs(chars, font_path, out_dir, half_w, half_h) -> List[str]`

- [ ] **Step 1: Write the failing test**

`tests/test_glyphgen.py`:

```python
import os
import pytest

from resources.lib.glyphgen import glyph_filename, render_glyphs

PIL = pytest.importorskip("PIL")
FONT = "assets/fonts/NimbusSans-Regular.otf"


def test_filename_is_zero_padded_codepoint_hex():
    assert glyph_filename("A", "top") == "t_0041.png"
    assert glyph_filename("A", "bottom") == "b_0041.png"
    assert glyph_filename(" ", "top") == "t_0020.png"
    assert glyph_filename("□", "bottom") == "b_25a1.png"


def test_filename_distinguishes_case_insensitively_safe_names():
    """Names must not collide on a case-insensitive filesystem."""
    assert glyph_filename("A", "top").lower() != glyph_filename("a", "top").lower()


def test_render_writes_two_files_per_character(tmp_path):
    written = render_glyphs("AB", FONT, str(tmp_path), 78, 71)
    assert len(written) == 4
    for name in ("t_0041.png", "b_0041.png", "t_0042.png", "b_0042.png"):
        assert os.path.exists(os.path.join(str(tmp_path), name))


def test_rendered_halves_have_requested_size(tmp_path):
    from PIL import Image
    render_glyphs("A", FONT, str(tmp_path), 78, 71)
    with Image.open(os.path.join(str(tmp_path), "t_0041.png")) as im:
        assert im.size == (78, 71)


def test_top_and_bottom_halves_differ(tmp_path):
    from PIL import Image
    render_glyphs("A", FONT, str(tmp_path), 78, 71)
    top = Image.open(os.path.join(str(tmp_path), "t_0041.png")).tobytes()
    bot = Image.open(os.path.join(str(tmp_path), "b_0041.png")).tobytes()
    assert top != bot
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_glyphgen.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resources.lib.glyphgen'`

- [ ] **Step 3: Fetch the font**

```bash
mkdir -p assets/fonts
curl -sSL -o assets/fonts/NimbusSans-Regular.otf \
  https://raw.githubusercontent.com/ArtifexSoftware/urw-base35-fonts/master/fonts/NimbusSans-Regular.otf
curl -sSL -o assets/fonts/LICENSE-nimbus.txt \
  https://raw.githubusercontent.com/ArtifexSoftware/urw-base35-fonts/master/LICENSE
```

Nimbus Sans is AGPLv3 with a font exception. Its licence file ships with the addon. If Kodi review objects, swap to Liberation Sans (OFL) — it is only ever an input to this module, so the change is one regeneration and no code.

- [ ] **Step 4: Write the implementation**

`resources/lib/glyphgen.py`:

```python
"""Rasterise a font into split-flap tile halves.

One rasteriser, three callers: the bundled build, the pack builder, and the
guarded runtime path. Keeping it single-sourced is what stops the three
drifting apart visually.

Cards and their shading are baked into the greyscale image; a colordiffuse
tint is applied by Kodi at runtime.
"""
import os
from typing import Iterable, List

CARD_VALUE = 24        # near-black card, so a tint barely moves it
LETTER_VALUE = 232     # light letterform, so a tint colours it
HINGE_VALUE = 8        # the seam between halves
CORNER_RADIUS = 6


def glyph_filename(ch, half):
    # type: (str, str) -> str
    prefix = "t" if half == "top" else "b"
    return "%s_%04x.png" % (prefix, ord(ch))


def render_glyphs(chars, font_path, out_dir, half_w, half_h):
    # type: (Iterable[str], str, str, int, int) -> List[str]
    """Render each character as a top and a bottom half. Returns filenames."""
    from PIL import Image, ImageDraw, ImageFont

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    full_h = half_h * 2
    # Fit the capital height to about 55% of the full card.
    size = _fit_font_size(font_path, full_h)
    font = ImageFont.truetype(font_path, size)

    written = []
    for ch in chars:
        card = Image.new("L", (half_w, full_h), CARD_VALUE)
        draw = ImageDraw.Draw(card)
        _draw_centred(draw, ch, font, half_w, full_h)
        draw.line([(0, half_h - 1), (half_w, half_h - 1)], fill=HINGE_VALUE, width=2)

        for half, box in (
            ("top", (0, 0, half_w, half_h)),
            ("bottom", (0, half_h, half_w, full_h)),
        ):
            name = glyph_filename(ch, half)
            card.crop(box).convert("L").save(os.path.join(out_dir, name), "PNG")
            written.append(name)
    return written


def _fit_font_size(font_path, full_h):
    # type: (str, int) -> int
    from PIL import ImageFont
    target = int(full_h * 0.55)
    size = target
    for _ in range(24):
        font = ImageFont.truetype(font_path, size)
        box = font.getbbox("H")
        cap = box[3] - box[1]
        if cap == 0:
            break
        if abs(cap - target) <= 1:
            break
        size = max(4, int(size * target / float(cap)))
    return size


def _draw_centred(draw, ch, font, w, h):
    box = draw.textbbox((0, 0), ch, font=font)
    x = (w - (box[2] - box[0])) / 2.0 - box[0]
    y = (h - (box[3] - box[1])) / 2.0 - box[1]
    draw.text((x, y), ch, fill=LETTER_VALUE, font=font)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_glyphgen.py -v`
Expected: PASS, 5 tests

- [ ] **Step 6: Write the bundled build tool and run it**

`tools/build_bundled.py`:

```python
"""Render the bundled glyph set. Run on a desktop; output is committed."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resources.lib.charset import bundled_charset      # noqa: E402
from resources.lib.glyphgen import render_glyphs       # noqa: E402

FONT = "assets/fonts/NimbusSans-Regular.otf"
OUT = "resources/media/glyphs"
# A half at default geometry is ~78x71; render at 2x so 4K stays crisp.
HALF_W, HALF_H = 156, 142

if __name__ == "__main__":
    written = render_glyphs(bundled_charset(), FONT, OUT, HALF_W, HALF_H)
    print("wrote %d files to %s" % (len(written), OUT))
```

```bash
python tools/build_bundled.py
ls resources/media/glyphs | wc -l   # expect ~290
du -sh resources/media/glyphs       # expect ~1M
```

- [ ] **Step 7: Eyeball one glyph before committing 290 files**

```bash
python -c "from PIL import Image; Image.open('resources/media/glyphs/t_0041.png').resize((312,284)).save('/tmp/A_top.png')"
```

Open `/tmp/A_top.png`. The letterform must be light on a near-black card, cut cleanly at the hinge. If it is clipped or off-centre, fix `_fit_font_size` before generating the full set.

- [ ] **Step 8: Commit**

```bash
git add resources/lib/glyphgen.py tools/build_bundled.py tests/test_glyphgen.py \
        assets/fonts resources/media/glyphs
git commit -m "feat: rasterise bundled glyph set from Nimbus Sans"
```

---

### Task 4: Glyph index and resolution order

**Files:**
- Create: `resources/lib/glyphs.py`
- Test: `tests/test_glyphs.py`

**Interfaces:**
- Consumes: `glyphgen.glyph_filename`, `charset.TOFU`
- Produces: `GlyphIndex(search_dirs, exists)` with `.path(ch, half) -> str` and `.charset -> Set[str]`

- [ ] **Step 1: Write the failing test**

`tests/test_glyphs.py`:

```python
from resources.lib.charset import TOFU
from resources.lib.glyphs import GlyphIndex


def fake_fs(*present):
    """present: sequence of (dir, filename) pairs that exist."""
    have = set(present)
    return lambda path: tuple(path.rsplit("/", 1)) in have


def test_first_hit_wins_in_order():
    exists = fake_fs(("cache", "t_0041.png"), ("pack", "t_0041.png"),
                     ("bundled", "t_0041.png"))
    idx = GlyphIndex(["cache", "pack", "bundled"], exists)
    assert idx.path("A", "top") == "cache/t_0041.png"


def test_falls_through_to_pack_then_bundled():
    exists = fake_fs(("pack", "t_0041.png"), ("bundled", "t_0041.png"))
    idx = GlyphIndex(["cache", "pack", "bundled"], exists)
    assert idx.path("A", "top") == "pack/t_0041.png"

    exists = fake_fs(("bundled", "t_0041.png"))
    idx = GlyphIndex(["cache", "pack", "bundled"], exists)
    assert idx.path("A", "top") == "bundled/t_0041.png"


def test_missing_character_resolves_to_tofu():
    exists = fake_fs(("bundled", "t_25a1.png"), ("bundled", "b_25a1.png"))
    idx = GlyphIndex(["bundled"], exists)
    assert idx.path("Ж", "top") == "bundled/t_25a1.png"


def test_tofu_itself_missing_raises_rather_than_looping():
    idx = GlyphIndex(["bundled"], lambda path: False)
    try:
        idx.path("A", "top")
    except LookupError as exc:
        assert TOFU in str(exc) or "tofu" in str(exc).lower()
    else:
        raise AssertionError("expected LookupError")


def test_charset_reports_characters_with_both_halves():
    exists = fake_fs(("bundled", "t_0041.png"), ("bundled", "b_0041.png"),
                     ("bundled", "t_0042.png"))  # B has no bottom half
    idx = GlyphIndex(["bundled"], exists)
    cs = idx.charset("AB")
    assert "A" in cs
    assert "B" not in cs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_glyphs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resources.lib.glyphs'`

- [ ] **Step 3: Write the implementation**

`resources/lib/glyphs.py`:

```python
"""Resolve a character and half to a glyph file.

Order: runtime cache, then the selected pack, then the bundled set, then
tofu. Tofu is bundled like any other glyph, so the fallback can never
itself be missing -- if it is, that is a packaging bug and we say so
loudly rather than recursing.
"""
from typing import Callable, Iterable, List, Set

from .charset import TOFU
from .glyphgen import glyph_filename


class GlyphIndex(object):
    def __init__(self, search_dirs, exists):
        # type: (List[str], Callable[[str], bool]) -> None
        self._dirs = list(search_dirs)
        self._exists = exists

    def _find(self, ch, half):
        name = glyph_filename(ch, half)
        for d in self._dirs:
            path = "%s/%s" % (d, name)
            if self._exists(path):
                return path
        return None

    def path(self, ch, half):
        # type: (str, str) -> str
        found = self._find(ch, half)
        if found is not None:
            return found
        fallback = self._find(TOFU, half)
        if fallback is None:
            raise LookupError(
                "tofu glyph %r is missing from every search dir %r -- "
                "the bundled set is incomplete" % (TOFU, self._dirs)
            )
        return fallback

    def charset(self, candidates):
        # type: (Iterable[str]) -> Set[str]
        """Characters with BOTH halves present, so a tile can render them."""
        out = set()
        for ch in candidates:
            if self._find(ch, "top") and self._find(ch, "bottom"):
                out.add(ch)
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_glyphs.py -v`
Expected: PASS, 5 tests

- [ ] **Step 5: Commit**

```bash
git add resources/lib/glyphs.py tests/test_glyphs.py
git commit -m "feat: glyph index with cache/pack/bundled/tofu resolution"
```

---

### Task 5: Geometry

**Files:**
- Create: `resources/lib/geometry.py`
- Test: `tests/test_geometry.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Geometry` with `rows, cols, tile_w, tile_h, gap, origin_x, origin_y`; `compute(rows, skin_w=1920, skin_h=1080, margin_pct=0.02, gap=6) -> Geometry`; `Geometry.half_rect(row, col, half) -> Tuple[int,int,int,int]`

- [ ] **Step 1: Write the failing test**

`tests/test_geometry.py`:

```python
from resources.lib.geometry import BOARD_ASPECT, CELL_ASPECT, compute


def test_reference_geometry_is_22_by_6():
    """Measured from the reference image by FFT of the tile field."""
    g = compute(rows=6)
    assert g.rows == 6
    assert g.cols == 22


def test_cells_are_portrait():
    g = compute(rows=6)
    assert g.tile_w < g.tile_h
    assert abs(g.tile_w / float(g.tile_h) - CELL_ASPECT) < 0.05


def test_board_fits_the_frame_at_every_row_count():
    for rows in range(2, 16):
        g = compute(rows=rows)
        width = g.cols * g.tile_w + (g.cols - 1) * g.gap
        height = g.rows * g.tile_h + (g.rows - 1) * g.gap
        assert width <= 1920, rows
        assert height <= 1080, rows


def test_board_letterboxes_rather_than_filling_height():
    """BOARD_ASPECT 2.0 exceeds the frame's 1.78, so there is vertical slack."""
    g = compute(rows=6)
    height = g.rows * g.tile_h + (g.rows - 1) * g.gap
    assert height < 1080 * 0.95
    assert BOARD_ASPECT > 1920 / 1080.0


def test_grid_is_centred():
    g = compute(rows=6)
    width = g.cols * g.tile_w + (g.cols - 1) * g.gap
    height = g.rows * g.tile_h + (g.rows - 1) * g.gap
    assert abs(g.origin_x - (1920 - width) / 2) <= 1
    assert abs(g.origin_y - (1080 - height) / 2) <= 1


def test_more_rows_means_more_columns():
    assert compute(rows=3).cols < compute(rows=6).cols < compute(rows=10).cols


def test_half_rects_stack_and_tile():
    g = compute(rows=6)
    top = g.half_rect(0, 0, "top")
    bottom = g.half_rect(0, 0, "bottom")
    assert top[1] + top[3] == bottom[1]
    assert top[3] + bottom[3] == g.tile_h
    assert top[2] == bottom[2] == g.tile_w


def test_adjacent_cells_are_a_pitch_apart():
    g = compute(rows=6)
    a = g.half_rect(0, 0, "top")
    b = g.half_rect(0, 1, "top")
    assert b[0] - a[0] == g.tile_w + g.gap
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_geometry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resources.lib.geometry'`

- [ ] **Step 3: Write the implementation**

`resources/lib/geometry.py`:

```python
"""Board geometry in Kodi's fixed 1920x1080 skin coordinate space.

Rows is the only setting. Columns derive from the tile field's own aspect,
measured from the reference image at 2.0 -- wider than the 16:9 frame, so
the board fills the width and letterboxes vertically, exactly as the
reference does. Deriving columns by filling the HEIGHT instead yields 18
columns at six rows and does not match.
"""
from typing import Tuple

CELL_ASPECT = 0.55    # tile width / tile height. Split-flap cards are portrait.
BOARD_ASPECT = 2.0    # tile field width / height, measured from the reference.
SKIN_W = 1920
SKIN_H = 1080


class Geometry(object):
    def __init__(self, rows, cols, tile_w, tile_h, gap, origin_x, origin_y):
        # type: (int, int, int, int, int, int, int) -> None
        self.rows = rows
        self.cols = cols
        self.tile_w = tile_w
        self.tile_h = tile_h
        self.gap = gap
        self.origin_x = origin_x
        self.origin_y = origin_y

    @property
    def cells(self):
        # type: () -> int
        return self.rows * self.cols

    def half_rect(self, row, col, half):
        # type: (int, int, str) -> Tuple[int, int, int, int]
        """Return (x, y, w, h) for one half of one tile."""
        x = self.origin_x + col * (self.tile_w + self.gap)
        y = self.origin_y + row * (self.tile_h + self.gap)
        top_h = self.tile_h // 2
        if half == "top":
            return (x, y, self.tile_w, top_h)
        return (x, y + top_h, self.tile_w, self.tile_h - top_h)


def compute(rows, skin_w=SKIN_W, skin_h=SKIN_H, margin_pct=0.02, gap=6):
    # type: (int, int, int, float, int) -> Geometry
    if rows < 1:
        raise ValueError("rows must be >= 1, got %r" % (rows,))

    cols = int(round(rows * BOARD_ASPECT / CELL_ASPECT))
    cols = max(1, cols)

    margin_x = int(skin_w * margin_pct)
    tile_w = int((skin_w - 2 * margin_x - (cols - 1) * gap) / cols)
    tile_h = int(tile_w / CELL_ASPECT)

    # BOARD_ASPECT exceeds the frame aspect, so this normally has slack. Clamp
    # anyway: a caller passing an extreme margin must not overflow the frame.
    margin_y = int(skin_h * margin_pct)
    max_tile_h = int((skin_h - 2 * margin_y - (rows - 1) * gap) / rows)
    if tile_h > max_tile_h:
        tile_h = max_tile_h
        tile_w = int(tile_h * CELL_ASPECT)

    width = cols * tile_w + (cols - 1) * gap
    height = rows * tile_h + (rows - 1) * gap
    return Geometry(
        rows=rows, cols=cols, tile_w=tile_w, tile_h=tile_h, gap=gap,
        origin_x=(skin_w - width) // 2,
        origin_y=(skin_h - height) // 2,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_geometry.py -v`
Expected: PASS, 8 tests

- [ ] **Step 5: Commit**

```bash
git add resources/lib/geometry.py tests/test_geometry.py
git commit -m "feat: derive board geometry from rows and measured aspects"
```

---

### Task 6: Layout — one source line becomes one board

**Files:**
- Create: `resources/lib/layout.py`
- Test: `tests/test_layout.py`

**Interfaces:**
- Consumes: `charset.BLANK`
- Produces: `Board` with `.grid: Tuple[str, ...]` and `.accents: FrozenSet[Tuple[int,int]]`; `build(lines, accents, rows, cols, rtl=False) -> Board`; `ELLIPSIS`

- [ ] **Step 1: Write the failing test**

`tests/test_layout.py`:

```python
from resources.lib.layout import ELLIPSIS, build


def grid(lines, rows=6, cols=22, accents=(), rtl=False):
    return build(lines, accents, rows, cols, rtl=rtl).grid


def test_board_is_exactly_rows_by_cols():
    g = grid(["HELLO"])
    assert len(g) == 6
    assert all(len(row) == 22 for row in g)


def test_text_is_uppercased():
    assert "HELLO" in "".join(grid(["hello"]))


def test_short_line_is_centred_horizontally():
    g = grid(["ABCD"], rows=1, cols=10)
    assert g[0] == "   ABCD   "


def test_block_is_centred_vertically_and_grows_to_fit():
    one = grid(["AB"], rows=5, cols=22)
    assert one[2].strip() == "AB"          # single line lands in the middle
    three = grid(["AAA BBB CCC DDD EEE FFF GGG HHH"], rows=5, cols=11)
    filled = [i for i, r in enumerate(three) if r.strip()]
    assert filled == [1, 2, 3]             # three lines, still centred


def test_wraps_on_words():
    g = grid(["THE ONLY WAY OUT IS THROUGH"], rows=6, cols=12)
    text = [r.strip() for r in g if r.strip()]
    assert text == ["THE ONLY", "WAY OUT IS", "THROUGH"]


def test_over_long_word_is_hard_split():
    g = grid(["SUPERCALIFRAGILISTIC"], rows=6, cols=8)
    text = [r.strip() for r in g if r.strip()]
    assert text[0] == "SUPERCAL"


def test_case_expansion_takes_extra_cells():
    """The sharp s uppercases to two characters, so it needs two cells."""
    g = grid(["straße"], rows=1, cols=22)
    assert "STRASSE" in g[0]


def test_case_expansion_is_measured_after_wrapping():
    """Uppercasing must precede wrapping, since it changes line length."""
    g = grid(["aßaßaßa"], rows=3, cols=5)
    for row in g:
        assert len(row) == 5


def test_overflow_ellipsises_into_the_final_cell():
    long = " ".join(["WORD"] * 40)
    g = grid([long], rows=2, cols=10)
    assert g[-1].endswith(ELLIPSIS)
    assert len(g[-1]) == 10
    assert g[-1] != " " * 9 + ELLIPSIS      # last row is filled, not padded


def test_one_line_always_yields_one_board():
    """build returns a Board, never a sequence. There is no pagination."""
    b = build([" ".join(["WORD"] * 200)], (), 6, 22)
    assert isinstance(b.grid, tuple)
    assert len(b.grid) == 6


def test_author_line_is_its_own_line():
    g = grid(["THE ONLY WAY OUT IS THROUGH", "ROBERT FROST"], rows=6, cols=22)
    text = [r.strip() for r in g if r.strip()]
    assert text[-1] == "ROBERT FROST"


def test_rtl_line_is_reversed():
    g = grid(["ABC"], rows=1, cols=5, rtl=True)
    assert g[0].strip() == "CBA"


def test_rtl_ellipsis_goes_to_the_visual_end():
    g = grid([" ".join(["WORD"] * 40)], rows=1, cols=10, rtl=True)
    assert g[0].startswith(ELLIPSIS)


def test_accent_before_line_resolves_to_the_cell_left_of_it():
    b = build(["AB", "CD"], [{"before_line": 1}], 4, 10)
    row = next(i for i, r in enumerate(b.grid) if r.strip() == "CD")
    col = b.grid[row].index("C")
    assert (row, col - 1) in b.accents


def test_accent_corners_resolve_to_grid_corners():
    b = build(["AB"], [{"corner": "top-left"}, {"corner": "top-right"}], 4, 10)
    assert (0, 0) in b.accents
    assert (0, 9) in b.accents


def test_accent_explicit_cell_passes_through():
    b = build(["AB"], [{"cell": [2, 3]}], 4, 10)
    assert (2, 3) in b.accents


def test_accent_outside_the_grid_is_dropped_not_raised():
    b = build(["AB"], [{"cell": [99, 99]}], 4, 10)
    assert b.accents == frozenset()


def test_empty_lines_give_a_blank_board():
    g = grid([])
    assert all(row.strip() == "" for row in g)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_layout.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resources.lib.layout'`

- [ ] **Step 3: Write the implementation**

`resources/lib/layout.py`:

```python
"""Turn one source line into exactly one board.

There is no pagination: a phrase never spills onto a second board just for
being long. The block grows to fit and centres; genuine overflow
ellipsises into the final cell of a full-width last row, where a board
running out of space would put it.
"""
from typing import Any, Dict, FrozenSet, List, Sequence, Tuple

from .charset import BLANK

ELLIPSIS = "…"


class Board(object):
    def __init__(self, grid, accents):
        # type: (Tuple[str, ...], FrozenSet[Tuple[int, int]]) -> None
        self.grid = grid
        self.accents = accents


def build(lines, accents, rows, cols, rtl=False):
    # type: (Sequence[str], Sequence[Dict[str, Any]], int, int, bool) -> Board
    # 1. Uppercase the whole string first. Case expansion changes line
    #    length, so it must happen before wrapping.
    upper = [line.upper() for line in lines]

    # 2-3. Wrap and record where each source line starts among wrapped lines.
    wrapped = []           # type: List[str]
    line_start = []        # type: List[int]
    for line in upper:
        line_start.append(len(wrapped))
        pieces = _wrap(line, cols)
        wrapped.extend(pieces if pieces else [""])

    # 5. Overflow ellipsises rather than paginating.
    truncated = False
    if len(wrapped) > rows:
        remainder = " ".join(wrapped[rows - 1:])
        last = remainder[:cols - 1] + ELLIPSIS
        wrapped = wrapped[:rows - 1] + [last]
        truncated = True

    # 4. Size the block to its line count and centre it vertically.
    top = (rows - len(wrapped)) // 2

    grid = []
    offsets = []           # type: List[int]
    for r in range(rows):
        i = r - top
        if 0 <= i < len(wrapped):
            text = wrapped[i]
            is_filled_last = truncated and i == len(wrapped) - 1
            if rtl:
                text = text[::-1]
            if is_filled_last:
                pad = 0
                row = text.ljust(cols, BLANK)[:cols]
            else:
                pad = (cols - len(text)) // 2
                row = (BLANK * pad + text).ljust(cols, BLANK)[:cols]
            offsets.append(pad)
            grid.append(row)
        else:
            offsets.append(0)
            grid.append(BLANK * cols)

    resolved = _resolve_accents(accents, rows, cols, top, line_start, offsets, wrapped)
    return Board(tuple(grid), frozenset(resolved))


def _wrap(text, cols):
    # type: (str, int) -> List[str]
    out = []          # type: List[str]
    current = ""
    for word in text.split():
        while len(word) > cols:
            if current:
                out.append(current)
                current = ""
            out.append(word[:cols])
            word = word[cols:]
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= cols:
            current = current + " " + word
        else:
            out.append(current)
            current = word
    if current:
        out.append(current)
    return out


def _resolve_accents(accents, rows, cols, top, line_start, offsets, wrapped):
    # type: (...) -> List[Tuple[int, int]]
    out = []
    for spec in accents or ():
        cell = None
        if "cell" in spec:
            cell = (int(spec["cell"][0]), int(spec["cell"][1]))
        elif "corner" in spec:
            corner = spec["corner"]
            cell = {
                "top-left": (0, 0),
                "top-right": (0, cols - 1),
                "bottom-left": (rows - 1, 0),
                "bottom-right": (rows - 1, cols - 1),
            }.get(corner)
        elif "before_line" in spec:
            idx = int(spec["before_line"])
            if 0 <= idx < len(line_start):
                wrapped_idx = line_start[idx]
                if wrapped_idx < len(wrapped):
                    row = top + wrapped_idx
                    if 0 <= row < rows:
                        cell = (row, offsets[row] - 1)
        if cell and 0 <= cell[0] < rows and 0 <= cell[1] < cols:
            out.append(cell)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_layout.py -v`
Expected: PASS, 18 tests

- [ ] **Step 5: Commit**

```bash
git add resources/lib/layout.py tests/test_layout.py
git commit -m "feat: lay out one source line as exactly one board"
```

---

### Task 7: Drum

**Files:**
- Create: `resources/lib/drum.py`
- Test: `tests/test_drum.py`

**Interfaces:**
- Consumes: `charset.BLANK`
- Produces: `MAX_STEPS`; `Drum(charset)` with `.chars: Tuple[str, ...]`, `.distance(cur, target) -> int`, `.sequence(cur, target, max_steps=MAX_STEPS) -> Tuple[str, ...]`

- [ ] **Step 1: Write the failing test**

`tests/test_drum.py`:

```python
import pytest

from resources.lib.charset import BLANK
from resources.lib.drum import MAX_STEPS, Drum


def test_blank_is_first_then_codepoints_ascending():
    d = Drum("CAB ")
    assert d.chars == (BLANK, "A", "B", "C")


def test_adjacent_characters_are_one_step():
    """'1' -> '2' is the common clock case and must be a single flap."""
    d = Drum("0123456789")
    assert d.distance("1", "2") == 1
    assert d.sequence("1", "2") == ("2",)


def test_letters_are_also_one_step_apart():
    d = Drum("ABCDEFGHIJ ")
    assert d.sequence("A", "B") == ("B",)


def test_motion_is_forward_only_and_wraps():
    """A target below the current codepoint wraps the whole drum."""
    d = Drum("0123456789")
    assert d.distance("9", "0") == len(d.chars) - 1
    assert d.distance("0", "9") == 9


def test_wrap_is_clamped_to_max_steps():
    d = Drum("".join(chr(c) for c in range(0x41, 0x41 + 140)))
    seq = d.sequence("Z", "A")
    assert len(seq) <= MAX_STEPS


def test_sequence_always_lands_exactly_on_target():
    d = Drum("".join(chr(c) for c in range(0x41, 0x41 + 60)))
    for target in d.chars:
        assert d.sequence("A", target)[-1] == target


def test_sequence_is_empty_free_for_same_character():
    d = Drum("ABC ")
    assert d.sequence("B", "B") == ()


def test_sequence_moves_forward_through_the_drum():
    d = Drum("".join(chr(c) for c in range(0x41, 0x41 + 40)))
    seq = d.sequence("A", d.chars[-1])
    idx = [d.chars.index(c) for c in seq]
    assert idx == sorted(idx)


def test_unknown_character_is_treated_as_blank():
    """After a mid-session pack change the displayed char may be gone."""
    d = Drum("AB ")
    assert d.distance("Ж", "A") == d.distance(BLANK, "A")


def test_unknown_target_raises():
    d = Drum("AB ")
    with pytest.raises(KeyError):
        d.sequence("A", "Ж")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_drum.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resources.lib.drum'`

- [ ] **Step 3: Write the implementation**

`resources/lib/drum.py`:

```python
"""The ordered, circular sequence a tile cycles through.

Blank first, then codepoints ascending. Motion is forward-only and wraps,
exactly as a physical drum: a target below the current codepoint spins the
whole way round, which is why a clock's minutes digit spins on every
rollover while the tens digit ticks once.

Our drum is longer than any real board's -- Solari modules carried 40 to 64
flaps, extended ASCII gives us ~145 -- so a full wrap is stride-sampled
rather than contiguous. MAX_STEPS is a tuning constant, not a derived one.
"""
from typing import Dict, Iterable, Tuple

from .charset import BLANK

MAX_STEPS = 12


def _ceil_div(a, b):
    # type: (int, int) -> int
    return -(-a // b)


class Drum(object):
    def __init__(self, charset):
        # type: (Iterable[str]) -> None
        rest = sorted(set(charset) - {BLANK})
        self.chars = (BLANK,) + tuple(rest)   # type: Tuple[str, ...]
        self._index = {c: i for i, c in enumerate(self.chars)}  # type: Dict[str, int]

    def _pos(self, ch):
        # type: (str) -> int
        return self._index.get(ch, 0)   # unknown current char reads as blank

    def distance(self, cur, target):
        # type: (str, str) -> int
        n = len(self.chars)
        return (self._index[target] - self._pos(cur)) % n

    def sequence(self, cur, target, max_steps=MAX_STEPS):
        # type: (str, str, int) -> Tuple[str, ...]
        """Characters to display in order, ending exactly on target."""
        if target not in self._index:
            raise KeyError("%r is not in the drum" % (target,))
        dist = self.distance(cur, target)
        if dist == 0:
            return ()
        stride = _ceil_div(dist, max_steps)
        start = self._pos(cur)
        n = len(self.chars)
        steps = _ceil_div(dist, stride)
        out = [self.chars[(start + i * stride) % n] for i in range(1, steps)]
        out.append(target)
        return tuple(out)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_drum.py -v`
Expected: PASS, 10 tests

- [ ] **Step 5: Commit**

```bash
git add resources/lib/drum.py tests/test_drum.py
git commit -m "feat: forward-only drum with stride-sampled sequences"
```

---

### Task 8: Flap state machine

**Files:**
- Create: `resources/lib/flap.py`
- Test: `tests/test_flap.py`

**Interfaces:**
- Consumes: `drum.Drum`, `drum.MAX_STEPS`
- Produces: `STEP_MS`, `COL_DELAY_MS`, `ROW_DELAY_MS`; `PaintOp(cell, half, char)`; `FlapMachine(drum, rows, cols, ...)` with `.retarget(grid)`, `.tick(now_ms) -> List[PaintOp]`, `.settled -> bool`

- [ ] **Step 1: Write the failing test**

`tests/test_flap.py`:

```python
from resources.lib.drum import Drum
from resources.lib.flap import STEP_MS, FlapMachine


def machine(rows=1, cols=3, chars="AB C123"):
    return FlapMachine(Drum(chars), rows=rows, cols=cols,
                       col_delay_ms=0, row_delay_ms=0, jitter_ms=0)


def drain(m, start=0, limit=200):
    """Run the machine to completion, returning every op emitted."""
    ops, t = [], start
    for _ in range(limit):
        ops.extend(m.tick(t))
        if m.settled:
            break
        t += STEP_MS // 2
    return ops


def test_starts_settled_and_emits_nothing():
    m = machine()
    assert m.settled
    assert m.tick(0) == []


def test_settled_board_emits_zero_ops():
    """The whole perf argument rests on this."""
    m = machine()
    m.retarget(("   ",))
    drain(m)
    assert m.settled
    assert m.tick(10 ** 6) == []


def test_single_step_change_emits_two_half_ops():
    m = machine(cols=1, chars="12 ")
    m.retarget(("1",))
    drain(m)
    m.retarget(("2",))
    ops = drain(m)
    assert [(o.half, o.char) for o in ops] == [("top", "2"), ("bottom", "2")]


def test_top_half_leads_the_bottom_half():
    m = machine(cols=1, chars="12 ")
    m.retarget(("1",))
    drain(m)
    m.retarget(("2",))
    ops = drain(m)
    assert ops[0].half == "top"
    assert ops[1].half == "bottom"


def test_a_step_takes_STEP_MS():
    """200ms, the reported real-hardware rate of five flaps per second."""
    assert STEP_MS == 200


def test_unchanged_cells_do_not_move():
    m = machine(cols=3, chars="AB ")
    m.retarget(("AAA",))
    drain(m)
    m.retarget(("ABA",))
    ops = drain(m)
    assert {o.cell for o in ops} == {1}


def test_cell_index_is_row_major():
    m = FlapMachine(Drum("AB "), rows=2, cols=3,
                    col_delay_ms=0, row_delay_ms=0, jitter_ms=0)
    m.retarget(("   ", "  A"))
    ops = drain(m)
    assert {o.cell for o in ops} == {5}


def test_stagger_makes_later_columns_start_later():
    m = FlapMachine(Drum("AB "), rows=1, cols=3,
                    col_delay_ms=100, row_delay_ms=0, jitter_ms=0)
    m.retarget(("AAA",))
    first_tick = m.tick(0)
    assert {o.cell for o in first_tick} == {0}


def test_retarget_mid_flight_redirects_without_restarting_the_board():
    m = machine(cols=1, chars="123 ")
    m.retarget(("3",))
    m.tick(0)
    m.retarget(("1",))
    ops = drain(m, start=STEP_MS)
    assert ops[-1].char == "1"


def test_grid_shape_mismatch_raises():
    m = machine(rows=1, cols=3)
    try:
        m.retarget(("AB",))
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError on wrong-width grid")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_flap.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resources.lib.flap'`

- [ ] **Step 3: Write the implementation**

`resources/lib/flap.py`:

```python
"""Animation state machine. Emits paint ops; never touches Kodi.

A step is one character advance -- one card falling -- rendered as two
half-steps: the top lands, then the bottom. That transient mismatch
between halves IS the hinge effect.

Transitions retarget directly, with no clear-to-blank, so cells whose
character is unchanged never move. A settled board emits zero ops, which
is what keeps the cost confined to the transition.
"""
from typing import List, Optional, Sequence, Tuple

from .drum import MAX_STEPS, Drum

STEP_MS = 200          # real hardware runs at five flaps per second
COL_DELAY_MS = 18      # left-to-right ripple
ROW_DELAY_MS = 40
JITTER_MS = 12


class PaintOp(object):
    __slots__ = ("cell", "half", "char")

    def __init__(self, cell, half, char):
        # type: (int, str, str) -> None
        self.cell = cell
        self.half = half
        self.char = char

    def __repr__(self):
        return "PaintOp(%d, %r, %r)" % (self.cell, self.half, self.char)


class _Cell(object):
    __slots__ = ("char", "seq", "step", "phase", "start_ms")

    def __init__(self, char):
        self.char = char
        self.seq = ()          # type: Tuple[str, ...]
        self.step = 0
        self.phase = 0         # 0 = top pending, 1 = bottom pending
        self.start_ms = 0

    @property
    def busy(self):
        return self.step < len(self.seq)


class FlapMachine(object):
    def __init__(self, drum, rows, cols, max_steps=MAX_STEPS, step_ms=STEP_MS,
                 col_delay_ms=COL_DELAY_MS, row_delay_ms=ROW_DELAY_MS,
                 jitter_ms=JITTER_MS, blank=" "):
        # type: (Drum, int, int, int, int, int, int, int, str) -> None
        self._drum = drum
        self._rows = rows
        self._cols = cols
        self._max_steps = max_steps
        self._step_ms = step_ms
        self._col_delay = col_delay_ms
        self._row_delay = row_delay_ms
        self._jitter = jitter_ms
        self._cells = [_Cell(blank) for _ in range(rows * cols)]

    @property
    def settled(self):
        # type: () -> bool
        return not any(c.busy for c in self._cells)

    def retarget(self, grid):
        # type: (Sequence[str]) -> None
        if len(grid) != self._rows:
            raise ValueError("expected %d rows, got %d" % (self._rows, len(grid)))
        for r, row in enumerate(grid):
            if len(row) != self._cols:
                raise ValueError(
                    "row %d has %d cells, expected %d" % (r, len(row), self._cols)
                )
            for c, target in enumerate(row):
                idx = r * self._cols + c
                cell = self._cells[idx]
                seq = self._drum.sequence(cell.char, target, self._max_steps)
                if not seq:
                    cell.seq = ()
                    cell.step = 0
                    continue
                cell.seq = seq
                cell.step = 0
                cell.phase = 0
                cell.start_ms = (
                    c * self._col_delay
                    + r * self._row_delay
                    + (idx * 7919) % (self._jitter + 1)   # deterministic jitter
                )

    def tick(self, now_ms):
        # type: (int) -> List[PaintOp]
        ops = []   # type: List[PaintOp]
        half_ms = self._step_ms // 2
        for idx, cell in enumerate(self._cells):
            while cell.busy:
                due = cell.start_ms + (cell.step * 2 + cell.phase) * half_ms
                if due > now_ms:
                    break
                char = cell.seq[cell.step]
                if cell.phase == 0:
                    ops.append(PaintOp(idx, "top", char))
                    cell.phase = 1
                else:
                    ops.append(PaintOp(idx, "bottom", char))
                    cell.phase = 0
                    cell.char = char
                    cell.step += 1
            if not cell.busy and cell.seq:
                cell.seq = ()
                cell.step = 0
        return ops

    def current_grid(self):
        # type: () -> Tuple[str, ...]
        return tuple(
            "".join(self._cells[r * self._cols + c].char for c in range(self._cols))
            for r in range(self._rows)
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_flap.py -v`
Expected: PASS, 10 tests

- [ ] **Step 5: Commit**

```bash
git add resources/lib/flap.py tests/test_flap.py
git commit -m "feat: flap state machine emitting half-step paint ops"
```

---

### Task 9: Source protocol and the phrase source

**Files:**
- Create: `resources/lib/sources/base.py`, `resources/lib/sources/phrases.py`
- Test: `tests/test_phrases.py`

**Interfaces:**
- Consumes: nothing
- Produces: `Content(lines, accents, refresh_in)`; `parse_phrases(text) -> List[str]`; `split_author(phrase) -> List[str]`; `PhraseSource(pools, rng)` with `.id`, `.next() -> Content`

- [ ] **Step 1: Write the failing test**

`tests/test_phrases.py`:

```python
import random

from resources.lib.sources.base import Content
from resources.lib.sources.phrases import PhraseSource, parse_phrases, split_author


def test_parse_drops_comments_and_blank_lines():
    text = "# a comment\n\nFIRST\n   \nSECOND\n# trailing\n"
    assert parse_phrases(text) == ["FIRST", "SECOND"]


def test_parse_keeps_hash_inside_a_phrase():
    assert parse_phrases("NUMBER # ONE") == ["NUMBER # ONE"]


def test_split_author_on_literal_backslash_n():
    """A real newline cannot serve: one file line is one phrase."""
    assert split_author("THE ONLY WAY OUT\\nROBERT FROST") == [
        "THE ONLY WAY OUT", "ROBERT FROST"
    ]


def test_split_author_without_author():
    assert split_author("JUST A PHRASE") == ["JUST A PHRASE"]


def test_next_returns_content():
    s = PhraseSource([["ONE"]], random.Random(0))
    c = s.next()
    assert isinstance(c, Content)
    assert c.lines == ("ONE",)


def test_refresh_in_is_none_so_phrases_only_advance_on_hold():
    s = PhraseSource([["ONE"]], random.Random(0))
    assert s.next().refresh_in is None


def test_pools_are_merged():
    s = PhraseSource([["A"], ["B"]], random.Random(0))
    seen = {s.next().lines[0] for _ in range(2)}
    assert seen == {"A", "B"}


def test_shuffle_exhausts_the_pool_before_repeating():
    pool = [str(i) for i in range(10)]
    s = PhraseSource([pool], random.Random(1))
    first = [s.next().lines[0] for _ in range(10)]
    assert sorted(first) == sorted(pool)


def test_reshuffles_after_exhaustion():
    pool = [str(i) for i in range(10)]
    s = PhraseSource([pool], random.Random(1))
    first = [s.next().lines[0] for _ in range(10)]
    second = [s.next().lines[0] for _ in range(10)]
    assert sorted(second) == sorted(pool)
    assert first != second


def test_accents_are_the_two_top_corners():
    s = PhraseSource([["ONE"]], random.Random(0))
    accents = s.next().accents
    assert {"corner": "top-left"} in accents
    assert {"corner": "top-right"} in accents


def test_author_line_gets_an_accent_before_it():
    s = PhraseSource([["PHRASE\\nAUTHOR"]], random.Random(0))
    c = s.next()
    assert c.lines == ("PHRASE", "AUTHOR")
    assert {"before_line": 1} in c.accents


def test_empty_pool_yields_a_blank_board_not_a_crash():
    s = PhraseSource([[]], random.Random(0))
    assert s.next().lines == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_phrases.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resources.lib.sources.base'`

- [ ] **Step 3: Write the implementation**

`resources/lib/sources/base.py`:

```python
"""The contract every source implements, built-in or third-party.

Pull, not push: we ask, the source answers with content and a hint about
when to ask again. No callbacks, and no third-party code inside the render
loop.

One method suffices because identical content produces zero paint ops --
refreshing in place and advancing are indistinguishable at the render
layer. refresh_in is what stops a fast poll racing the phrase list.
"""
from typing import Any, Dict, Optional, Sequence, Tuple


class Content(object):
    __slots__ = ("lines", "accents", "refresh_in")

    def __init__(self, lines=(), accents=(), refresh_in=None):
        # type: (Sequence[str], Sequence[Dict[str, Any]], Optional[float]) -> None
        self.lines = tuple(lines)      # type: Tuple[str, ...]
        self.accents = tuple(accents)
        self.refresh_in = refresh_in

    def __eq__(self, other):
        return (
            isinstance(other, Content)
            and self.lines == other.lines
            and self.accents == other.accents
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return "Content(lines=%r, accents=%r, refresh_in=%r)" % (
            self.lines, self.accents, self.refresh_in
        )


class Source(object):
    """Duck-typed base. Subclasses set id and implement next()."""

    id = "source"

    def next(self):
        # type: () -> Content
        raise NotImplementedError
```

`resources/lib/sources/phrases.py`:

```python
"""Phrases from a file and/or a remote URL, merged into one pool.

The file/URL distinction is plumbing, not content, so they merge -- which
also makes "my curated list plus a remote one" work for free.

Ordering is shuffled without repeat until the pool is exhausted. Plain
random visibly repeats within a few boards and reads as a bug.
"""
import random
from typing import List, Sequence

from .base import Content, Source

AUTHOR_SEP = "\\n"


def parse_phrases(text):
    # type: (str) -> List[str]
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def split_author(phrase):
    # type: (str) -> List[str]
    return [part.strip() for part in phrase.split(AUTHOR_SEP)]


class PhraseSource(Source):
    id = "phrases"

    def __init__(self, pools, rng=None):
        # type: (Sequence[Sequence[str]], random.Random) -> None
        self._pool = [p for pool in pools for p in pool]
        self._rng = rng or random.Random()
        self._order = []       # type: List[int]

    def _advance(self):
        # type: () -> str
        if not self._pool:
            return ""
        if not self._order:
            self._order = list(range(len(self._pool)))
            self._rng.shuffle(self._order)
        return self._pool[self._order.pop()]

    def next(self):
        # type: () -> Content
        phrase = self._advance()
        if not phrase:
            return Content(lines=(), accents=(), refresh_in=None)
        lines = split_author(phrase)
        accents = [{"corner": "top-left"}, {"corner": "top-right"}]
        if len(lines) > 1:
            accents.append({"before_line": len(lines) - 1})
        return Content(lines=lines, accents=accents, refresh_in=None)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_phrases.py -v`
Expected: PASS, 12 tests

- [ ] **Step 5: Commit**

```bash
git add resources/lib/sources/base.py resources/lib/sources/phrases.py tests/test_phrases.py
git commit -m "feat: source protocol and phrase source with merged shuffled pool"
```

---

### Task 10: Remote phrase fetching

**Files:**
- Create: `resources/lib/sources/remote.py`
- Test: `tests/test_remote.py`

**Interfaces:**
- Consumes: `sources.phrases.parse_phrases`
- Produces: `parse_remote(payload) -> List[str]`; `RemoteCache(path_read, path_write)` with `.load(fetch, url) -> List[str]`

- [ ] **Step 1: Write the failing test**

`tests/test_remote.py`:

```python
import pytest

from resources.lib.sources.remote import RemoteCache, parse_remote


def test_parses_plain_text():
    assert parse_remote("ONE\nTWO\n# skip\n") == ["ONE", "TWO"]


def test_parses_json_array():
    assert parse_remote('["ONE", "TWO"]') == ["ONE", "TWO"]


def test_parses_json_object_with_phrases_key():
    assert parse_remote('{"phrases": ["ONE", "TWO"]}') == ["ONE", "TWO"]


def test_json_non_string_entries_are_dropped():
    assert parse_remote('["ONE", 5, null, "TWO"]') == ["ONE", "TWO"]


def test_malformed_json_falls_back_to_plain_text():
    assert parse_remote('["ONE", "TWO"') == ['["ONE", "TWO"']


def test_empty_payload_yields_empty_list():
    assert parse_remote("") == []


def test_successful_fetch_is_written_to_cache():
    written = {}
    cache = RemoteCache(read=lambda: None, write=lambda t: written.setdefault("t", t))
    got = cache.load(lambda url: "ONE\nTWO", "http://example/x")
    assert got == ["ONE", "TWO"]
    assert written["t"] == "ONE\nTWO"


def test_failed_fetch_falls_back_to_cache():
    def boom(url):
        raise IOError("network down")

    cache = RemoteCache(read=lambda: "CACHED", write=lambda t: None)
    assert cache.load(boom, "http://example/x") == ["CACHED"]


def test_failed_fetch_with_no_cache_yields_empty_not_an_exception():
    def boom(url):
        raise IOError("network down")

    cache = RemoteCache(read=lambda: None, write=lambda t: None)
    assert cache.load(boom, "http://example/x") == []


def test_cache_write_failure_does_not_lose_the_fetched_content():
    def bad_write(text):
        raise OSError("read-only fs")

    cache = RemoteCache(read=lambda: None, write=bad_write)
    assert cache.load(lambda url: "ONE", "http://example/x") == ["ONE"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_remote.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resources.lib.sources.remote'`

- [ ] **Step 3: Write the implementation**

`resources/lib/sources/remote.py`:

```python
"""Fetch a phrase list over HTTP, with a disk cache as the fallback.

Parsing is pure and tested; the network call is injected, so nothing here
touches a socket under test. The caller runs load() on a background thread
-- it must never sit on the render loop.
"""
import json
from typing import Callable, List, Optional

from .phrases import parse_phrases

TIMEOUT_S = 10


def parse_remote(payload):
    # type: (str) -> List[str]
    text = (payload or "").strip()
    if not text:
        return []
    if text[0] in "[{":
        try:
            data = json.loads(text)
        except ValueError:
            return parse_phrases(payload)
        if isinstance(data, dict):
            data = data.get("phrases", [])
        if isinstance(data, list):
            return [item.strip() for item in data
                    if isinstance(item, str) and item.strip()]
        return []
    return parse_phrases(payload)


def http_get(url):
    # type: (str) -> str
    """Real fetcher. Injected so tests never open a socket."""
    from urllib.request import urlopen
    handle = urlopen(url, timeout=TIMEOUT_S)
    try:
        return handle.read().decode("utf-8", "replace")
    finally:
        handle.close()


class RemoteCache(object):
    def __init__(self, read, write):
        # type: (Callable[[], Optional[str]], Callable[[str], None]) -> None
        self._read = read
        self._write = write

    def load(self, fetch, url):
        # type: (Callable[[str], str], str) -> List[str]
        try:
            payload = fetch(url)
        except Exception:
            cached = self._read()
            return parse_remote(cached) if cached else []
        try:
            self._write(payload)
        except Exception:
            pass   # a stale cache is not worth losing a good fetch over
        return parse_remote(payload)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_remote.py -v`
Expected: PASS, 10 tests

- [ ] **Step 5: Commit**

```bash
git add resources/lib/sources/remote.py tests/test_remote.py
git commit -m "feat: remote phrase fetching with disk-cache fallback"
```

---

### Task 11: Live info composition

**Files:**
- Create: `resources/lib/compose.py`
- Test: `tests/test_compose.py`

**Interfaces:**
- Consumes: `sources.base.Content`
- Produces: `compose(flags, values, combine) -> List[Content]`; `seconds_to_next_minute(now_seconds) -> float`

- [ ] **Step 1: Write the failing test**

`tests/test_compose.py`:

```python
from resources.lib.compose import compose, seconds_to_next_minute

VALUES = {
    "time": "12:45",
    "date": "MON 27 AUG",
    "weather_location": "SYDNEY",
    "weather_temp": "17°",
    "weather_conditions": "RAIN",
    "np_artist": "MILES DAVIS",
    "np_title": "SO WHAT",
}
ALL_OFF = {"time": False, "date": False, "weather": False, "nowplaying": False}


def flags(**kw):
    out = dict(ALL_OFF)
    out.update(kw)
    return out


def test_time_only():
    boards = compose(flags(time=True), VALUES, combine=True)
    assert len(boards) == 1
    assert boards[0].lines == ("12:45",)


def test_weather_only_is_two_lines():
    boards = compose(flags(weather=True), VALUES, combine=True)
    assert boards[0].lines == ("SYDNEY", "17° RAIN")


def test_time_and_weather_combined_on_one_board():
    boards = compose(flags(time=True, weather=True), VALUES, combine=True)
    assert len(boards) == 1
    assert boards[0].lines == ("12:45", "SYDNEY", "17° RAIN")


def test_time_and_weather_separate_boards():
    boards = compose(flags(time=True, weather=True), VALUES, combine=False)
    assert len(boards) == 2
    assert boards[0].lines == ("12:45",)
    assert boards[1].lines == ("SYDNEY", "17° RAIN")


def test_accent_sits_before_the_time_line():
    boards = compose(flags(time=True), VALUES, combine=True)
    assert {"before_line": 0} in boards[0].accents


def test_accent_sits_before_the_weather_line():
    boards = compose(flags(weather=True), VALUES, combine=True)
    assert {"before_line": 1} in boards[0].accents


def test_empty_value_drops_its_line():
    values = dict(VALUES, weather_location="")
    boards = compose(flags(weather=True), values, combine=True)
    assert boards[0].lines == ("17° RAIN",)


def test_wholly_empty_board_is_skipped():
    """No weather addon configured means the weather board never appears."""
    values = dict(VALUES, weather_location="", weather_temp="",
                  weather_conditions="")
    boards = compose(flags(weather=True), values, combine=False)
    assert boards == []


def test_nothing_ticked_yields_no_boards():
    assert compose(flags(), VALUES, combine=True) == []


def test_nowplaying_lines():
    boards = compose(flags(nowplaying=True), VALUES, combine=True)
    assert boards[0].lines == ("MILES DAVIS", "SO WHAT")


def test_refresh_in_counts_down_to_the_next_minute():
    boards = compose(flags(time=True), VALUES, combine=True)
    assert boards[0].refresh_in is not None
    assert 0 < boards[0].refresh_in <= 60


def test_no_time_shown_means_no_minute_refresh():
    boards = compose(flags(weather=True), VALUES, combine=True)
    assert boards[0].refresh_in is None or boards[0].refresh_in > 60


def test_seconds_to_next_minute():
    assert seconds_to_next_minute(0.0) == 60.0
    assert seconds_to_next_minute(59.0) == 1.0
    assert seconds_to_next_minute(120.5) == 59.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_compose.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resources.lib.compose'`

- [ ] **Step 3: Write the implementation**

`resources/lib/compose.py`:

```python
"""Turn live-info checkbox state plus resolved values into boards.

Pure: the caller resolves Kodi infolabels and hands the strings in.

Empty-token rule: a value resolving empty drops its line, and a board
resolving wholly empty is skipped -- so an unconfigured weather addon
means the weather board never appears, rather than a board of blanks.
"""
from typing import Any, Dict, List

from .sources.base import Content

WEATHER_REFRESH_S = 900.0


def seconds_to_next_minute(now_seconds):
    # type: (float) -> float
    return 60.0 - (now_seconds % 60.0)


def _nonempty(*parts):
    # type: (*str) -> str
    return " ".join(p.strip() for p in parts if p and p.strip())


def _sections(flags, values):
    # type: (Dict[str, bool], Dict[str, str]) -> List[Dict[str, Any]]
    out = []
    if flags.get("time"):
        out.append({"lines": [values.get("time", "")], "ticks": True})
    if flags.get("date"):
        out.append({"lines": [values.get("date", "")], "ticks": False})
    if flags.get("weather"):
        out.append({
            "lines": [
                values.get("weather_location", ""),
                _nonempty(values.get("weather_temp", ""),
                          values.get("weather_conditions", "")),
            ],
            "ticks": False,
        })
    if flags.get("nowplaying"):
        out.append({
            "lines": [values.get("np_artist", ""), values.get("np_title", "")],
            "ticks": False,
        })
    return out


def _to_content(sections, now_seconds):
    # type: (List[Dict[str, Any]], float) -> Content
    lines = []
    accents = []
    ticks = False
    for section in sections:
        kept = [l.strip() for l in section["lines"] if l and l.strip()]
        if not kept:
            continue
        accents.append({"before_line": len(lines) + len(kept) - 1})
        lines.extend(kept)
        ticks = ticks or section["ticks"]
    if not lines:
        return Content()
    refresh = seconds_to_next_minute(now_seconds) if ticks else WEATHER_REFRESH_S
    return Content(lines=lines, accents=accents, refresh_in=refresh)


def compose(flags, values, combine, now_seconds=0.0):
    # type: (Dict[str, bool], Dict[str, str], bool, float) -> List[Content]
    sections = _sections(flags, values)
    if not sections:
        return []
    if combine:
        content = _to_content(sections, now_seconds)
        return [content] if content.lines else []
    out = []
    for section in sections:
        content = _to_content([section], now_seconds)
        if content.lines:
            out.append(content)
    return out
```

Note on the accent rule: the spec places accents immediately left of the *time* line and the *weather* line. `_to_content` anchors one accent per section at the section's last line, which puts it beside `17° RAIN` rather than `SYDNEY`, matching the reference image where the accent sits next to the conditions line. For a single-line section (time) the last line is the only line, so it lands correctly there too.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_compose.py -v`
Expected: PASS, 13 tests

- [ ] **Step 5: Commit**

```bash
git add resources/lib/compose.py tests/test_compose.py
git commit -m "feat: compose live-info boards from checkbox state"
```

---

### Task 12: Bundled phrases and the fit test

**Files:**
- Create: `resources/data/phrases.txt`
- Test: `tests/test_bundled_phrases.py`

**Interfaces:**
- Consumes: `layout.build`, `layout.ELLIPSIS`, `geometry.compute`, `sources.phrases.parse_phrases`, `sources.phrases.split_author`
- Produces: `resources/data/phrases.txt`, the default phrase file path

- [ ] **Step 1: Write the failing test**

`tests/test_bundled_phrases.py`:

```python
import io
import os

from resources.lib.geometry import compute
from resources.lib.layout import ELLIPSIS, build
from resources.lib.charset import bundled_charset
from resources.lib.sources.phrases import parse_phrases, split_author

PATH = "resources/data/phrases.txt"


def load():
    with io.open(PATH, encoding="utf-8") as handle:
        return parse_phrases(handle.read())


def test_file_exists_and_has_enough_phrases():
    phrases = load()
    assert 20 <= len(phrases) <= 40


def test_every_phrase_fits_at_default_geometry():
    """'Guaranteed to fit' is enforced, not hoped for."""
    g = compute(rows=6)
    for phrase in load():
        board = build(split_author(phrase), (), g.rows, g.cols)
        joined = "".join(board.grid)
        assert ELLIPSIS not in joined, "%r ellipsises at %dx%d" % (
            phrase, g.rows, g.cols
        )


def test_every_character_is_in_the_bundled_charset():
    cs = set(bundled_charset())
    for phrase in load():
        for part in split_author(phrase):
            for ch in part.upper():
                assert ch in cs, "%r in %r is not bundled" % (ch, phrase)


def test_phrases_are_unique():
    phrases = load()
    assert len(phrases) == len(set(phrases))


def test_attributed_phrases_use_the_author_separator():
    for phrase in load():
        assert "|" not in phrase        # separator is \n, not a pipe
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bundled_phrases.py -v`
Expected: FAIL with `FileNotFoundError: resources/data/phrases.txt`

- [ ] **Step 3: Write the phrase file**

Selection avoids copyright risk: well-known attributed lines from public-domain-era authors, plus unattributed maxims. Every one must fit 6x22 after uppercasing.

`resources/data/phrases.txt`:

```
# Split-Flap Board - default phrases.
# One phrase per board. Blank lines and lines starting with # are ignored.
# Use \n to put the author on its own line.
# Point the addon at your own file in Settings to replace these.
THE ONLY WAY OUT IS THROUGH\nROBERT FROST
WE SUFFER MORE IN IMAGINATION THAN IN REALITY\nSENECA
IT IS NOT DEATH THAT A MAN SHOULD FEAR\nMARCUS AURELIUS
FALL SEVEN TIMES STAND UP EIGHT\nJAPANESE PROVERB
WHAT WE DO NOW ECHOES IN ETERNITY\nMARCUS AURELIUS
THE IMPEDIMENT TO ACTION ADVANCES ACTION\nMARCUS AURELIUS
LUCK IS WHAT HAPPENS WHEN PREPARATION MEETS OPPORTUNITY\nSENECA
HE WHO HAS A WHY CAN BEAR ALMOST ANY HOW\nNIETZSCHE
THAT WHICH DOES NOT KILL US MAKES US STRONGER\nNIETZSCHE
A JOURNEY OF A THOUSAND MILES BEGINS WITH ONE STEP\nLAO TZU
WHETHER YOU THINK YOU CAN OR CANNOT YOU ARE RIGHT\nHENRY FORD
GENIUS IS ONE PERCENT INSPIRATION\nTHOMAS EDISON
I HAVE NOT FAILED I FOUND TEN THOUSAND WAYS THAT WON'T WORK\nTHOMAS EDISON
THE BEST TIME TO PLANT A TREE WAS TWENTY YEARS AGO
NOTHING IN LIFE IS TO BE FEARED IT IS ONLY TO BE UNDERSTOOD\nMARIE CURIE
IN THE MIDDLE OF DIFFICULTY LIES OPPORTUNITY\nALBERT EINSTEIN
IMAGINATION IS MORE IMPORTANT THAN KNOWLEDGE\nALBERT EINSTEIN
DO WHAT YOU CAN WITH WHAT YOU HAVE WHERE YOU ARE\nTHEODORE ROOSEVELT
FAR BETTER TO DARE MIGHTY THINGS\nTHEODORE ROOSEVELT
IT ALWAYS SEEMS IMPOSSIBLE UNTIL IT IS DONE
THE WOUND IS THE PLACE WHERE THE LIGHT ENTERS YOU\nRUMI
WHAT YOU SEEK IS SEEKING YOU\nRUMI
KNOWING YOURSELF IS THE BEGINNING OF ALL WISDOM\nARISTOTLE
WE ARE WHAT WE REPEATEDLY DO\nARISTOTLE
THE UNEXAMINED LIFE IS NOT WORTH LIVING\nSOCRATES
BE THE CHANGE YOU WISH TO SEE
SIMPLICITY IS THE ULTIMATE SOPHISTICATION\nLEONARDO DA VINCI
ONE DAY OR DAY ONE YOU DECIDE
KEEP GOING
DON'T PANIC
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_bundled_phrases.py -v`
Expected: PASS, 5 tests

If `test_every_phrase_fits_at_default_geometry` fails, shorten the offending phrase — never relax the test. Six rows of 22 caps is 132 cells, and long quotes will not fit.

- [ ] **Step 5: Commit**

```bash
git add resources/data/phrases.txt tests/test_bundled_phrases.py
git commit -m "feat: bundle default phrases with a geometry fit test"
```

---

### Task 13: Rotator — hold timing and source failure policy

**Files:**
- Create: `resources/lib/rotator.py`
- Test: `tests/test_rotator.py`

**Interfaces:**
- Consumes: `sources.base.Content`
- Produces: `Rotator(source, hold_s, fallback=None, log=None)` with `.poll(now_s) -> Optional[Content]`, `.settled(now_s)`, `.failed -> bool`

- [ ] **Step 1: Write the failing test**

`tests/test_rotator.py`:

```python
from resources.lib.rotator import Rotator
from resources.lib.sources.base import Content


class Fake(object):
    id = "fake"

    def __init__(self, contents):
        self.contents = list(contents)
        self.calls = 0

    def next(self):
        self.calls += 1
        return self.contents[(self.calls - 1) % len(self.contents)]


class Boom(object):
    id = "boom"

    def next(self):
        raise RuntimeError("third-party addon exploded")


def test_first_poll_returns_content_immediately():
    r = Rotator(Fake([Content(["A"])]), hold_s=10)
    assert r.poll(0.0).lines == ("A",)


def test_no_further_content_until_hold_expires():
    src = Fake([Content(["A"]), Content(["B"])])
    r = Rotator(src, hold_s=10)
    r.poll(0.0)
    r.settled(1.0)
    assert r.poll(5.0) is None
    assert src.calls == 1


def test_hold_counts_from_when_the_flap_settles():
    """Raising hold must double reading time, not add a variable flap."""
    src = Fake([Content(["A"]), Content(["B"])])
    r = Rotator(src, hold_s=10)
    r.poll(0.0)
    r.settled(3.0)              # flap took three seconds
    assert r.poll(12.0) is None  # would have fired at 10 if counted from poll
    assert r.poll(13.1).lines == ("B",)


def test_refresh_in_fires_before_hold():
    src = Fake([Content(["12:45"], refresh_in=5.0),
                Content(["12:46"], refresh_in=60.0)])
    r = Rotator(src, hold_s=100)
    r.poll(0.0)
    r.settled(0.5)
    assert r.poll(6.0).lines == ("12:46",)


def test_raising_source_is_disabled_and_falls_back():
    fallback = Fake([Content(["FALLBACK"])])
    logged = []
    r = Rotator(Boom(), hold_s=10, fallback=fallback, log=logged.append)
    assert r.poll(0.0).lines == ("FALLBACK",)
    assert r.failed
    assert logged and "boom" in logged[0].lower()


def test_disabled_source_is_not_retried_within_the_session():
    class CountingBoom(object):
        id = "boom"
        calls = 0

        def next(self):
            CountingBoom.calls += 1
            raise RuntimeError("nope")

    src = CountingBoom()
    r = Rotator(src, hold_s=1, fallback=Fake([Content(["F"])]))
    r.poll(0.0)
    r.settled(0.1)
    r.poll(5.0)
    assert CountingBoom.calls == 1


def test_raising_source_with_no_fallback_yields_empty_content():
    r = Rotator(Boom(), hold_s=10, fallback=None)
    assert r.poll(0.0).lines == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rotator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resources.lib.rotator'`

- [ ] **Step 3: Write the implementation**

`resources/lib/rotator.py`:

```python
"""Advance the active source and own display timing.

Exactly one source is active; there is no cross-source rotation. The
source owns data freshness via refresh_in, we own presentation via hold,
so a source can never override a user's display setting.

Hold counts from when the flap SETTLES, so raising it doubles reading
time rather than adding a variable flap on top.

A source that raises is disabled for the session and we fall back. A
source that HANGS freezes the screensaver -- accepted, since the built-in
sources cannot hang; revisit when contributor discovery ships.
"""
from typing import Callable, Optional

from .sources.base import Content


class Rotator(object):
    def __init__(self, source, hold_s, fallback=None, log=None):
        # type: (object, float, object, Callable[[str], None]) -> None
        self._source = source
        self._hold = float(hold_s)
        self._fallback = fallback
        self._log = log or (lambda msg: None)
        self._current = None      # type: Optional[Content]
        self._settled_at = None   # type: Optional[float]
        self._polled_at = None    # type: Optional[float]
        self.failed = False

    def _call(self, now_s):
        # type: (float) -> Content
        if not self.failed:
            try:
                return self._source.next()
            except Exception as exc:
                self.failed = True
                self._log(
                    "source %r raised %r -- disabled for this session, "
                    "falling back" % (getattr(self._source, "id", "?"), exc)
                )
        if self._fallback is not None:
            try:
                return self._fallback.next()
            except Exception as exc:
                self._log("fallback source also raised %r" % (exc,))
        return Content()

    def settled(self, now_s):
        # type: (float) -> None
        """Tell the rotator the flap finished. Starts the hold clock."""
        self._settled_at = now_s

    def poll(self, now_s):
        # type: (float) -> Optional[Content]
        if self._current is None:
            self._current = self._call(now_s)
            self._polled_at = now_s
            self._settled_at = None
            return self._current

        refresh = self._current.refresh_in
        refresh_due = (
            refresh is not None
            and self._polled_at is not None
            and now_s - self._polled_at >= refresh
        )
        hold_due = (
            self._settled_at is not None
            and now_s - self._settled_at >= self._hold
        )
        if not (refresh_due or hold_due):
            return None

        self._current = self._call(now_s)
        self._polled_at = now_s
        self._settled_at = None
        return self._current
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rotator.py -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Commit**

```bash
git add resources/lib/rotator.py tests/test_rotator.py
git commit -m "feat: rotator with settle-anchored hold and source failure policy"
```

---

### Task 14: Kodi shell — the board renderer

**Files:**
- Create: `resources/lib/board.py`

Not unit-testable: it constructs Kodi controls. Verified by the manual checklist in Task 17. Keep it thin — everything decidable belongs in the pure modules it calls.

**Interfaces:**
- Consumes: `geometry.Geometry`, `glyphs.GlyphIndex`, `flap.PaintOp`
- Produces: `BoardView(window, geometry, index, letter_colour, accent_colour)` with `.build()`, `.paint(ops)`, `.set_accents(cells)`

- [ ] **Step 1: Write the implementation**

`resources/lib/board.py`:

```python
"""Create the tile controls and paint ops onto them. The only renderer.

Every cell is a tile of two ControlImage halves -- there is no background
layer, because a blank tile is just another glyph. Colour comes from
colorDiffuse over greyscale glyphs.

If the Task 0 spike found colorDiffuse unavailable as a Python kwarg, set
COLOR_DIFFUSE_KWARG to False and the tints move to setColorDiffuse calls.
"""
from typing import Dict, Iterable, List, Tuple

import xbmc
import xbmcgui

from .charset import BLANK
from .flap import PaintOp
from .geometry import Geometry
from .glyphs import GlyphIndex

COLOR_DIFFUSE_KWARG = True


def _argb(hex_rgb):
    # type: (str) -> str
    return "FF" + hex_rgb.lstrip("#").upper()


class BoardView(object):
    def __init__(self, window, geometry, index, letter_colour, accent_colour):
        # type: (xbmcgui.Window, Geometry, GlyphIndex, str, str) -> None
        self._window = window
        self._geo = geometry
        self._index = index
        self._letter = _argb(letter_colour)
        self._accent = _argb(accent_colour)
        self._halves = {}     # type: Dict[Tuple[int, str], xbmcgui.ControlImage]
        self._accent_cells = frozenset()

    def build(self):
        # type: () -> None
        blank_top = self._index.path(BLANK, "top")
        blank_bottom = self._index.path(BLANK, "bottom")
        controls = []   # type: List[xbmcgui.ControlImage]
        for row in range(self._geo.rows):
            for col in range(self._geo.cols):
                cell = row * self._geo.cols + col
                for half, texture in (("top", blank_top), ("bottom", blank_bottom)):
                    x, y, w, h = self._geo.half_rect(row, col, half)
                    control = self._make(x, y, w, h, texture, self._letter)
                    self._halves[(cell, half)] = control
                    controls.append(control)
        self._window.addControls(controls)
        xbmc.log("splitflap: built %d controls" % len(controls), xbmc.LOGDEBUG)

    def _make(self, x, y, w, h, texture, colour):
        if COLOR_DIFFUSE_KWARG:
            return xbmcgui.ControlImage(x, y, w, h, texture, colorDiffuse=colour)
        control = xbmcgui.ControlImage(x, y, w, h, texture)
        control.setColorDiffuse(colour)
        return control

    def set_accents(self, cells):
        # type: (Iterable[Tuple[int, int]]) -> None
        """Recolour accent tiles. Called once per board, not per frame."""
        wanted = frozenset(r * self._geo.cols + c for r, c in cells)
        for cell in self._accent_cells - wanted:
            self._recolour(cell, self._letter)
        for cell in wanted - self._accent_cells:
            self._recolour(cell, self._accent)
        self._accent_cells = wanted

    def _recolour(self, cell, colour):
        for half in ("top", "bottom"):
            control = self._halves.get((cell, half))
            if control is not None:
                control.setColorDiffuse(colour)

    def paint(self, ops):
        # type: (Iterable[PaintOp]) -> None
        for op in ops:
            control = self._halves.get((op.cell, op.half))
            if control is None:
                continue
            control.setImage(self._index.path(op.char, op.half), useCache=True)
```

- [ ] **Step 2: Sanity-check it imports without Kodi present**

Run: `python -c "import ast; ast.parse(open('resources/lib/board.py').read())"`
Expected: no output. It cannot be imported on CI — only parsed — because `xbmc` does not exist there.

- [ ] **Step 3: Verify CI's pure-module guard still passes**

Run: `python -m pytest -v`
Expected: PASS. `board.py` is not in the guarded list, and nothing pure imports it.

- [ ] **Step 4: Commit**

```bash
git add resources/lib/board.py
git commit -m "feat: Kodi board renderer over two-half tile controls"
```

---

### Task 15: Kodi shell — live info source

**Files:**
- Create: `resources/lib/sources/liveinfo.py`

**Interfaces:**
- Consumes: `compose.compose`, `sources.base.Content`, `sources.base.Source`
- Produces: `read_values() -> Dict[str, str]`; `LiveInfoSource(flags, combine, reader=None, clock=None)` with `.id`, `.next()`

- [ ] **Step 1: Write the implementation**

`resources/lib/sources/liveinfo.py`:

```python
"""Kodi infolabels as a source. The only Kodi-touching source.

Values come from Kodi's own weather service, so this addon needs no API
keys, no HTTP, and no secrets. Composition is pure and lives in
compose.py; this file only reads labels.
"""
import time
from typing import Callable, Dict, List, Optional

import xbmc

from ..compose import compose
from .base import Content, Source

LABELS = {
    "time": "System.Time",
    "date": "System.Date",
    "weather_location": "Weather.Location",
    "weather_temp": "Weather.Temperature",
    "weather_conditions": "Weather.Conditions",
    "np_artist": "MusicPlayer.Artist",
    "np_title": "MusicPlayer.Title",
}


def read_values():
    # type: () -> Dict[str, str]
    return {key: xbmc.getInfoLabel(label) or "" for key, label in LABELS.items()}


class LiveInfoSource(Source):
    id = "liveinfo"

    def __init__(self, flags, combine, reader=None, clock=None):
        # type: (Dict[str, bool], bool, Optional[Callable], Optional[Callable]) -> None
        self._flags = flags
        self._combine = combine
        self._reader = reader or read_values
        self._clock = clock or time.time
        self._queue = []    # type: List[Content]

    def next(self):
        # type: () -> Content
        if not self._queue:
            self._queue = compose(
                self._flags, self._reader(), self._combine, self._clock()
            )
        if not self._queue:
            return Content()
        return self._queue.pop(0)
```

Note: in combine mode `compose` returns a single board, so the queue refills on every call and the clock re-reads each time — which is what makes a displayed clock re-flap in place. In separate-boards mode the queue drains across successive calls before re-reading.

- [ ] **Step 2: Sanity-check syntax**

Run: `python -c "import ast; ast.parse(open('resources/lib/sources/liveinfo.py').read())"`
Expected: no output

- [ ] **Step 3: Commit**

```bash
git add resources/lib/sources/liveinfo.py
git commit -m "feat: live info source reading Kodi infolabels"
```

---

### Task 16: Kodi shell — addon manifest, settings, and entry point

**Files:**
- Create: `addon.xml`, `resources/settings.xml`, `resources/language/resource.language.en_gb/strings.po`
- Create: `default.py`, `resources/lib/config.py`
- Create: `resources/skins/default/1080i/script-splitflap.xml`
- Create: `icon.png`, `fanart.jpg`

**Interfaces:**
- Consumes: everything above
- Produces: a runnable addon

- [ ] **Step 1: Write the addon manifest**

`addon.xml`:

```xml
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="screensaver.splitflap" name="Split-Flap Board" version="0.1.0" provider-name="finkel">
  <requires>
    <import addon="xbmc.python" version="3.0.0"/>
  </requires>
  <extension point="xbmc.ui.screensaver" library="default.py"/>
  <extension point="xbmc.addon.metadata">
    <summary lang="en_GB">A mechanical split-flap departure board</summary>
    <description lang="en_GB">Renders a Solari-style split-flap board showing phrases, the time, and the weather. Characters flap through the drum exactly as the hardware does.</description>
    <license>GPL-2.0-or-later</license>
    <platform>all</platform>
    <assets>
      <icon>icon.png</icon>
      <fanart>fanart.jpg</fanart>
    </assets>
  </extension>
</addon>
```

- [ ] **Step 2: Write the settings**

`resources/settings.xml` (Kodi 21 format):

```xml
<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<settings version="1">
  <section id="screensaver.splitflap">
    <category id="board" label="30001">
      <group id="1">
        <setting id="rows" type="integer" label="30010">
          <level>0</level>
          <default>6</default>
          <constraints><minimum>2</minimum><step>1</step><maximum>14</maximum></constraints>
          <control type="slider" format="integer"/>
        </setting>
        <setting id="hold_seconds" type="integer" label="30011">
          <level>0</level>
          <default>15</default>
          <constraints><minimum>3</minimum><step>1</step><maximum>120</maximum></constraints>
          <control type="slider" format="integer"/>
        </setting>
        <setting id="max_steps" type="integer" label="30012">
          <level>1</level>
          <default>12</default>
          <constraints><minimum>1</minimum><step>1</step><maximum>40</maximum></constraints>
          <control type="slider" format="integer"/>
        </setting>
        <setting id="letter_colour" type="string" label="30013">
          <level>1</level><default>E8E8E8</default><control type="edit" format="string"/>
        </setting>
        <setting id="accent_colour" type="string" label="30014">
          <level>1</level><default>2B5CE6</default><control type="edit" format="string"/>
        </setting>
      </group>
    </category>
    <category id="content" label="30002">
      <group id="1">
        <setting id="source" type="string" label="30020">
          <level>0</level>
          <default>liveinfo</default>
          <constraints>
            <options>
              <option label="30021">liveinfo</option>
              <option label="30022">phrases</option>
            </options>
          </constraints>
          <control type="spinner" format="string"/>
        </setting>
        <setting id="info_time" type="boolean" label="30030">
          <level>0</level><default>true</default><control type="toggle"/>
        </setting>
        <setting id="info_date" type="boolean" label="30031">
          <level>0</level><default>true</default><control type="toggle"/>
        </setting>
        <setting id="info_weather" type="boolean" label="30032">
          <level>0</level><default>true</default><control type="toggle"/>
        </setting>
        <setting id="info_nowplaying" type="boolean" label="30033">
          <level>0</level><default>false</default><control type="toggle"/>
        </setting>
        <setting id="info_combine" type="boolean" label="30034">
          <level>0</level><default>true</default><control type="toggle"/>
        </setting>
        <setting id="phrases_file" type="path" label="30040">
          <level>0</level><default></default>
          <constraints><writable>false</writable></constraints>
          <control type="button" format="file"/>
        </setting>
        <setting id="phrases_url" type="string" label="30041">
          <level>1</level><default></default><control type="edit" format="string"/>
        </setting>
        <setting id="phrases_refresh_mins" type="integer" label="30042">
          <level>1</level><default>60</default>
          <constraints><minimum>5</minimum><step>5</step><maximum>1440</maximum></constraints>
          <control type="slider" format="integer"/>
        </setting>
      </group>
    </category>
    <category id="glyphs" label="30003">
      <group id="1">
        <setting id="glyph_pack" type="string" label="30050">
          <level>0</level><default></default><control type="edit" format="string"/>
        </setting>
      </group>
    </category>
  </section>
</settings>
```

- [ ] **Step 3: Write the strings**

`resources/language/resource.language.en_gb/strings.po`:

```po
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\n"
"Language: en_GB\n"

msgctxt "#30001"
msgid "Board"
msgstr ""

msgctxt "#30002"
msgid "Content"
msgstr ""

msgctxt "#30003"
msgid "Glyphs"
msgstr ""

msgctxt "#30010"
msgid "Rows (columns are derived)"
msgstr ""

msgctxt "#30011"
msgid "Seconds per board"
msgstr ""

msgctxt "#30012"
msgid "Maximum flap steps"
msgstr ""

msgctxt "#30013"
msgid "Letter colour (RRGGBB)"
msgstr ""

msgctxt "#30014"
msgid "Accent colour (RRGGBB)"
msgstr ""

msgctxt "#30020"
msgid "Show"
msgstr ""

msgctxt "#30021"
msgid "Live info"
msgstr ""

msgctxt "#30022"
msgid "Phrases"
msgstr ""

msgctxt "#30030"
msgid "Time"
msgstr ""

msgctxt "#30031"
msgid "Date"
msgstr ""

msgctxt "#30032"
msgid "Weather"
msgstr ""

msgctxt "#30033"
msgid "Now playing"
msgstr ""

msgctxt "#30034"
msgid "Combine onto one board"
msgstr ""

msgctxt "#30040"
msgid "Phrase file"
msgstr ""

msgctxt "#30041"
msgid "Phrase URL"
msgstr ""

msgctxt "#30042"
msgid "Refresh phrases every (minutes)"
msgstr ""

msgctxt "#30050"
msgid "Glyph pack add-on id (blank for bundled)"
msgstr ""
```

- [ ] **Step 4: Write the settings reader**

`resources/lib/config.py`:

```python
"""Read settings once per activation.

Settings cannot be edited while the screensaver runs, so nothing needs to
handle a live change -- we read at activation and rebuild geometry then.
"""
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()


def _path(special):
    return xbmcvfs.translatePath(special)


def read():
    get = ADDON.getSetting
    get_bool = ADDON.getSettingBool
    get_int = ADDON.getSettingInt
    addon_path = _path(ADDON.getAddonInfo("path"))
    profile = _path(ADDON.getAddonInfo("profile"))
    phrases_file = get("phrases_file") or (addon_path + "/resources/data/phrases.txt")
    return {
        "rows": get_int("rows"),
        "hold_seconds": get_int("hold_seconds"),
        "max_steps": get_int("max_steps"),
        "letter_colour": get("letter_colour") or "E8E8E8",
        "accent_colour": get("accent_colour") or "2B5CE6",
        "source": get("source") or "liveinfo",
        "info_flags": {
            "time": get_bool("info_time"),
            "date": get_bool("info_date"),
            "weather": get_bool("info_weather"),
            "nowplaying": get_bool("info_nowplaying"),
        },
        "info_combine": get_bool("info_combine"),
        "phrases_file": phrases_file,
        "phrases_url": get("phrases_url"),
        "glyph_pack": get("glyph_pack"),
        "addon_path": addon_path,
        "profile": profile,
    }
```

- [ ] **Step 5: Write the window skin file**

`resources/skins/default/1080i/script-splitflap.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<window type="dialog">
  <defaultcontrol>-1</defaultcontrol>
  <animation effect="fade" time="400">WindowOpen</animation>
  <animation effect="fade" time="400">WindowClose</animation>
  <controls>
    <control type="image" id="1">
      <posx>0</posx><posy>0</posy><width>1920</width><height>1080</height>
      <texture>black.png</texture>
      <colordiffuse>FF000000</colordiffuse>
    </control>
  </controls>
</window>
```

Tiles are added from Python at runtime; this file only supplies the black ground behind them.

- [ ] **Step 6: Write the entry point**

`default.py`:

```python
"""Split-Flap Board screensaver entry point."""
import io
import os
import random
import sys
import threading
import time

import xbmc
import xbmcgui
import xbmcvfs

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "resources", "lib"))

from resources.lib import config                                    # noqa: E402
from resources.lib.board import BoardView                           # noqa: E402
from resources.lib.charset import bundled_charset                   # noqa: E402
from resources.lib.drum import Drum                                 # noqa: E402
from resources.lib.flap import FlapMachine                          # noqa: E402
from resources.lib.geometry import compute                          # noqa: E402
from resources.lib.glyphs import GlyphIndex                         # noqa: E402
from resources.lib.layout import build as build_board               # noqa: E402
from resources.lib.rotator import Rotator                           # noqa: E402
from resources.lib.sources.liveinfo import LiveInfoSource           # noqa: E402
from resources.lib.sources.phrases import PhraseSource, parse_phrases  # noqa: E402
from resources.lib.sources.remote import RemoteCache, http_get, parse_remote  # noqa: E402

FRAME_MS = 50


def log(msg):
    xbmc.log("splitflap: %s" % (msg,), xbmc.LOGINFO)


def _read_text(path):
    if not xbmcvfs.exists(path):
        return ""
    with io.open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def _glyph_dirs(cfg):
    dirs = [os.path.join(cfg["profile"], "glyphs")]
    if cfg["glyph_pack"]:
        dirs.append("resource://%s" % cfg["glyph_pack"])
    dirs.append(os.path.join(cfg["addon_path"], "resources", "media", "glyphs"))
    return dirs


def _build_source(cfg):
    if cfg["source"] == "phrases":
        pools = [parse_phrases(_read_text(cfg["phrases_file"]))]
        if cfg["phrases_url"]:
            cache_path = os.path.join(cfg["profile"], "remote.txt")
            cache = RemoteCache(
                read=lambda: _read_text(cache_path) or None,
                write=lambda text: io.open(
                    cache_path, "w", encoding="utf-8").write(text),
            )
            pools.append(cache.load(http_get, cfg["phrases_url"]))
        return PhraseSource(pools, random.Random())
    return LiveInfoSource(cfg["info_flags"], cfg["info_combine"])


class Screensaver(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        self._stop = False
        self._cfg = config.read()

    def onInit(self):
        cfg = self._cfg
        geo = compute(rows=cfg["rows"])
        index = GlyphIndex(_glyph_dirs(cfg), xbmcvfs.exists)
        available = index.charset(bundled_charset())
        drum = Drum(available)

        self._geo = geo
        self._view = BoardView(self, geo, index,
                               cfg["letter_colour"], cfg["accent_colour"])
        self._view.build()
        self._flap = FlapMachine(drum, geo.rows, geo.cols,
                                 max_steps=cfg["max_steps"])
        self._rotator = Rotator(
            _build_source(cfg), cfg["hold_seconds"],
            fallback=LiveInfoSource(cfg["info_flags"], cfg["info_combine"]),
            log=log,
        )
        threading.Thread(target=self._run).start()

    def _run(self):
        monitor = xbmc.Monitor()
        was_settled = True
        while not self._stop and not monitor.abortRequested():
            if not xbmc.getCondVisibility("System.ScreenSaverActive"):
                break
            now = time.time()
            content = self._rotator.poll(now)
            if content is not None:
                board = build_board(content.lines, content.accents,
                                    self._geo.rows, self._geo.cols)
                self._view.set_accents(board.accents)
                self._flap.retarget(board.grid)
                was_settled = False
            ops = self._flap.tick(int(now * 1000))
            if ops:
                self._view.paint(ops)
            if self._flap.settled and not was_settled:
                self._rotator.settled(now)
                was_settled = True
            if monitor.waitForAbort(FRAME_MS / 1000.0):
                break
        self.close()

    def onAction(self, action):
        self._stop = True
        self.close()


if __name__ == "__main__":
    window = Screensaver("script-splitflap.xml",
                         xbmcvfs.translatePath(
                             config.ADDON.getAddonInfo("path")),
                         "default", "1080i")
    window.doModal()
    del window
```

- [ ] **Step 7: Create the artwork**

Kodi requires an icon (512x512 PNG) and fanart (1280x720 JPG) for repository submission. Render them from the real glyphs so they match the product:

```bash
python - <<'EOF'
from PIL import Image
tiles = ["t_0053.png", "t_0046.png"]   # S, F
icon = Image.new("RGB", (512, 512), (10, 10, 10))
for i, name in enumerate(tiles):
    g = Image.open("resources/media/glyphs/%s" % name).convert("RGB")
    g = g.resize((200, 180))
    icon.paste(g, (56 + i * 200, 166))
icon.save("icon.png")
Image.new("RGB", (1280, 720), (10, 10, 10)).save("fanart.jpg", quality=90)
EOF
```

- [ ] **Step 8: Install and run on the Fire TV**

```bash
zip -r screensaver.splitflap.zip addon.xml default.py icon.png fanart.jpg resources -x '*.pyc'
adb connect <firetv-ip>:5555
adb push screensaver.splitflap.zip /sdcard/
# Kodi: Settings > Add-ons > Install from zip file > /sdcard/
# Kodi: Settings > Interface > Screensaver > Split-Flap Board > Preview
adb shell "run-as org.xbmc.kodi cat files/.kodi/temp/kodi.log" | grep splitflap
```

Expected: a board of blank tiles builds, then the time, date and weather flap in.

- [ ] **Step 9: Commit**

```bash
git add addon.xml default.py icon.png fanart.jpg resources/settings.xml \
        resources/language resources/skins resources/lib/config.py
git commit -m "feat: addon manifest, settings, and screensaver entry point"
```

---

### Task 17: Manual verification on hardware

**Files:**
- Create: `docs/superpowers/spikes/2026-08-27-manual-verification.md`

The Kodi shell has no automated coverage by design. This task is its test cycle, and a reviewer can reject on it.

- [ ] **Step 1: Run every check and record the result**

For each, write PASS/FAIL plus the observation into the findings file:

1. Board builds and the first board flaps within 2s of activation.
2. Any remote input dismisses it and returns to the previous window.
3. A settled board consumes no measurable CPU — `adb shell top -m 5` shows Kodi idle.
4. The clock re-flaps in place on the minute **without** advancing to a different board.
5. `1` -> `2` on the clock takes one flap; `9` -> `0` spins the drum.
6. Accents render in the accent colour, everything else in the letter colour.
7. Set `rows` to 3 and to 10; confirm columns rescale and the board stays centred.
8. Switch to Phrases; confirm bundled phrases appear, none ellipsised.
9. Select a glyph pack, confirm `resource://` glyphs resolve.
10. Point the glyph pack at a missing addon id; confirm tofu, not a crash.

- [ ] **Step 2: Commit the results**

```bash
git add docs/superpowers/spikes/2026-08-27-manual-verification.md
git commit -m "test: record manual hardware verification results"
```

---

### Task 18: Glyph pack builder

**Files:**
- Create: `tools/make_glyph_pack.py`
- Test: `tests/test_make_glyph_pack.py`

**Interfaces:**
- Consumes: `glyphgen.render_glyphs`, `charset.bundled_charset`
- Produces: `charset_for(names) -> str`; `build_pack(font, chars, addon_id, name, out_zip, half_w, half_h) -> str`

- [ ] **Step 1: Write the failing test**

`tests/test_make_glyph_pack.py`:

```python
import zipfile

import pytest

from tools.make_glyph_pack import build_pack, charset_for

PIL = pytest.importorskip("PIL")
FONT = "assets/fonts/NimbusSans-Regular.otf"


def test_named_charsets_resolve():
    assert "A" in charset_for(["ascii"])
    assert "А" in charset_for(["cyrillic"])
    assert "Α" in charset_for(["greek"])


def test_unknown_charset_name_raises():
    with pytest.raises(ValueError):
        charset_for(["klingon"])


def test_pack_zip_contains_addon_xml_and_glyphs(tmp_path):
    out = str(tmp_path / "pack.zip")
    build_pack(FONT, "AB", "resource.images.splitflap.test", "Test Pack",
               out, 40, 36)
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
    assert "resource.images.splitflap.test/addon.xml" in names
    assert "resource.images.splitflap.test/t_0041.png" in names
    assert "resource.images.splitflap.test/pack.json" in names


def test_addon_xml_declares_the_resource_images_type(tmp_path):
    out = str(tmp_path / "pack.zip")
    build_pack(FONT, "A", "resource.images.splitflap.test", "Test Pack",
               out, 40, 36)
    with zipfile.ZipFile(out) as zf:
        xml = zf.read("resource.images.splitflap.test/addon.xml").decode("utf-8")
    assert "kodi.resource.images" in xml


def test_pack_json_records_metrics(tmp_path):
    import json
    out = str(tmp_path / "pack.zip")
    build_pack(FONT, "A", "resource.images.splitflap.test", "Test Pack",
               out, 40, 36)
    with zipfile.ZipFile(out) as zf:
        meta = json.loads(
            zf.read("resource.images.splitflap.test/pack.json").decode("utf-8"))
    assert meta["half_w"] == 40
    assert meta["half_h"] == 36
    assert "NimbusSans" in meta["font"]


def test_warns_when_the_letterset_omits_ascii(tmp_path, capsys):
    out = str(tmp_path / "pack.zip")
    build_pack(FONT, "АБ", "resource.images.splitflap.ru", "RU",
               out, 40, 36)
    assert "ascii" in capsys.readouterr().out.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_make_glyph_pack.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tools.make_glyph_pack'`

- [ ] **Step 3: Write the implementation**

```bash
touch tools/__init__.py
```

`tools/make_glyph_pack.py`:

```python
"""Build an installable glyph pack from a font and a letterset.

A pack is a standard kodi.resource.images addon, so it installs from a zip
or from the official repository -- no filesystem access needed on Fire TV
or webOS, and no custom loader on our side.

A pack carries a font AND a letterset, so it both adds scripts and
restyles the board. A pack whose letterset includes ASCII overrides the
bundle completely and keeps the board typographically consistent.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
import zipfile
from typing import Iterable, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from resources.lib.charset import bundled_charset      # noqa: E402
from resources.lib.glyphgen import render_glyphs       # noqa: E402

NAMED = {
    "ascii": lambda: "".join(bundled_charset()),
    "cyrillic": lambda: "".join(
        chr(cp) for cp in range(0x400, 0x460) if not chr(cp).islower()),
    "greek": lambda: "".join(
        chr(cp) for cp in range(0x386, 0x3D0) if not chr(cp).islower()),
    "hebrew": lambda: "".join(chr(cp) for cp in range(0x5D0, 0x5EB)),
}

ADDON_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="{id}" name="{name}" version="1.0.0" provider-name="splitflap">
  <requires><import addon="kodi.resource" version="1.0.0"/></requires>
  <extension point="kodi.resource.images"/>
  <extension point="xbmc.addon.metadata">
    <summary lang="en_GB">Glyph pack for Split-Flap Board</summary>
    <description lang="en_GB">{name}</description>
    <platform>all</platform>
  </extension>
</addon>
"""


def charset_for(names):
    # type: (Iterable[str]) -> str
    out = []   # type: List[str]
    for name in names:
        key = name.strip().lower()
        if key not in NAMED:
            raise ValueError(
                "unknown charset %r, known: %s" % (name, ", ".join(sorted(NAMED)))
            )
        for ch in NAMED[key]():
            if ch not in out:
                out.append(ch)
    return "".join(out)


def build_pack(font, chars, addon_id, name, out_zip, half_w, half_h):
    # type: (str, str, str, str, str, int, int) -> str
    ascii_caps = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    if not ascii_caps.issubset(set(chars)):
        print("warning: letterset omits ascii -- the board will mix this "
              "pack's typeface with the bundled one. Add --charset ascii "
              "for a consistent look.")

    staging = tempfile.mkdtemp()
    try:
        root = os.path.join(staging, addon_id)
        os.makedirs(root)
        render_glyphs(chars, font, root, half_w, half_h)
        with open(os.path.join(root, "addon.xml"), "w") as handle:
            handle.write(ADDON_XML.format(id=addon_id, name=name))
        with open(os.path.join(root, "pack.json"), "w") as handle:
            json.dump({
                "font": os.path.basename(font),
                "chars": chars,
                "half_w": half_w,
                "half_h": half_h,
            }, handle, indent=2)
        with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for folder, _dirs, files in os.walk(root):
                for filename in files:
                    full = os.path.join(folder, filename)
                    zf.write(full, os.path.relpath(full, staging))
        return out_zip
    finally:
        shutil.rmtree(staging)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font", required=True)
    parser.add_argument("--charset", default="")
    parser.add_argument("--chars", default="")
    parser.add_argument("--chars-from", default="")
    parser.add_argument("--id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--half-w", type=int, default=156)
    parser.add_argument("--half-h", type=int, default=142)
    args = parser.parse_args()

    chars = ""
    if args.charset:
        chars += charset_for(args.charset.split(","))
    if args.chars:
        chars += args.chars
    if args.chars_from:
        with open(args.chars_from) as handle:
            chars += handle.read()
    chars = "".join(sorted(set(c for c in chars.upper() if c.strip() or c == " ")))
    if not chars:
        parser.error("no characters selected")

    build_pack(args.font, chars, args.id, args.name, args.out,
               args.half_w, args.half_h)
    print("wrote %s (%d characters)" % (args.out, len(chars)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_make_glyph_pack.py -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Build a real Cyrillic pack and check it on the device**

```bash
python tools/make_glyph_pack.py --font assets/fonts/NimbusSans-Regular.otf \
  --charset ascii,cyrillic \
  --id resource.images.splitflap.nimbus-ru \
  --name "Split-Flap - Nimbus, Latin + Cyrillic" \
  --out resource.images.splitflap.nimbus-ru.zip
```

Install it on the Fire TV, set `glyph_pack` to that id, and point the phrase file at a Cyrillic list. Confirm the glyphs resolve.

- [ ] **Step 6: Commit**

```bash
git add tools/__init__.py tools/make_glyph_pack.py tests/test_make_glyph_pack.py
git commit -m "feat: glyph pack builder emitting installable resource addons"
```

---

### Task 19: Packaging, README, and repository submission

**Files:**
- Create: `README.md`, `LICENSE`, `tools/build_addon.sh`
- Modify: `.github/workflows/tests.yml`

- [ ] **Step 1: Write the packaging script**

`tools/build_addon.sh`:

```bash
#!/usr/bin/env bash
# Package the addon exactly as Kodi expects: a single top-level directory
# named for the addon id.
set -euo pipefail

ID="screensaver.splitflap"
VERSION="$(grep -o 'version="[0-9.]*"' addon.xml | head -1 | cut -d'"' -f2)"
OUT="build/${ID}-${VERSION}.zip"

rm -rf build/staging
mkdir -p "build/staging/${ID}" build
cp -r addon.xml default.py icon.png fanart.jpg resources "build/staging/${ID}/"
find "build/staging/${ID}" -name '__pycache__' -type d -exec rm -rf {} +
find "build/staging/${ID}" -name '*.pyc' -delete

( cd build/staging && zip -qr "../../${OUT}" "${ID}" )
echo "wrote ${OUT}"
```

```bash
chmod +x tools/build_addon.sh
./tools/build_addon.sh
```

- [ ] **Step 2: Write the README**

`README.md`:

````markdown
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

**Fire TV users:** Fire OS runs its own screensaver. Set Kodi's screensaver
timeout shorter than Fire OS's, or Amazon's photo screensaver wins.

## Settings

| Setting | Meaning |
|---|---|
| Rows | Board height. Columns derive from it — the default 6 gives 22 columns, matching a real board. |
| Seconds per board | How long a finished board is held. Counted from when the flap finishes. |
| Show | Live info, or phrases. One at a time — they never interleave. |
| Phrase file | One phrase per board. `#` comments, blank lines ignored, `\n` puts the author on its own line. |
| Glyph pack | Add-on id of an installed glyph pack, for non-Latin scripts or a different typeface. |

## Phrase file format

```
# Lines starting with a hash are ignored.
THE ONLY WAY OUT IS THROUGH\nROBERT FROST
KEEP GOING
```

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
typefaces.

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
````

- [ ] **Step 3: Add the licence file**

```bash
curl -sSL -o LICENSE https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt
```

- [ ] **Step 4: Add packaging to CI**

Append to the `test` job in `.github/workflows/tests.yml`:

```yaml
      - name: package addon
        run: ./tools/build_addon.sh
      - uses: actions/upload-artifact@v4
        with:
          name: addon-zip
          path: build/*.zip
```

- [ ] **Step 5: Verify the full suite and the package**

Run: `python -m pytest -v && ./tools/build_addon.sh`
Expected: all tests PASS, zip written to `build/`

- [ ] **Step 6: Commit**

```bash
git add README.md LICENSE tools/build_addon.sh .github/workflows/tests.yml
git commit -m "chore: package the addon and document usage"
```

- [ ] **Step 7: Submit to the official Kodi repository**

Follow the Kodi addon submission process: fork `xbmc/repo-scripts`, add the
addon on the branch for the target Kodi version (`Omega`/`Piers`), open a pull
request. Their review covers licensing, packaging layout, and code standards.

Expect the licence question on Nimbus Sans. If raised, the fix is to
regenerate the bundled glyphs from Liberation Sans (OFL) — one command, no
code change, because the font is only ever an input to `glyphgen.py`:

```bash
curl -sSL -o assets/fonts/LiberationSans-Regular.ttf \
  https://github.com/liberationfonts/liberation-fonts/raw/main/src/LiberationSans-Regular.ttf
# edit FONT in tools/build_bundled.py, then:
python tools/build_bundled.py
```

---

### Task 20: Contributor source discovery

**Files:**
- Create: `resources/lib/sources/discovery.py`
- Modify: `resources/settings.xml`, `resources/language/resource.language.en_gb/strings.po`, `default.py`
- Test: `tests/test_discovery.py`

Deferred to v2 in the design, but the bar was "either there, or relatively simple to
add" — and a promise in a spec is not a seam that exists. The protocol is already fixed
by Task 9 and proven by two built-in sources, so this only adds the finding.

**Interfaces:**
- Consumes: `sources.base.Content`
- Produces: `SOURCE_PREFIX`; `discover(list_addons, load_module, log) -> List[object]`; `kodi_list_addons()`; `kodi_load_module(addon_id, path)`

- [ ] **Step 1: Write the failing test**

`tests/test_discovery.py`:

```python
from resources.lib.sources.base import Content
from resources.lib.sources.discovery import SOURCE_PREFIX, discover


class Module(object):
    def __init__(self, factory):
        self.create_source = factory


class Good(object):
    id = "good"

    def next(self):
        return Content(["HI"])


def modules(mapping):
    return lambda addon_id, path: mapping[addon_id]


def test_ignores_addons_without_the_prefix():
    listed = [("script.something.else", "/a"), ("plugin.video.x", "/b")]
    assert discover(lambda: listed, modules({}), lambda m: None) == []


def test_loads_a_matching_addon():
    aid = SOURCE_PREFIX + "quotes"
    found = discover(
        lambda: [(aid, "/a")],
        modules({aid: Module(lambda: Good())}),
        lambda m: None,
    )
    assert len(found) == 1
    assert found[0].next().lines == ("HI",)


def test_addon_missing_create_source_is_skipped_and_logged():
    aid = SOURCE_PREFIX + "broken"
    logged = []
    found = discover(
        lambda: [(aid, "/a")],
        modules({aid: object()}),
        logged.append,
    )
    assert found == []
    assert logged and aid in logged[0]


def test_addon_returning_a_non_source_is_skipped():
    aid = SOURCE_PREFIX + "wrong"
    logged = []
    found = discover(
        lambda: [(aid, "/a")],
        modules({aid: Module(lambda: "not a source")}),
        logged.append,
    )
    assert found == []
    assert logged


def test_raising_factory_does_not_abort_the_whole_scan():
    """One broken contributor must not hide the working ones."""
    bad, good = SOURCE_PREFIX + "bad", SOURCE_PREFIX + "good"

    def boom():
        raise RuntimeError("addon exploded at import")

    logged = []
    found = discover(
        lambda: [(bad, "/a"), (good, "/b")],
        modules({bad: Module(boom), good: Module(lambda: Good())}),
        logged.append,
    )
    assert len(found) == 1
    assert logged


def test_listing_failure_yields_no_sources_rather_than_raising():
    def boom():
        raise RuntimeError("json-rpc down")

    logged = []
    assert discover(boom, modules({}), logged.append) == []
    assert logged
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_discovery.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'resources.lib.sources.discovery'`

- [ ] **Step 3: Write the implementation**

`resources/lib/sources/discovery.py`:

```python
"""Find sources supplied by other add-ons.

A contributor declares a normal xbmc.python.module extension with an id
under SOURCE_PREFIX and exposes create_source(). We discover it, import
it, and call it -- no dependency declaration needed, which is the part
that has to be right, because we cannot declare a dependency on add-ons
that do not exist yet.

Listing and importing are injected, so the whole policy is testable
without Kodi. One broken contributor is skipped and logged; it must never
hide the working ones.
"""
from typing import Callable, List, Tuple

SOURCE_PREFIX = "script.splitflap.source."


def discover(list_addons, load_module, log):
    # type: (Callable[[], List[Tuple[str, str]]], Callable[[str, str], object], Callable[[str], None]) -> List[object]
    try:
        listed = list_addons()
    except Exception as exc:
        log("could not list add-ons: %r" % (exc,))
        return []

    found = []
    for addon_id, path in listed:
        if not addon_id.startswith(SOURCE_PREFIX):
            continue
        try:
            module = load_module(addon_id, path)
            factory = getattr(module, "create_source", None)
            if factory is None:
                raise AttributeError("no create_source()")
            source = factory()
            if not callable(getattr(source, "next", None)):
                raise TypeError("create_source() returned %r, which has no "
                                "next()" % (type(source).__name__,))
            if not getattr(source, "id", None):
                source.id = addon_id
            found.append(source)
        except Exception as exc:
            log("contributor %s skipped: %r" % (addon_id, exc))
    return found


def kodi_list_addons():
    # type: () -> List[Tuple[str, str]]
    """Enumerate installed python modules via JSON-RPC."""
    import json
    import xbmc
    import xbmcaddon

    request = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "Addons.GetAddons",
        "params": {"type": "xbmc.python.module", "enabled": True,
                   "properties": ["path"]},
    })
    reply = json.loads(xbmc.executeJSONRPC(request))
    out = []
    for entry in reply.get("result", {}).get("addons", []):
        addon_id = entry.get("addonid", "")
        if not addon_id.startswith(SOURCE_PREFIX):
            continue
        try:
            path = xbmcaddon.Addon(addon_id).getAddonInfo("path")
        except Exception:
            path = entry.get("path", "")
        out.append((addon_id, path))
    return out


def kodi_load_module(addon_id, path):
    # type: (str, str) -> object
    import importlib.util
    import os
    import xbmcvfs

    entry = os.path.join(xbmcvfs.translatePath(path), "source.py")
    spec = importlib.util.spec_from_file_location(
        addon_id.replace(".", "_"), entry)
    if spec is None or spec.loader is None:
        raise ImportError("no loadable source.py at %s" % (entry,))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_discovery.py -v`
Expected: PASS, 6 tests

- [ ] **Step 5: Add the setting**

Kodi's settings options are static, so a discovered add-on cannot appear in the
dropdown without dynamic-options machinery. A third option plus an id field costs two
settings and no machinery.

In `resources/settings.xml`, add to the `source` setting's `<options>`:

```xml
              <option label="30023">contributor</option>
```

and after the `source` setting, add:

```xml
        <setting id="source_addon_id" type="string" label="30024">
          <level>0</level><default></default><control type="edit" format="string"/>
        </setting>
```

In `strings.po`, append:

```po
msgctxt "#30023"
msgid "Add-on"
msgstr ""

msgctxt "#30024"
msgid "Source add-on id"
msgstr ""
```

In `resources/lib/config.py`, add to the returned dict:

```python
        "source_addon_id": get("source_addon_id"),
```

- [ ] **Step 6: Wire it into the entry point**

In `default.py`, replace `_build_source` with:

```python
def _build_source(cfg):
    if cfg["source"] == "contributor":
        from resources.lib.sources.discovery import (
            discover, kodi_list_addons, kodi_load_module)
        wanted = cfg["source_addon_id"]
        for source in discover(kodi_list_addons, kodi_load_module, log):
            if not wanted or source.id == wanted:
                return source
        log("no contributor source %r found, falling back to live info"
            % (wanted,))
        return LiveInfoSource(cfg["info_flags"], cfg["info_combine"])
    if cfg["source"] == "phrases":
        pools = [parse_phrases(_read_text(cfg["phrases_file"]))]
        if cfg["phrases_url"]:
            cache_path = os.path.join(cfg["profile"], "remote.txt")
            cache = RemoteCache(
                read=lambda: _read_text(cache_path) or None,
                write=lambda text: io.open(
                    cache_path, "w", encoding="utf-8").write(text),
            )
            pools.append(cache.load(http_get, cfg["phrases_url"]))
        return PhraseSource(pools, random.Random())
    return LiveInfoSource(cfg["info_flags"], cfg["info_combine"])
```

An uninstalled or missing contributor falls back to live info — the one source that
always resolves, since `System.Time` cannot be empty.

- [ ] **Step 7: Document the contract**

Append to `README.md`:

````markdown
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
````

- [ ] **Step 8: Run the full suite**

Run: `python -m pytest -v`
Expected: all PASS

- [ ] **Step 9: Commit**

```bash
git add resources/lib/sources/discovery.py tests/test_discovery.py \
        resources/settings.xml resources/language resources/lib/config.py \
        default.py README.md
git commit -m "feat: discover source add-ons via a documented extension point"
```

---

## Self-Review

**Spec coverage.** Walked every spec section against the task list:

| Spec section | Task |
|---|---|
| Architecture / module map | 1, and each module's own task |
| addon.xml | 16 |
| Geometry | 5 |
| Controls | 14 |
| Glyphs | 3, 4 |
| Drum | 7 |
| Flap sequence / half-step / transitions / loop | 8, 16 |
| Sources / protocol | 9 |
| Accents | 6 (resolution), 9 and 11 (production) |
| Phrases | 9, 10, 12 |
| Live info | 11, 15 |
| Contributor addons | Protocol in Task 9, discovery in Task 20 |
| Layout | 6 |
| Glyph pipeline / bundled set / font / packs | 2, 3, 4, 18 |
| Runtime generation | **Gap found** — see below |
| Settings | 16 |
| Distribution | 19 |
| Testing | every task, plus 17 for the manual pass |
| Spike | 0 |

**Gap found and closed:** contributor discovery had no task. The design defers it to
v2, but the stated bar was "either there, or relatively simple to add", so Task 20
implements it — the protocol was already fixed and proven by two built-in sources, so
only the finding was missing.

**Gap found and accepted:** the spec keeps a guarded runtime-PIL glyph
generation path; no task implements it. It is deliberately deferred — it is
dead code on Fire TV and webOS (the only targets that matter here), and
`glyphgen.py` already exists for it. Adding it later is a background thread
around `render_glyphs` writing into `addon_data/glyphs/`, which Task 4's
resolution order already searches first. Flagged rather than silently dropped.

**Placeholder scan:** no TBD/TODO, no "add error handling", no "similar to
Task N", no test steps without test code.

**Type consistency:** `glyph_filename(ch, half)` is used identically in Tasks
3, 4 and 18. `Content(lines, accents, refresh_in)` is constructed in Tasks 9,
11, 13 and consumed in 16 with the same field names. `half` is always the
string `"top"`/`"bottom"`, never a bool. `Geometry.half_rect(row, col, half)`
returns `(x, y, w, h)` in Tasks 5 and 14. `PaintOp(cell, half, char)` with
`cell` a row-major int in Tasks 8 and 14. `build(lines, accents, rows, cols,
rtl)` in Tasks 6, 12 and 16.
