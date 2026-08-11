"""Unit tests for board.py.

Primary failure modes:
- **Frozen but not immutable**: a dataclass's frozen only prevents rebinding an
  attribute. Holding a dict in `levels` lets the contents change and drops
  hashability. Cycle detection needs a set of "states already seen", so being
  hashable is itself a functional requirement.
- **Order leaks into the output bytes**: if iteration order comes from a set or
  dict, the same board emits different bytes. The canonical order is guaranteed
  by the type.
- **Confusing the boundary conditions**: swapping torus for fixed leaves the
  board running either way. A torus narrower than three degenerates, counting
  the same cell as a neighbour twice.
"""

from __future__ import annotations

import pytest

from game_of_life.board import Board, neighbour_counts


def board(levels, w=5, h=5, boundary="torus"):
    return Board.of(width=w, height=h, boundary=boundary, levels=levels)


# ------------------------------------------------- canonical form and immutability

def test_levels_are_stored_in_ascending_y_then_x():
    b = board({(3, 1): 1, (0, 0): 1, (1, 1): 1, (2, 0): 1})
    assert b.levels == (((0, 0), 1), ((2, 0), 1), ((1, 1), 1), ((3, 1), 1))


def test_two_boards_built_from_differently_ordered_input_are_equal():
    assert board({(0, 0): 1, (1, 1): 2}) == board({(1, 1): 2, (0, 0): 1})


def test_a_board_is_hashable_and_equal_boards_hash_equally():
    """The precondition for cycle detection holding seen states in a set."""
    a, b = board({(0, 0): 1, (1, 1): 2}), board({(1, 1): 2, (0, 0): 1})
    assert hash(a) == hash(b)
    assert len({a, b}) == 1


def test_boards_that_differ_only_in_level_are_not_equal():
    assert board({(0, 0): 1}) != board({(0, 0): 2})


def test_a_board_cannot_be_mutated_after_construction():
    b = board({(0, 0): 1})
    with pytest.raises((AttributeError, TypeError)):
        b.levels = ()  # type: ignore[misc]
    with pytest.raises(TypeError):
        b.levels[0] = ((9, 9), 1)  # type: ignore[index]


def test_a_zero_or_negative_level_is_rejected_rather_than_stored():
    """Level 0 means dead and must never sit on the board: it corrupts the live count."""
    with pytest.raises(ValueError):
        board({(0, 0): 0})
    with pytest.raises(ValueError):
        board({(0, 0): -1})


def test_a_cell_outside_the_board_is_rejected():
    with pytest.raises(ValueError):
        board({(5, 0): 1})
    with pytest.raises(ValueError):
        board({(0, -1): 1})


def test_an_unknown_boundary_is_rejected_naming_the_allowed_values():
    with pytest.raises(ValueError, match="torus"):
        board({(0, 0): 1}, boundary="wrap-around")


def test_dimensions_below_three_are_rejected():
    """A torus narrower than three counts a cell twice and destroys the rule's meaning."""
    with pytest.raises(ValueError):
        board({(0, 0): 1}, w=2, h=5)


# ---------------------------------------------------------------- neighbourhoods

def test_neighbours_are_counted_by_presence_not_by_level():
    """A level-4 cell still counts as one. Getting this wrong changes only the decay rule."""
    strong = neighbour_counts(board({(1, 1): 4, (2, 1): 4, (3, 1): 4}))
    weak = neighbour_counts(board({(1, 1): 1, (2, 1): 1, (3, 1): 1}))
    assert strong == weak


def test_a_lone_cell_gives_each_of_its_eight_neighbours_a_count_of_one():
    counts = neighbour_counts(board({(2, 2): 1}))
    assert sorted(counts.values()) == [1] * 8
    assert (2, 2) not in counts


def test_a_cell_never_counts_itself():
    counts = neighbour_counts(board({(2, 2): 1, (2, 3): 1}))
    assert counts[(2, 2)] == 1


def test_torus_wraps_at_every_edge():
    counts = neighbour_counts(board({(0, 0): 1}))
    assert counts[(4, 4)] == 1
    assert counts[(4, 0)] == 1
    assert counts[(0, 4)] == 1


def test_fixed_boundary_does_not_wrap():
    counts = neighbour_counts(board({(0, 0): 1}, boundary="fixed"))
    assert (4, 4) not in counts
    assert sorted(counts.values()) == [1, 1, 1]


def test_the_same_board_under_the_two_boundaries_differs_at_the_edge():
    cells = {(0, 0): 1, (0, 1): 1, (0, 2): 1}
    assert neighbour_counts(board(cells)) != neighbour_counts(board(cells, boundary="fixed"))


def test_an_empty_board_has_no_neighbour_counts():
    assert neighbour_counts(board({})) == {}


# ---------------------------------------------------------------- derived values

def test_live_count_reports_the_number_of_cells_not_the_sum_of_levels():
    assert board({(0, 0): 4, (1, 0): 3}).live_count == 2


def test_density_is_live_cells_over_board_area():
    assert board({(0, 0): 1, (1, 0): 1}, w=5, h=4).density == pytest.approx(2 / 20)


def test_an_empty_board_has_zero_density_rather_than_dividing_by_zero():
    assert board({}).density == 0.0


def test_clamped_lowers_every_level_to_the_given_maximum():
    b = board({(0, 0): 4, (1, 0): 2, (2, 0): 1})
    assert sorted(v for _, v in b.clamped(1).levels) == [1, 1, 1]


def test_clamped_leaves_levels_already_within_range_untouched():
    b = board({(0, 0): 2, (1, 0): 1})
    assert b.clamped(4) == b


def test_clamped_rejects_a_maximum_below_one():
    with pytest.raises(ValueError):
        board({(0, 0): 1}).clamped(0)
