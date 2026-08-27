---
title: Split-Flap Board
---

# Split-Flap Board for Kodi

A screensaver that renders a mechanical split-flap departure board — the kind
that used to clatter in railway stations and airports — showing motivational
phrases, the time, and the weather.

## Install

Add this source in Kodi:

```
https://asm0dey.github.io/kodi-splitflap/repo
```

**Settings → File manager → Add source**, paste the URL, name it `splitflap`.
Then **Settings → Add-ons → Install from zip file → splitflap →
`repository.splitflap-1.0.0.zip`**.

After that the screensaver and its glyph packs appear under
**Install from repository → Split-Flap Repository**, and update themselves like
any other add-on.

Prefer a single zip? Grab
[`screensaver.splitflap`](repo/screensaver.splitflap/) directly — you just
won't get updates.

## What's here

| Add-on | What it is |
|---|---|
| `screensaver.splitflap` | the screensaver |
| `resource.images.splitflap.nimbus-ru` | a glyph pack adding Cyrillic |
| `repository.splitflap` | this repository, so the others self-update |

The bundled glyphs cover capitals-only extended ASCII — Western European out of
the box. Anything else shows as tofu (□) until you install a pack, which
matters on a Fire TV or webOS device where there is no practical way to drop
files onto the box.

## Fire TV

Fire OS runs its own screensaver. Set Kodi's timeout shorter than Fire OS's, or
Amazon's photo screensaver wins and you never see this one.
