# Manual verification checklist

The Kodi shell (`board.py`, `liveinfo.py`, `config.py`, `default.py`,
`discovery.py`) has no automated coverage by design — it builds Kodi objects
that cannot exist off-device. This checklist is its test.

Run **Part A on desktop Kodi first**. It catches the crashes cheaply, and
everything in Part B assumes the add-on at least starts.

Record PASS/FAIL plus what you actually observed. "Seemed fine" is not a
result; the point of writing it down is that the next person can tell what was
genuinely checked.

---

## Part A — desktop Kodi (crashes, wiring, resolution)

Install: **Settings → Add-ons → Install from zip file →**
`screensaver.splitflap-0.1.0.zip`

Then **Settings → Interface → Screensaver → Split-Flap Board**, and use
**Preview** rather than waiting for the idle timeout.

| # | Check | Expected | Result |
|---|---|---|---|
| A1 | Add-on installs | No dependency error. Icon and fanart appear in the add-on browser | |
| A2 | First run, default settings | A board of blank tiles builds, then time/date/weather flap in. Default source is Live info, so this works with **no configuration at all** | |
| A3 | First board appears | Within ~2s of activation | |
| A4 | Dismissal | Any key or mouse move exits and returns to the previous window. **No crash, no hang** | |
| A5 | Clock ticks in place | Wait for a minute boundary. The minutes digit re-flaps *without* the board changing to different content | |
| A6 | `1`→`2` vs `9`→`0` | A single-digit step is one flap (~200ms). A `9`→`0` rollover spins the drum. Both are correct — the drum is forward-only | |
| A7 | Phrases source | Set **Content → Show → Phrases**. 30 bundled phrases appear, none truncated with `…` | |
| A8 | Accents | The accent-coloured tiles render in the accent colour (default blue), everything else in the letter colour | |
| A9 | Rows setting | Set rows to 3, then to 10. Columns rescale, board stays centred, nothing renders off-screen | |
| A10 | Glyph pack resolves | Install `resource.images.splitflap.nimbus-ru.zip`, set **Glyphs → glyph pack** to `resource.images.splitflap.nimbus-ru`, point the phrase file at a Cyrillic list. Glyphs resolve via `resource://` | |
| A11 | Missing pack degrades | Set the glyph pack id to something not installed. Board falls back to bundled glyphs — **tofu (□), not a crash** | |
| A12 | Bad colour value | Type garbage into the letter colour field. Board renders white with a warning in the log, rather than corrupting every tile | |
| A13 | Log check | `grep splitflap ~/.kodi/temp/kodi.log` — note which `colorDiffuse` branch was taken (kwarg vs `setColorDiffuse` fallback). **This answers spike item 4** | |

---

## Part B — Amazon Fire TV (only what needs the hardware)

Install the same zip. Fire OS runs its own screensaver, so first:

> **Set Kodi's screensaver timeout shorter than Fire OS's**, or Amazon's photo
> screensaver wins and you will never see this one.

| # | Check | Expected | Result |
|---|---|---|---|
| B1 | Control budget | Board builds without a visible stall. **Spike item 2** — this is the A53-silicon question that cannot be answered from a desktop | **PASS** — runs smoothly on a Fire TV (2026-08-27). Closes the project's longest-standing unknown: 264 controls with ~40 setImage calls per 200ms step are comfortable on A53. No fallback to fewer rows needed. |
| B2 | Idle cost | With a settled board, `adb shell top -m 5` shows Kodi essentially idle. A settled board emits zero paint ops by design; if CPU is busy, that claim is wrong | |
| B3 | Flap feel | Watch a full-drum wrap (`9`→`0`) from couch distance. Does `MAX_STEPS = 12` at 200ms/step look right, or should it be higher? **Spike item 0 — a judgement, not a measurement** | |
| B4 | Transition smoothness | During a board change, no stutter. Glyph resolution is memoised; if it stutters, that memoisation is not working as intended | |
| B5 | Dismissal under load | Press a key *during* a flap transition. Clean exit, no crash. This is the teardown race that was fixed — B5 is what confirms the fix | |
| B6 | Texture memory | 285 glyph textures resident worst case (~24MB). No out-of-memory, no texture thrashing | |
| B7 | GUI resolution | Check **Settings → System → Display**. Fire Sticks often render the GUI at 1080p even on a 4K panel; at 4K the glyphs are pixel-perfect 1:1 | |

---

## If something fails

- `adb shell "run-as org.xbmc.kodi cat files/.kodi/temp/kodi.log" | grep splitflap`
- Every log line from this add-on is prefixed `splitflap:`
- The most likely failure modes, in order: Fire OS screensaver winning (timeout),
  a `colorDiffuse` path this build does not support (A13 tells you which branch),
  and control-build time on the Stick (B1)

## Known limitation

A source that *hangs* freezes the screensaver — accepted, since neither built-in
source can hang. It becomes relevant only if third-party contributor sources
ship. Recorded in the spec, not a defect to report.
