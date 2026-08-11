"""Load the pattern library.

Patterns live in `assets/patterns/*.rle`, one per file. Adding a pattern means
adding a file; nothing is added to the code.

Loading reads every file at once and stops, **naming the offending file**, if
any one of them is broken. Silently skipping a broken pattern would make it
disappear from the gallery with nobody noticing.
"""

from __future__ import annotations

import pathlib

from game_of_life.rle import CATEGORIES, Pattern, RleError, parse_rle

PATTERN_DIR = pathlib.Path(__file__).resolve().parent / "assets" / "patterns"
MINIMUM_PATTERNS = 25


def load_all(directory: pathlib.Path | None = None) -> tuple[Pattern, ...]:
    """Read every RLE in the directory. Ordered by file name, so deterministic."""
    directory = directory or PATTERN_DIR
    if not directory.is_dir():
        raise RleError(f"pattern directory not found: {directory.name}")
    out = []
    for path in sorted(directory.glob("*.rle")):
        try:
            out.append(parse_rle(path.read_text(encoding="utf-8"), slug=path.stem))
        except RleError as exc:
            raise RleError(f"{path.name}: {exc}") from exc
    return tuple(out)


def by_category(patterns: tuple[Pattern, ...]) -> dict[str, list[Pattern]]:
    """Category order, then name order within a category. The gallery follows this."""
    grouped: dict[str, list[Pattern]] = {c: [] for c in CATEGORIES}
    for p in patterns:
        grouped[p.category].append(p)
    return {c: sorted(ps, key=lambda p: p.name) for c, ps in grouped.items() if ps}
