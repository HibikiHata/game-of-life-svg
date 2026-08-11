"""How the presets are reached, and whether they stay within budget.

Primary failure modes:
- **Dead settings**: this actually happened — the preset dimensions were
  asserted by tests while no code path built a board from them. A reader
  assumes they work, the tests keep guarding the numbers, and nobody ever runs
  them. **The reachable path itself is under test here.**
- **A budget only ever measured by a throwaway script**: if nothing
  re-verifies the numbers, changing the renderer silently breaks the budget of
  a preset no path exercises.
- **Passing a preset has no effect**: if the board dimensions do not change,
  the same animation comes out and the argument was silently ignored.
"""

from __future__ import annotations

import pytest

from game_of_life.config import PRESETS, Options
from game_of_life.evolve import sequence, slice_range
from game_of_life.patterns import load_all
from game_of_life.render import bake, size_report
from game_of_life.rules import RULES
from game_of_life.theme import theme_of
from game_of_life.compose import board_for_preset

PATTERNS = {p.slug: p for p in load_all()}
SIZED = sorted(name for name, p in PRESETS.items() if p.size)


# ---------------------------------------------------------------- reachability

@pytest.mark.parametrize("preset", SIZED)
def test_a_pattern_can_be_placed_on_any_sized_preset(preset):
    board = board_for_preset(PATTERNS["glider"], preset)
    assert (board.width, board.height) == PRESETS[preset].size


def test_the_pattern_keeps_its_cells_when_the_canvas_changes():
    small = board_for_preset(PATTERNS["glider"], "card")
    large = board_for_preset(PATTERNS["glider"], "square-l")
    assert small.live_count == large.live_count == 5


def test_the_pattern_is_centred_on_the_new_canvas():
    board = board_for_preset(PATTERNS["glider"], "square-l")
    xs = [x for (x, _), _ in board.levels]
    ys = [y for (_, y), _ in board.levels]
    assert 45 < sum(xs) / len(xs) < 55
    assert 45 < sum(ys) / len(ys) < 55


def test_the_preset_actually_changes_the_animation():
    """If the dimensions have no effect, the argument was silently ignored."""
    rule = RULES["standard"]
    a = sequence(board_for_preset(PATTERNS["glider"], "card"), rule, limit=60)
    b = sequence(board_for_preset(PATTERNS["glider"], "square-l"), rule, limit=60)
    assert a.frames[-1].levels != b.frames[-1].levels


def test_grass_has_no_size_and_cannot_host_a_pattern():
    """The grass size comes from the calendar and must not be fixed here."""
    with pytest.raises(ValueError, match="grass"):
        board_for_preset(PATTERNS["glider"], "grass")


def test_a_pattern_too_large_for_the_canvas_is_rejected():
    """simkin-gun is 33x21; banner is 80x20, so it is not tall enough."""
    with pytest.raises(ValueError, match="does not fit"):
        board_for_preset(PATTERNS["simkin-gun"], "banner")


def test_an_unknown_preset_is_rejected():
    with pytest.raises(ValueError):
        board_for_preset(PATTERNS["glider"], "enormous")


def test_the_boundary_comes_from_the_pattern_not_the_preset():
    assert board_for_preset(PATTERNS["gosper-gun"], "square-l").boundary == "fixed"
    assert board_for_preset(PATTERNS["glider"], "square-l").boundary == "torus"


# ---------------------------------------------------------------- budget

@pytest.mark.parametrize("preset", SIZED)
def test_every_sized_preset_stays_within_budget_at_its_full_frame_count(preset):
    """Re-verify the constant table's numbers for real.

    Measured under the heaviest condition: a methuselah that grows dense, run
    under the decay rule (which emits paths for four colours) up to that
    preset's generation limit.
    """
    rule = RULES["decay"]
    board = board_for_preset(PATTERNS["r-pentomino"], preset).clamped(rule.max_level)
    board = board.with_levels({p: rule.max_level for p, _ in board.levels})
    options = Options(preset=preset, rule="decay", frame_range="head")
    frames = slice_range(sequence(board, rule, limit=options.limit), "head")
    data = bake(frames, rule=rule, theme=theme_of("dark"), options=options,
                title=f"budget probe {preset}")
    report = size_report(f"{preset}.svg", data, options.budget_bytes)
    assert report.within_budget, (
        f"{preset}: {len(frames)} frames gzip to {report.gzipped_bytes}B "
        f"(budget {options.budget_bytes}B)"
    )


@pytest.mark.parametrize("preset", SIZED)
def test_the_generation_limit_bounds_the_frames_actually_baked(preset):
    rule = RULES["decay"]
    board = board_for_preset(PATTERNS["r-pentomino"], preset)
    board = board.with_levels({p: rule.max_level for p, _ in board.levels})
    frames = slice_range(sequence(board, rule, limit=PRESETS[preset].limit), "head")
    assert len(frames) <= PRESETS[preset].limit


def test_larger_canvases_produce_larger_artefacts():
    """The budget table's ordering must match measurement. An inversion means
    either the table or the implementation is wrong."""
    rule = RULES["decay"]
    sizes = {}
    for preset in ("card", "square-s", "square-l"):
        board = board_for_preset(PATTERNS["r-pentomino"], preset)
        board = board.with_levels({p: rule.max_level for p, _ in board.levels})
        options = Options(preset=preset, rule="decay", frame_range="head", limit=120)
        frames = slice_range(sequence(board, rule, limit=120), "head")
        data = bake(frames, rule=rule, theme=theme_of("dark"), options=options, title="t")
        sizes[preset] = size_report(preset, data, options.budget_bytes).gzipped_bytes
    assert sizes["card"] < sizes["square-s"] < sizes["square-l"], sizes
