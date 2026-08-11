"""Place a library pattern on a different canvas.

A pattern's RLE declares its own board, but that is a default rather than a
fixed property. A glider placed on `square-l` wraps at 100 cells instead of 20,
so the same pattern yields a different animation. This is the only place where
the presets carry meaning; without it they would be settings nobody reads.

The boundary condition belongs to the pattern, not to the canvas. A gun placed
on a torus destroys itself (measured: generation 180 on a 60x40 field), so the
boundary is carried over even when the canvas changes.
"""

from __future__ import annotations

from game_of_life.board import Board
from game_of_life.config import PRESETS
from game_of_life.rle import Pattern


def board_for_preset(pattern: Pattern, preset: str, *, level: int = 1) -> Board:
    """Return a board with the pattern centred on the preset's canvas."""
    if preset not in PRESETS:
        raise ValueError(f"unknown preset: {preset!r} (expected {' / '.join(PRESETS)})")
    size = PRESETS[preset].size
    if size is None:
        # The grass widget's dimensions come from the calendar. Fixing them here
        # would reject the legitimate 52-to-54 week variation.
        raise ValueError(
            f"preset {preset!r} has no fixed size (it is derived from the calendar)"
        )

    width, height = size
    cells = pattern.cells
    span_x = max(x for x, _ in cells) + 1
    span_y = max(y for _, y in cells) + 1
    if span_x > width or span_y > height:
        raise ValueError(
            f"{pattern.name} spans {span_x}x{span_y} and does not fit the "
            f"{width}x{height} canvas of preset {preset}"
        )

    ox = (width - span_x) // 2
    oy = (height - span_y) // 2
    return Board.of(width=width, height=height, boundary=pattern.boundary,
                    levels={(x + ox, y + oy): level for x, y in cells})
