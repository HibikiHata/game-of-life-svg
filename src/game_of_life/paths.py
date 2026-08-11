"""Encode the live cells of a board into a single SVG path.

Cells adjacent along a row are merged into one rectangle. Measured on
2026-08-10, this produces roughly a fifth of the bytes of the naive one
`<rect>` per cell approach, and a 1.2x to 1.9x advantage survives gzip.

**The output order is fixed to ascending `(y, x)`.** If set or dict iteration
order leaks into the output, the same board emits different bytes. The picture
is unchanged, so only the determinism test and the golden files can catch it.
"""

from __future__ import annotations

from typing import Iterable

Pos = tuple[int, int]


def run_merged_path(cells: Iterable[Pos]) -> str:
    """Turn a set of cells into a `d` attribute. Empty input gives ""."""
    by_row: dict[int, set[int]] = {}
    for cell in cells:
        try:
            x, y = cell
        except (TypeError, ValueError) as exc:
            raise ValueError(f"malformed coordinate: {cell!r}") from exc
        if not isinstance(x, int) or not isinstance(y, int):
            raise ValueError(f"coordinates must be integers: {cell!r}")
        by_row.setdefault(y, set()).add(x)

    parts: list[str] = []
    for y in sorted(by_row):
        xs = sorted(by_row[y])
        i = 0
        while i < len(xs):
            j = i
            while j + 1 < len(xs) and xs[j + 1] == xs[j] + 1:
                j += 1
            n = j - i + 1
            parts.append(f"M{xs[i]} {y}h{n}v1h-{n}z")
            i = j + 1
    return "".join(parts)
