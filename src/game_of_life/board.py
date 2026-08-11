"""Board geometry and neighbourhoods.

A `Board` knows nothing about rules. It knows its dimensions, its boundary
condition, and which cells are alive at which strength — nothing more.

`levels` is held as a **canonical tuple** rather than a Mapping for three
reasons, all of them functional requirements:

1. `frozen=True` only prevents rebinding an attribute, so a dict would still be
   mutable in place
2. a dict is unhashable, and cycle detection needs a set of "states already seen"
3. if dict or set iteration order leaks out, the same board emits different bytes

Canonicalising to ascending `(y, x)` settles all three in the type itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Mapping

Pos = tuple[int, int]

BOUNDARIES = ("torus", "fixed")
MIN_DIMENSION = 3


@dataclass(frozen=True)
class Board:
    width: int
    height: int
    boundary: str
    levels: tuple[tuple[Pos, int], ...]      # ascending (y, x); levels are >= 1

    @classmethod
    def of(cls, *, width: int, height: int, boundary: str,
           levels: Mapping[Pos, int]) -> "Board":
        """Build a validated, canonicalised board. Do not call `__init__` directly."""
        if boundary not in BOUNDARIES:
            raise ValueError(
                f"unknown boundary: {boundary!r} (expected {' / '.join(BOUNDARIES)})"
            )
        # A torus narrower than three counts the same cell as a neighbour twice,
        # which destroys the meaning of the rule.
        if width < MIN_DIMENSION or height < MIN_DIMENSION:
            raise ValueError(
                f"board too small: {width}x{height} "
                f"(each side must be at least {MIN_DIMENSION})"
            )
        for (x, y), level in levels.items():
            if level < 1:
                # Level 0 means dead. Putting it on the board corrupts both the
                # live count and the neighbour counts.
                raise ValueError(f"level must be at least 1: {(x, y)} has {level}")
            if not (0 <= x < width and 0 <= y < height):
                raise ValueError(
                    f"outside the board: {(x, y)} does not fit {width}x{height}"
                )
        canonical = tuple(sorted(levels.items(), key=lambda kv: (kv[0][1], kv[0][0])))
        return cls(width=width, height=height, boundary=boundary, levels=canonical)

    def with_levels(self, levels: Mapping[Pos, int]) -> "Board":
        """The same dimensions and boundary, with the contents replaced."""
        return Board.of(width=self.width, height=self.height,
                        boundary=self.boundary, levels=levels)

    def clamped(self, max_level: int) -> "Board":
        """Lower every level to the rule's maximum.

        Rounding implicitly would change the picture silently, so the caller
        does it explicitly. It is needed when a calendar-derived board (levels
        1 to 4) is run under the standard rule, whose maximum is 1.
        """
        if max_level < 1:
            raise ValueError(f"max_level must be at least 1: {max_level}")
        return self.with_levels({p: min(v, max_level) for p, v in self.levels})

    def as_map(self) -> dict[Pos, int]:
        return dict(self.levels)

    @property
    def live_count(self) -> int:
        """The number of live cells, not the sum of their levels."""
        return len(self.levels)

    @property
    def density(self) -> float:
        return self.live_count / (self.width * self.height)


def _neighbours(x: int, y: int, board: Board) -> Iterator[Pos]:
    torus = board.boundary == "torus"
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if torus:
                yield nx % board.width, ny % board.height
            elif 0 <= nx < board.width and 0 <= ny < board.height:
                yield nx, ny


def neighbour_counts(board: Board) -> dict[Pos, int]:
    """Live neighbours per cell. **Counted by presence, never by level.**

    Positions with no live cell appear too, as long as a live cell is adjacent —
    births are decided there.
    """
    counts: dict[Pos, int] = {}
    for (x, y), _level in board.levels:
        for pos in _neighbours(x, y, board):
            counts[pos] = counts.get(pos, 0) + 1
    return counts
