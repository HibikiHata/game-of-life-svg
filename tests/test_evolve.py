"""Unit tests for evolve.py.

Primary failure modes:
- **Reporting a period that was never observed**: treating a digest collision
  as "found a cycle" bakes a loop that jumps at the seam. Identity is confirmed
  by comparing the boards.
- **Special-casing the empty board so range=cycle is zero frames**: the
  renderer rejects an empty sequence, so returning period=0 here always fails
  downstream.
- **A silent fallback**: if falling back to head is not recorded, an artefact
  that promised a seamless loop ships with a seam and says nothing.
- **Measurements rotting**: the generation at which a gun destroys itself on a
  torus is evidence that the boundary is implemented correctly. If that number
  moves after a change, the implementation broke.
"""

from __future__ import annotations

import pytest

from game_of_life.board import Board
from game_of_life.evolve import Run, sequence, slice_range
from game_of_life.rules import RULES
from tests.fixtures import GOSPER_GUN_CORE, core_cells, gun_cells

STANDARD = RULES["standard"]
DECAY = RULES["decay"]


def b(levels, w=8, h=8, boundary="torus"):
    return Board.of(width=w, height=h, boundary=boundary, levels=levels)


BLINKER = {(3, 2): 1, (3, 3): 1, (3, 4): 1}
BLOCK = {(2, 2): 1, (3, 2): 1, (2, 3): 1, (3, 3): 1}


# ---------------------------------------------------------------- determinism

def test_the_same_inputs_produce_the_same_sequence():
    a = sequence(b(BLINKER), STANDARD, limit=20)
    c = sequence(b(BLINKER), STANDARD, limit=20)
    assert a.frames == c.frames


def test_the_input_board_is_never_mutated():
    board = b(BLINKER)
    before = board.levels
    sequence(board, STANDARD, limit=20)
    assert board.levels == before


def test_frame_zero_is_the_input_board():
    board = b(BLINKER)
    assert sequence(board, STANDARD, limit=20).frames[0] == board


# ---------------------------------------------------------------- cycle detection

def test_a_blinker_reports_period_two():
    run = sequence(b(BLINKER), STANDARD, limit=20)
    assert (run.transient, run.period) == (0, 2)


def test_a_still_life_reports_period_one():
    run = sequence(b(BLOCK), STANDARD, limit=20)
    assert run.period == 1


def test_an_empty_board_reports_period_one_and_flags_itself():
    """An empty board is a still life too; period 0 would make cycle zero frames."""
    run = sequence(b({(0, 0): 1}), STANDARD, limit=20)
    assert run.stopped_empty is True
    assert run.period == 1
    assert run.frames[-1].live_count == 0


def test_no_cycle_within_the_limit_reports_none_rather_than_a_false_period():
    run = sequence(b(gun_cells(), w=60, h=40, boundary="fixed"), STANDARD, limit=40)
    assert run.period is None
    assert len(run.frames) == 40


def test_a_digest_collision_cannot_fabricate_a_cycle():
    """The digest only proposes; identity is confirmed on the boards themselves."""
    run = sequence(b(gun_cells(), w=60, h=40, boundary="fixed"), STANDARD,
                   limit=60, digest=lambda board: b"same-for-everything")
    assert run.period is None, "a colliding digest fabricated a period"


def test_the_reported_period_actually_holds_on_the_frames():
    run = sequence(b(BLINKER), STANDARD, limit=20)
    assert run.frames[run.transient] == run.frames[run.transient + run.period]


def test_generation_limit_bounds_the_frame_count():
    assert len(sequence(b(gun_cells(), w=60, h=40, boundary="fixed"),
                        STANDARD, limit=15).frames) == 15


@pytest.mark.parametrize("limit", [0, -1])
def test_a_limit_below_one_is_rejected(limit):
    with pytest.raises(ValueError):
        sequence(b(BLINKER), STANDARD, limit=limit)


# ---------------------------------------------------------------- range

def test_cycle_emits_exactly_the_cycle():
    run = sequence(b(BLINKER), STANDARD, limit=20)
    frames = slice_range(run, "cycle")
    assert len(frames) == 2
    assert frames[0] == run.frames[run.transient]


def test_full_emits_generation_zero_through_the_end_of_the_first_cycle():
    run = sequence(b(BLINKER), STANDARD, limit=20)
    assert len(slice_range(run, "full")) == run.transient + run.period


def test_head_emits_the_first_limit_generations():
    run = sequence(b(gun_cells(), w=60, h=40, boundary="fixed"), STANDARD, limit=25)
    assert len(slice_range(run, "head")) == 25


def test_cycle_without_a_detected_cycle_falls_back_and_says_so():
    """Falling back to head silently would break the seamless-loop promise."""
    run = sequence(b(gun_cells(), w=60, h=40, boundary="fixed"), STANDARD, limit=30)
    frames = slice_range(run, "cycle")
    assert len(frames) == 30
    assert run.fallback is not None
    assert "cycle" in run.fallback


def test_no_fallback_is_recorded_when_the_range_was_honoured():
    run = sequence(b(BLINKER), STANDARD, limit=20)
    slice_range(run, "cycle")
    assert run.fallback is None


def test_range_changes_only_which_frames_are_emitted():
    """Taken from the same Run, the frames themselves do not depend on the range."""
    run = sequence(b(BLINKER), STANDARD, limit=20)
    cycle, full = slice_range(run, "cycle"), slice_range(run, "full")
    assert cycle[0] in full
    assert all(f in run.frames for f in cycle + full)


def test_an_unknown_range_is_rejected():
    run = sequence(b(BLINKER), STANDARD, limit=20)
    with pytest.raises(ValueError, match="cycle"):
        slice_range(run, "tail")


def test_a_cycle_slice_is_never_empty():
    """Even for an empty board, cycle must never be zero frames long."""
    run = sequence(b({(0, 0): 1}), STANDARD, limit=20)
    assert len(slice_range(run, "cycle")) >= 1


# ---------------------------------------------------------------- pinned measurements

@pytest.mark.parametrize("w,h,expected", [(60, 40, 180), (80, 60, 270), (120, 120, 480)])
def test_a_gun_on_a_torus_destroys_itself_at_the_measured_generation(w, h, expected):
    """Measured 2026-08-10. A larger board only delays it; it always breaks.

    If this number moves, either the boundary or the rule implementation changed.
    """
    run = sequence(b(gun_cells(), w=w, h=h), STANDARD, limit=expected + 60)
    intact = gun_cells()
    broke = next(i for i, f in enumerate(run.frames)
                 if i and i % 30 == 0 and core_cells(f.as_map()) != core_cells(intact))
    assert broke == expected


def test_a_gun_on_a_fixed_boundary_keeps_firing():
    """The same gun and the same rule; only the boundary decides the outcome.

    It was measured intact at 6,000 generations, but the test stops at 1,000 —
    far enough from the 180 at which the torus version breaks.
    """
    run = sequence(b(gun_cells(), w=60, h=40, boundary="fixed"), STANDARD, limit=1000)
    assert core_cells(run.frames[-1].as_map()) != {}
    for i in range(0, 1000, 30):
        assert core_cells(run.frames[i].as_map()) == core_cells(gun_cells()), f"generation {i}"


def test_a_dense_board_dies_under_standard_but_is_sustained_by_decay():
    """Pin, at engine level, the reason decay is the grass default.

    This test first tried to assert "the standard rule kills 80 per cent in the
    first generation (120 -> 24)", but **that turned out to be a property of the
    real calendar**, not of the rule. A GitHub calendar stacks weekdays
    vertically and wraps by week, so a run of active days extends **down a
    column** and forms a dense rectangle. The real data contains runs of 46, 33
    and 18 days; the 46-day run fills about seven rows by seven columns, and the
    cells inside it have all eight neighbours alive, so they die of overcrowding
    together. Uniform random data at the same density has no such structure and
    *grows* instead. Measured 2026-08-10:

        uniform random, 120 cells  standard 120->136->115  decay 120->180->214 (peak 235)
        real calendar,  120 cells  standard 120-> 24-> 38  decay 120->138->145 (peak 199)

    What holds regardless of the board's structure is the other claim: standard
    collapses within 40 generations while decay sustains the population. The
    first-generation collapse is pinned where the real calendar fixture lives.
    """
    import random
    rnd = random.Random("dense")
    cells = rnd.sample([(x, y) for x in range(53) for y in range(7)], 120)
    board = b({p: 1 for p in cells}, w=53, h=7)

    std = sequence(board, STANDARD, limit=41)
    assert std.frames[40].live_count <= 10, "the standard rule did not collapse"

    dec = sequence(board.with_levels({p: 4 for p in cells}), DECAY, limit=41)
    assert dec.frames[40].live_count > 100, "decay did not sustain the population"


def test_a_board_whose_levels_exceed_the_rule_is_rejected_not_silently_clamped():
    """The path where a calendar board (levels 1-4) meets the standard rule (max 1).

    Rounding silently produces a different picture than the one requested, so
    Board.clamped makes it explicit.
    """
    rich = b({(1, 1): 4, (2, 1): 3})
    with pytest.raises(ValueError, match="clamped"):
        sequence(rich, STANDARD, limit=5)
    assert sequence(rich.clamped(1), STANDARD, limit=5).frames
