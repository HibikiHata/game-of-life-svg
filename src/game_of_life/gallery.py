"""Assemble the gallery's artefacts and its page.

The artefacts and the page come out of **the same module**. Splitting them
allows a state where the page references images that were never generated: the
README links fine and only the pictures are broken.

File names are derived from the **RLE file name (the slug)**, not the display
name. Deriving them from a name like `Kok's galaxy` makes collisions depend on
how punctuation happens to be stripped.
"""

from __future__ import annotations

import pathlib

from game_of_life.config import Options
from game_of_life.evolve import sequence, slice_range
from game_of_life.patterns import by_category
from game_of_life.render import SizeReport, bake, bake_static, size_report
from game_of_life.rle import Pattern
from game_of_life.rules import RULES
from game_of_life.theme import theme_of

ARTEFACT_DIR = "patterns"
PATTERN_SOURCE_DIR = "../src/game_of_life/assets/patterns"

CATEGORY_TITLES = {
    "still-life": ("Still lifes", "Patterns that never change. Every live cell has "
                   "exactly two or three live neighbours, so nothing dies, and no empty "
                   "cell has exactly three, so nothing is born."),
    "oscillator": ("Oscillators", "Patterns that return to their starting shape after a "
                   "fixed number of generations, without moving. The number is the period."),
    "spaceship": ("Spaceships", "Patterns that return to their starting shape in a "
                  "different place. They are the only way information travels in Life."),
    "gun": ("Guns", "Patterns that emit spaceships forever, so the population grows "
            "without limit. Note the boundary each one declares — on a wrapping board a "
            "gun is eventually destroyed by its own output."),
    "methuselah": ("Methuselahs", "Small patterns that stay chaotic for a very long time "
                   "before settling. The record holders start from fewer than ten cells."),
    "misc": ("Everything else", "Puffers that move and leave debris behind them, a "
             "reflector that turns a passing glider, collisions, unbounded growth from a "
             "single row — patterns whose behaviour does not fit the categories above."),
}

INTRO = """# Pattern gallery

Every pattern below is a single self-contained SVG. Download it, drop it into a
README or a slide, and it plays with no scripts and no external requests.

## The rules

Conway's Game of Life runs on a grid where each cell is alive or dead. What
happens next depends only on how many of a cell's **eight neighbours** are alive:

| Cell | Live neighbours | Next generation |
|---|---|---|
| dead | exactly 3 | **alive** — a birth |
| alive | 2 or 3 | **alive** — it survives |
| alive | 0 or 1 | dead — too sparse |
| alive | 4 or more | dead — too crowded |

Every cell updates at the same instant. That simultaneity is the whole game: if
you updated cells one at a time you would get something else entirely.

Nobody plays Life. You choose a starting arrangement, and everything after that
is already decided.

## Reading this page

Each pattern shows its animation, its behaviour, and who first found it. The
board size and the boundary condition are part of the pattern, not the renderer:
a pattern that flies off the edge behaves differently on a board whose edges
wrap. Where an animation would be unwelcome, a **static** link gives the first
frame as a still image — useful if you prefer reduced motion.
"""


def _frames(pattern: Pattern, rule_name: str):
    rule = RULES[rule_name]
    run = sequence(pattern.to_board(), rule, limit=pattern.generations)
    return slice_range(run, pattern.frame_range), rule


def build(patterns: tuple[Pattern, ...], *, out_dir: pathlib.Path,
          options: Options) -> list[SizeReport]:
    """Write four files per pattern and return the size reports."""
    target = pathlib.Path(out_dir) / ARTEFACT_DIR
    target.mkdir(parents=True, exist_ok=True)
    reports: list[SizeReport] = []
    for pattern in patterns:
        frames, rule = _frames(pattern, options.rule)
        for mode in ("light", "dark"):
            theme = theme_of(mode)
            pairs = (
                (f"{pattern.slug}-{mode}.svg",
                 bake(frames, rule=rule, theme=theme, options=options, title=pattern.name)),
                (f"{pattern.slug}-{mode}-static.svg",
                 bake_static(frames[0], rule=rule, theme=theme, options=options,
                             title=f"{pattern.name} (first frame)")),
            )
            for name, data in pairs:
                (target / name).write_bytes(data)
                reports.append(size_report(f"{ARTEFACT_DIR}/{name}", data,
                                           options.budget_bytes))
    return reports


def page(patterns: tuple[Pattern, ...]) -> str:
    """The contents of `docs/patterns.md`. Deterministic."""
    out = [INTRO]
    for category, group in by_category(patterns).items():
        title, blurb = CATEGORY_TITLES[category]
        out.append(f"\n## {title} (`{category}`)\n\n{blurb}\n")
        for p in group:
            attribution = f" — {p.discovered}" if p.discovered and p.discovered != "—" else ""
            out.append(
                f"\n### {p.name}{attribution}\n\n"
                f'<picture>\n'
                f'  <source media="(prefers-color-scheme: dark)" '
                f'srcset="{ARTEFACT_DIR}/{p.slug}-dark.svg">\n'
                f'  <img src="{ARTEFACT_DIR}/{p.slug}-light.svg" alt="{p.name}">\n'
                f"</picture>\n\n"
                f"{p.explanation}\n\n"
                f"Board {p.board[0]}×{p.board[1]}, {p.boundary} boundary. "
                f"[Download the pattern]({PATTERN_SOURCE_DIR}/{p.slug}.rle) · "
                f"Still image for reduced motion: "
                f"[light]({ARTEFACT_DIR}/{p.slug}-light-static.svg) · "
                f"[dark]({ARTEFACT_DIR}/{p.slug}-dark-static.svg)\n"
            )
    return "".join(out)
