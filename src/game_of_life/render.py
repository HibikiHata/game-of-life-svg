"""Bake a frame sequence into a self-contained SVG.

One frame is one `<g>`, holding one `<path>` per level. `paths` fixes the cell
order to ascending `(y, x)`, so the same input always emits the same bytes.

The budget is measured **after gzip**. The delivery path was measured to serve
`content-encoding: gzip`, and judging on raw bytes is off by a factor of 5 to
30 — the compression ratio depends on how repetitive the content is, and is not
a constant.
"""

from __future__ import annotations

import gzip
from dataclasses import dataclass
from typing import Sequence

from game_of_life.board import Board
from game_of_life.config import Options
from game_of_life.document import Svg
from game_of_life.keyframes import frame_track
from game_of_life.paths import run_merged_path
from game_of_life.rules import Rule
from game_of_life.theme import Theme

CELL_PIXELS = 10


@dataclass(frozen=True)
class SizeReport:
    path: str
    raw_bytes: int
    gzipped_bytes: int
    within_budget: bool


def _check(frames: Sequence[Board]) -> Board:
    if not frames:
        raise ValueError("no frames: there is nothing to bake")
    first = frames[0]
    for f in frames:
        if (f.width, f.height) != (first.width, first.height):
            raise ValueError(
                f"frame dimensions disagree: {first.width}x{first.height} "
                f"and {f.width}x{f.height}"
            )
    return first


def _level_paths(board: Board, rule: Rule, theme: Theme) -> str:
    """One path per level. Empty levels are not emitted."""
    by_level: dict[int, list[tuple[int, int]]] = {}
    for pos, level in board.levels:
        by_level.setdefault(level, []).append(pos)
    out = []
    for level in sorted(by_level):
        colour = theme.colour_for(level, rule.max_level)
        out.append(f'<path style="fill:{colour}" d="{run_merged_path(by_level[level])}"/>')
    return "".join(out)


def _document(board: Board, title: str) -> Svg:
    return Svg(width=board.width * CELL_PIXELS, height=board.height * CELL_PIXELS,
               view_box=f"0 0 {board.width} {board.height}", title=title)


def bake(frames: Sequence[Board], *, rule: Rule, theme: Theme,
         options: Options, title: str) -> bytes:
    """Return one animated SVG."""
    first = _check(frames)
    track = frame_track(frame_count=len(frames), fps=options.fps)
    svg = _document(first, title)
    svg.set_style(track.css)
    svg.append(f'<rect width="{first.width}" height="{first.height}" '
               f'style="fill:{theme.background}"/>')
    for i, board in enumerate(frames):
        svg.append(
            f'<g class="f f{i}" style="animation-delay:{track.delays[i]}">'
            f"{_level_paths(board, rule, theme)}</g>"
        )
    return svg.render().encode("utf-8")


def bake_static(board: Board, *, rule: Rule, theme: Theme,
                options: Options, title: str) -> bytes:
    """A single-frame variant carrying no animation at all.

    It gives viewers with `prefers-reduced-motion` something to reference, and
    at the same time guarantees the content is visible on any path that does
    not run CSS animation.
    """
    _check([board])
    svg = _document(board, title)
    svg.append(f'<rect width="{board.width}" height="{board.height}" '
               f'style="fill:{theme.background}"/>')
    svg.append(f"<g>{_level_paths(board, rule, theme)}</g>")
    return svg.render().encode("utf-8")


def size_report(path: str, data: bytes, budget_bytes: int) -> SizeReport:
    gzipped = len(gzip.compress(data, 9))
    return SizeReport(path=path, raw_bytes=len(data), gzipped_bytes=gzipped,
                      within_budget=gzipped <= budget_bytes)
