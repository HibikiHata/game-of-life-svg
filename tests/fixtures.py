"""Frozen test data.

These fixtures were authored once and are not extended. Adding to them
invalidates every count assertion already written, so an unavoidable addition
must re-verify all of them in the same change.
"""

from __future__ import annotations

# Gosper's glider gun, expanded from standard RLE. The origin is top-left and y
# points down. It spans 36x9 and emits a glider every 30 generations.
GOSPER_GUN = (
    (24, 0), (22, 1), (24, 1), (12, 2), (13, 2), (20, 2),
    (21, 2), (34, 2), (35, 2), (11, 3), (15, 3), (20, 3),
    (21, 3), (34, 3), (35, 3), (0, 4), (1, 4), (10, 4),
    (16, 4), (20, 4), (21, 4), (0, 5), (1, 5), (10, 5),
    (14, 5), (16, 5), (17, 5), (22, 5), (24, 5), (10, 6),
    (16, 6), (24, 6), (11, 7), (15, 7), (12, 8), (13, 8),
)

# The gun's "core" is the mechanism itself. Emitted gliders leave towards the
# bottom right, so whether the core is intact is judged inside this rectangle
# alone.
GOSPER_GUN_CORE = (0, 0, 26, 9)     # x, y, w, h


def gun_cells(level: int = 1) -> dict[tuple[int, int], int]:
    return {pos: level for pos in GOSPER_GUN}


def core_cells(levels: dict[tuple[int, int], int]) -> dict[tuple[int, int], int]:
    x0, y0, w, h = GOSPER_GUN_CORE
    return {(x, y): v for (x, y), v in levels.items()
            if x0 <= x < x0 + w and y0 <= y < y0 + h}
