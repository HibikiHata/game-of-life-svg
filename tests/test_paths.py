"""Unit tests for paths.py.

Primary failure modes:
- **Iteration order leaks into the output**: if the same board emits different
  bytes, both deterministic output and the golden files break — and the picture
  still looks correct.
- **A missed merge**: failing to combine horizontally adjacent cells into one
  rectangle leaves the picture identical and nearly quintuples the byte count.
  Only the budget check can see it.
- **Over-merging**: joining cells that are not adjacent changes the picture.
"""

from __future__ import annotations

import pytest

from game_of_life.paths import run_merged_path


def test_a_single_cell_becomes_one_unit_square():
    assert run_merged_path([(2, 3)]) == "M2 3h1v1h-1z"


def test_horizontally_adjacent_cells_merge_into_one_rectangle():
    assert run_merged_path([(2, 3), (3, 3), (4, 3)]) == "M2 3h3v1h-3z"


def test_a_gap_breaks_the_run():
    assert run_merged_path([(2, 3), (4, 3)]) == "M2 3h1v1h-1zM4 3h1v1h-1z"


def test_cells_on_different_rows_never_merge():
    assert run_merged_path([(2, 3), (2, 4)]) == "M2 3h1v1h-1zM2 4h1v1h-1z"


def test_output_is_ordered_by_row_then_column_regardless_of_input_order():
    a = run_merged_path([(5, 9), (0, 0), (3, 1)])
    b = run_merged_path([(3, 1), (5, 9), (0, 0)])
    assert a == b
    assert a.index("M0 0") < a.index("M3 1") < a.index("M5 9")


def test_an_empty_cell_set_produces_an_empty_path():
    assert run_merged_path([]) == ""


def test_a_set_and_a_list_of_the_same_cells_produce_identical_bytes():
    """Non-deterministic iteration order must not reach the output."""
    cells = [(4, 1), (2, 1), (3, 1), (9, 7)]
    assert run_merged_path(set(cells)) == run_merged_path(sorted(cells))


def test_a_full_row_is_a_single_subpath():
    assert run_merged_path([(x, 0) for x in range(10)]) == "M0 0h10v1h-10z"


def test_duplicate_cells_do_not_produce_duplicate_subpaths():
    assert run_merged_path([(1, 1), (1, 1)]) == "M1 1h1v1h-1z"


def test_merging_is_measurably_shorter_than_one_subpath_per_cell():
    """Confirm merging works by measuring length, not by looking at the picture."""
    row = [(x, 0) for x in range(40)]
    merged = run_merged_path(row)
    per_cell = "".join(f"M{x} 0h1v1h-1z" for x in range(40))
    assert len(merged) < len(per_cell) / 4


@pytest.mark.parametrize("bad", [(1,), (1, 2, 3), ("a", 1)])
def test_a_malformed_position_is_rejected(bad):
    with pytest.raises((ValueError, TypeError)):
        run_merged_path([bad])
