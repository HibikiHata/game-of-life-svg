"""Integration tests for the pattern library.

Primary failure modes:
- **Shipping the wrong pattern**: a single mistyped character in an RLE still
  parses and still draws. **Only the period changes, and it changes quietly.**
  Two patterns really were broken this way — clock (a still life where the
  period should be 2) and Kok's galaxy (period 16 instead of 8) — and only the
  comparison against documented periods found them. This table is what stops it
  happening again.
- **Shipping a self-destroyed gun**: comparing the core at a phase that is not
  a multiple of the period makes an intact gun look broken. Dropping the
  comparison altogether lets a broken gun through.
- **A budget overrun going unnoticed until publication**: there are four
  artefacts per pattern.
"""

from __future__ import annotations

import collections

import pytest

from game_of_life.config import Options
from game_of_life.evolve import sequence, slice_range
from game_of_life.patterns import MINIMUM_PATTERNS, by_category, load_all
from game_of_life.render import bake, bake_static, size_report
from game_of_life.rle import CATEGORIES, RleError
from game_of_life.rules import RULES
from game_of_life.theme import theme_of

PATTERNS = load_all()
RULE = RULES["standard"]
OPTIONS = Options(preset="card", rule="standard", frame_range="head")

# Periods established in the literature. Never derived from the implementation.
KNOWN_PERIODS = {
    "Blinker": 2, "Toad": 2, "Beacon": 2, "Clock": 2, "Pulsar": 3,
    "Pentadecathlon": 15, "Figure eight": 8, "Kok's galaxy": 8,
}


def frames_of(pattern):
    run = sequence(pattern.to_board(), RULE, limit=pattern.generations)
    return slice_range(run, pattern.frame_range), run


# ---------------------------------------------------------------- coverage

def test_the_library_meets_the_minimum_pattern_count():
    assert len(PATTERNS) >= MINIMUM_PATTERNS


def test_every_category_is_represented():
    assert set(collections.Counter(p.category for p in PATTERNS)) == set(CATEGORIES)


def test_every_pattern_has_a_name_and_an_explanation():
    for p in PATTERNS:
        assert p.name != "(unnamed)", p
        assert len(p.explanation) > 40, p.name


def test_pattern_names_are_unique():
    names = [p.name for p in PATTERNS]
    assert len(names) == len(set(names))


def test_loading_is_deterministic():
    assert [p.name for p in load_all()] == [p.name for p in PATTERNS]


def test_grouping_orders_categories_then_names():
    grouped = by_category(PATTERNS)
    assert list(grouped) == [c for c in CATEGORIES if c in grouped]
    for ps in grouped.values():
        assert [p.name for p in ps] == sorted(p.name for p in ps)


def test_a_broken_pattern_file_names_itself(tmp_path):
    (tmp_path / "broken.rle").write_text("#N x\nnot an rle\n", encoding="utf-8")
    with pytest.raises(RleError, match="broken.rle"):
        load_all(tmp_path)


# ---------------------------------------------------------------- correctness

@pytest.mark.parametrize("name,period", sorted(KNOWN_PERIODS.items()))
def test_a_known_oscillator_has_its_documented_period(name, period):
    """clock and galaxy were both found to be wrong by this check."""
    pattern = next(p for p in PATTERNS if p.name == name)
    run = sequence(pattern.to_board(), RULE, limit=max(pattern.generations, 60))
    assert run.period == period


@pytest.mark.parametrize("pattern", [p for p in PATTERNS if p.category == "still-life"],
                         ids=lambda p: p.name)
def test_a_still_life_never_changes(pattern):
    run = sequence(pattern.to_board(), RULE, limit=20)
    assert run.period == 1


@pytest.mark.parametrize("pattern", [p for p in PATTERNS if p.category == "gun"],
                         ids=lambda p: p.name)
def test_a_gun_keeps_its_core_at_every_phase_aligned_frame(pattern):
    """Without phase alignment even an intact gun mismatches."""
    frames, _ = frames_of(pattern)
    x0, y0, w, h = pattern.core
    ox, oy = pattern.offset

    def core(board):
        return {(x, y) for (x, y), _ in board.levels
                if x0 + ox <= x < x0 + ox + w and y0 + oy <= y < y0 + oy + h}

    base = core(frames[0])
    assert base, "the core is empty: the core rectangle does not cover the pattern"
    for i in range(0, len(frames), pattern.core_period):
        assert core(frames[i]) == base, f"{pattern.name}: the core changed at generation {i}"


# Documented (period, displacement per period) for each spaceship.
# An earlier version tried to stand in "the cell count stays roughly constant",
# but the period-7 Loafer legitimately varies between 20 and 33 cells by phase,
# so the test was the thing that was wrong. Measuring **the definition itself** —
# the same shape reappearing translated after k generations — is correct.
KNOWN_SPACESHIPS = {
    "Glider": (4, (1, 1)),
    "Lightweight spaceship": (4, (-2, 0)),
    "Middleweight spaceship": (4, (-2, 0)),
    "Heavyweight spaceship": (4, (-2, 0)),
    "Loafer": (7, (-1, 0)),
}


def _normalised(board):
    """The shape moved to the origin, together with where it actually was."""
    cells = [pos for pos, _ in board.levels]
    ox, oy = min(c[0] for c in cells), min(c[1] for c in cells)
    return frozenset((x - ox, y - oy) for x, y in cells), (ox, oy)


@pytest.mark.parametrize("pattern", [p for p in PATTERNS if p.category == "spaceship"],
                         ids=lambda p: p.name)
def test_a_spaceship_returns_to_its_own_shape_displaced(pattern):
    """The definition of a spaceship: the same shape reappears elsewhere after k steps."""
    frames, _ = frames_of(pattern)
    shape, origin = _normalised(frames[0])
    for k in range(1, min(30, len(frames))):
        k_shape, k_origin = _normalised(frames[k])
        delta = (k_origin[0] - origin[0], k_origin[1] - origin[1])
        if k_shape == shape and delta != (0, 0):
            assert (k, delta) == KNOWN_SPACESHIPS[pattern.name]
            return
    pytest.fail(f"{pattern.name}: no translated copy of the shape within 30 generations")


# ---------------------------------------------------------------- budget

@pytest.mark.parametrize("pattern", PATTERNS, ids=lambda p: p.name)
def test_every_artefact_for_every_pattern_fits_the_budget(pattern):
    frames, _ = frames_of(pattern)
    for mode in ("light", "dark"):
        theme = theme_of(mode)
        animated = bake(frames, rule=RULE, theme=theme, options=OPTIONS, title=pattern.name)
        static = bake_static(frames[0], rule=RULE, theme=theme, options=OPTIONS,
                             title=pattern.name)
        for label, data in (("animated", animated), ("static", static)):
            r = size_report(f"{pattern.name}-{mode}-{label}", data, OPTIONS.budget_bytes)
            assert r.within_budget, f"{r.path}: gzip {r.gzipped_bytes}B"


def test_the_frame_count_never_exceeds_the_declared_generations():
    for p in PATTERNS:
        frames, _ = frames_of(p)
        assert len(frames) <= p.generations, p.name


def test_every_pattern_produces_at_least_one_frame():
    for p in PATTERNS:
        frames, _ = frames_of(p)
        assert frames, p.name
