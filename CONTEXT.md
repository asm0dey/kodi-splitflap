# Split-Flap Screensaver

A Kodi screensaver that renders a mechanical split-flap departure board, displaying
phrases and live information. This glossary fixes the vocabulary; the design lives in
`docs/superpowers/specs/`.

## The board

**Board**:
The complete grid of cells at one moment, showing one piece of content.
_Avoid_: screen, page, frame

**Cell**:
A single position in the board's grid, identified by row and column.
_Avoid_: slot, square

**Tile**:
The flapping unit that occupies a cell and displays one character. Composed of two
halves.
_Avoid_: card, flap (as a noun), cell

**Half**:
The top or bottom portion of a tile. The two halves can display different characters
mid-flap, which is what produces the hinge effect.

**Block**:
The wrapped text occupying part of the board. Its height varies with content and it is
always centred in the grid.
_Avoid_: text block, message, band

**Accent cell**:
A cell tinted a distinct colour to draw the eye. Which cells are accented is decided by
the source, not by the board.

## Characters and rendering

**Glyph**:
The rendered image of one character for one half of a tile. Greyscale, so a colour
tint can be applied over it.

**Glyph set**:
The collection of characters a board can currently display, determined by the bundled
glyphs plus any selected pack.

**Glyph pack**:
An installable addon supplying a font and a letterset, extending or replacing the
bundled glyph set.

**Tofu**:
The □ marker shown in place of a character absent from the glyph set.

**Drum**:
The ordered, circular sequence of characters a tile cycles through when flapping.
Named for the physical drum of flaps in a Solari board.

**Flap**:
One tile's animated transition from its current character to a target character.

## Content

**Source**:
An origin of board content — a phrase file, a remote list, or Kodi's own information
labels. Exactly one is active at a time.
_Avoid_: contributor, provider, feed

**Phrase**:
One line of text from a source, which becomes exactly one board.
_Avoid_: quote, message, item

**Hold**:
How long a settled board is held before the next one is targeted. Counted from the
moment the flap finishes.
_Avoid_: dwell, delay, interval, timeout

**Contributor addon**:
A separate addon supplying a source, so third parties can provide content without
touching this addon's rendering.
