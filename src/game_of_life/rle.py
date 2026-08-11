"""Reading RLE, the standard interchange format for Life patterns.

**Standard RLE is read as-is.** The `x = <w>, y = <h>, rule = <rule>` header and
the `#N` (name) and `#O` (discoverer) lines are part of the standard; rejecting
them would make every file from an external collection unusable.

Metadata specific to this repository rides on `#C key: value`. `#C` is the
standard's free-form comment line, so the files stay valid for other tools.

Unknown tokens are **rejected rather than skipped**. A cell that is not read
simply vanishes from the picture without an error, and a subtly different
pattern ships.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from game_of_life.board import Board

CATEGORIES = ("still-life", "oscillator", "spaceship", "gun", "methuselah", "misc")
BOUNDARIES = ("torus", "fixed")
FRAME_RANGES = ("cycle", "full", "head")
REQUIRED_KEYS = ("category", "board", "boundary", "frame_range", "generations", "offset")

_HEADER = re.compile(
    r"^\s*x\s*=\s*(\d+)\s*,\s*y\s*=\s*(\d+)\s*(?:,\s*rule\s*=\s*(\S+))?\s*$",
    re.IGNORECASE,
)


class RleError(Exception):
    """An RLE file could not be read. Always names the file and the cause."""


@dataclass(frozen=True)
class Pattern:
    slug: str
    name: str
    discovered: str
    explanation: str
    category: str
    board: tuple[int, int]
    boundary: str
    frame_range: str
    generations: int
    offset: tuple[int, int]
    core: tuple[int, int, int, int] | None
    core_period: int | None
    extents: tuple[int, int]
    header_rule: str | None
    cells: frozenset[tuple[int, int]]

    def to_board(self, level: int = 1) -> Board:
        ox, oy = self.offset
        width, height = self.board
        return Board.of(width=width, height=height, boundary=self.boundary,
                        levels={(x + ox, y + oy): level for x, y in self.cells})


def _pair(value: str, count: int, key: str) -> tuple[int, ...]:
    parts = [p.strip() for p in value.replace("x", ",").split(",")]
    if len(parts) != count:
        raise RleError(f"{key} must be {count} integers: {value!r}")
    try:
        return tuple(int(p) for p in parts)
    except ValueError as exc:
        raise RleError(f"{key} is not made of integers: {value!r}") from exc


def _body_cells(body: str, extents: tuple[int, int]) -> frozenset[tuple[int, int]]:
    cells: set[tuple[int, int]] = set()
    x = y = 0
    run = ""
    for ch in body:
        if ch.isdigit():
            run += ch
            continue
        count = int(run) if run else 1
        run = ""
        if ch == "b":
            x += count
        elif ch == "o":
            for i in range(count):
                cells.add((x + i, y))
            x += count
        elif ch == "$":
            y += count
            x = 0
        elif ch == "!":
            break
        elif ch.isspace():
            continue
        else:
            # Skipping it would make cells disappear from the picture in silence.
            raise RleError(f"uninterpretable token in the RLE body: {ch!r}")
    w, h = extents
    for cx, cy in cells:
        if not (0 <= cx < w and 0 <= cy < h):
            raise RleError(
                f"cell outside the declared extents: {(cx, cy)} is beyond {w}x{h}"
            )
    return frozenset(cells)


def parse_rle(text: str, slug: str = "pattern") -> Pattern:
    name = discovered = ""
    meta: dict[str, str] = {}
    explanation: list[str] = []
    extents: tuple[int, int] | None = None
    header_rule: str | None = None
    body: list[str] = []

    for line in text.splitlines():
        if line.startswith("#N"):
            name = line[2:].strip()
        elif line.startswith("#O"):
            discovered = line[2:].strip()
        elif line.startswith("#C"):
            payload = line[2:].strip()
            key, _, value = payload.partition(":")
            key, value = key.strip(), value.strip()
            if key == "explanation":
                explanation.append(value)
            elif value:
                meta[key] = value
        elif line.startswith("#"):
            continue                       # other standard comments (#P, #R, ...)
        elif extents is None:
            m = _HEADER.match(line)
            if m:
                extents = (int(m.group(1)), int(m.group(2)))
                header_rule = m.group(3)
        else:
            body.append(line)

    if extents is None:
        raise RleError("the standard `x = , y = , rule = ` header was not found")
    if not explanation:
        raise RleError("explanation is missing (every pattern needs an original one)")
    for key in REQUIRED_KEYS:
        if key not in meta:
            raise RleError(f"the required `#C {key}:` is missing")

    category = meta["category"]
    if category not in CATEGORIES:
        raise RleError(
            f"invalid category: {category!r} (expected {' / '.join(CATEGORIES)})"
        )
    boundary = meta["boundary"]
    if boundary not in BOUNDARIES:
        raise RleError(
            f"invalid boundary: {boundary!r} (expected {' / '.join(BOUNDARIES)})"
        )
    frame_range = meta["frame_range"]
    if frame_range not in FRAME_RANGES:
        raise RleError(
            f"invalid frame_range: {frame_range!r} (expected {' / '.join(FRAME_RANGES)})"
        )

    core = _pair(meta["core"], 4, "core") if "core" in meta else None
    if category == "gun" and core is None:
        # Without a core there is no way to assert the gun is still intact, and
        # a self-destroying gun could ship.
        raise RleError("the gun category requires `#C core: x,y,w,h`")
    core_period = int(meta["core_period"]) if "core_period" in meta else None
    if category == "gun" and core_period is None:
        # Without the period the comparison cannot be phase-aligned, and even an
        # intact gun would mismatch.
        raise RleError("the gun category requires `#C core_period: <period>`")

    cells = _body_cells("".join(body), extents)
    board = _pair(meta["board"], 2, "board")
    offset = _pair(meta["offset"], 2, "offset")
    ox, oy = offset
    for cx, cy in cells:
        if not (0 <= cx + ox < board[0] and 0 <= cy + oy < board[1]):
            raise RleError(
                f"with offset {offset} the cells do not fit the "
                f"{board[0]}x{board[1]} board"
            )

    return Pattern(
        slug=slug, name=name or "(unnamed)", discovered=discovered,
        explanation=" ".join(explanation), category=category, board=board,
        boundary=boundary, frame_range=frame_range,
        generations=int(meta["generations"]), offset=offset, core=core, core_period=core_period,
        extents=extents, header_rule=header_rule, cells=cells,
    )
