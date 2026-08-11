"""Generating the sequence, detecting the cycle, and slicing the range.

Cycle detection uses a digest to *propose* a repeat and **confirms it by
comparing the boards themselves**. Deciding on the digest alone means a single
collision breaks the promise of a seamless loop. A board holds a canonical
tuple, so it can be a dict key directly and Python would compare for equality
on collision — but the confirmation is written out explicitly rather than left
to that. The injectable `digest` exists so the property can be tested.

`frame_range` is an enumeration (cycle / full / head) and the generation count
lives in `limit`. An earlier design packed "which slice" and "how many
generations" into one `head:N` string, where `N > limit` was undefined.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from game_of_life.board import Board, neighbour_counts
from game_of_life.rules import Rule

FRAME_RANGES = ("cycle", "full", "head")


@dataclass
class Run:
    """A generation sequence and only the facts actually observed about it.

    `fallback` is mutable: `slice_range` records there that the requested range
    could not be satisfied.
    """

    frames: tuple[Board, ...]
    transient: int
    period: int | None
    stopped_empty: bool
    fallback: str | None = None


def _default_digest(board: Board) -> bytes:
    return repr(board.levels).encode("utf-8")


def step(board: Board, rule: Rule) -> Board:
    """Advance one generation. The input is never modified."""
    counts = neighbour_counts(board)
    current = board.as_map()
    nxt: dict[tuple[int, int], int] = {}
    for pos in set(current) | set(counts):
        level = rule.next_level(current.get(pos, 0), counts.get(pos, 0))
        if level:
            nxt[pos] = level
    return board.with_levels(nxt)


def sequence(board: Board, rule: Rule, limit: int,
             digest: Callable[[Board], bytes] = _default_digest) -> Run:
    """Return `limit` generations of boards, and whether a cycle was found."""
    if limit < 1:
        raise ValueError(f"limit must be at least 1: {limit}")
    # If the board carries levels above the rule's maximum, stop rather than
    # round. Rounding silently produces a different picture than the one asked
    # for; the caller does it explicitly with Board.clamped.
    over = [v for _, v in board.levels if v > rule.max_level]
    if over:
        raise ValueError(
            f"board levels exceed the maximum of {rule.max_level} for rule "
            f"{rule.name}: highest is {max(over)}. "
            f"Lower them explicitly with Board.clamped({rule.max_level})"
        )

    frames: list[Board] = []
    seen: dict[bytes, list[int]] = {}
    transient = 0
    period: int | None = None
    stopped_empty = False

    for i in range(limit):
        frames.append(board)
        key = digest(board)
        if period is None:
            for j in seen.get(key, ()):
                # The digest only proposes. Identity is confirmed on the board.
                if frames[j] == board:
                    transient, period = j, i - j
                    break
        seen.setdefault(key, []).append(i)

        if board.live_count == 0:
            # An empty board is a still life too. Reporting period 0 would make
            # the cycle range zero frames long, which always trips the
            # renderer's precondition.
            stopped_empty = True
            if period is None:
                transient, period = i, 1
            break

        board = step(board, rule)

    return Run(frames=tuple(frames), transient=transient,
               period=period, stopped_empty=stopped_empty)


def slice_range(run: Run, frame_range: str) -> tuple[Board, ...]:
    """Return the requested frames, recording `run.fallback` if that is impossible."""
    if frame_range not in FRAME_RANGES:
        raise ValueError(
            f"invalid frame_range: {frame_range!r} (expected {' / '.join(FRAME_RANGES)})"
        )
    if frame_range == "head":
        return run.frames

    if run.period is None:
        run.fallback = (
            f"{frame_range} was requested, but no cycle was found within "
            f"{len(run.frames)} generations, so it was baked as head"
        )
        return run.frames

    if frame_range == "cycle":
        return run.frames[run.transient:run.transient + run.period]
    return run.frames[:run.transient + run.period]
