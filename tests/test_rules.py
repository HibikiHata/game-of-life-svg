"""Unit tests for rules.py.

Primary failure modes:
- **A shifted transition table passes silently**: getting the birth level or
  the survival increment wrong leaves the board running, so no amount of
  looking at it helps. The table is compared cell by cell.
- **Counting neighbours by level**: if a level-2 cell counted as two under the
  decay rule, its behaviour would diverge from the standard rule while both
  still looked plausible.
- **A rule that can see the board**: if `next_level` could reach the board,
  adding a new rule would no longer cost one table entry.
"""

from __future__ import annotations

import inspect

import pytest

from game_of_life.rules import RULES, Rule

# Copied by hand from the specified transition table. Never derived from the
# implementation.
STANDARD_TABLE = {
    0: [0, 0, 0, 1, 0, 0, 0, 0, 0],
    1: [0, 0, 1, 1, 0, 0, 0, 0, 0],
}
DECAY_TABLE = {
    0: [0, 0, 0, 4, 0, 0, 0, 0, 0],
    1: [0, 0, 2, 2, 0, 0, 0, 0, 0],
    2: [1, 1, 3, 3, 1, 1, 1, 1, 1],
    3: [2, 2, 4, 4, 2, 2, 2, 2, 2],
    4: [3, 3, 4, 4, 3, 3, 3, 3, 3],
}


# ---------------------------------------------------------------- transition table

@pytest.mark.parametrize("level,row", sorted(STANDARD_TABLE.items()))
def test_standard_matches_the_design_table_for_every_neighbour_count(level, row):
    rule = RULES["standard"]
    assert [rule.next_level(level, n) for n in range(9)] == row


@pytest.mark.parametrize("level,row", sorted(DECAY_TABLE.items()))
def test_decay_matches_the_design_table_for_every_neighbour_count(level, row):
    rule = RULES["decay"]
    assert [rule.next_level(level, n) for n in range(9)] == row


def test_max_level_belongs_to_the_rule():
    """A Board has no max_level. The Rule is its only owner."""
    assert RULES["standard"].max_level == 1
    assert RULES["decay"].max_level == 4


def test_a_cell_is_born_at_max_level_under_decay():
    """If birth started at 1, a new cell would die after one bad generation and
    the board would never recover."""
    assert RULES["decay"].next_level(0, 3) == RULES["decay"].max_level


def test_a_surviving_cell_rises_and_is_capped_under_decay():
    assert RULES["decay"].next_level(1, 2) == 2
    assert RULES["decay"].next_level(4, 3) == 4


def test_a_failing_cell_drops_one_level_and_dies_only_from_level_one():
    assert RULES["decay"].next_level(3, 8) == 2
    assert RULES["decay"].next_level(1, 8) == 0


def test_standard_never_returns_a_level_above_one():
    rule = RULES["standard"]
    assert {rule.next_level(l, n) for l in range(2) for n in range(9)} <= {0, 1}


# ---------------------------------------------------------------- structure

def test_next_level_takes_only_a_level_and_a_neighbour_count():
    """Being unable to see the board is what makes a new rule one table entry."""
    for name, rule in RULES.items():
        params = list(inspect.signature(rule.next_level).parameters)
        assert len(params) == 2, f"{name}: {params}"


def test_rules_are_frozen():
    with pytest.raises((AttributeError, TypeError)):
        RULES["decay"].max_level = 9  # type: ignore[misc]


def test_registry_holds_exactly_the_two_rules_the_prd_requires():
    assert set(RULES) == {"standard", "decay"}


def test_rule_name_matches_its_registry_key():
    for key, rule in RULES.items():
        assert rule.name == key


def test_unknown_neighbour_count_is_rejected_rather_than_silently_wrapped():
    """There are eight neighbours, so nine is unreachable: it means a caller defect."""
    with pytest.raises(ValueError):
        RULES["decay"].next_level(1, 9)
    with pytest.raises(ValueError):
        RULES["decay"].next_level(1, -1)


def test_level_outside_the_rules_range_is_rejected():
    with pytest.raises(ValueError):
        RULES["standard"].next_level(2, 3)
    with pytest.raises(ValueError):
        RULES["decay"].next_level(5, 3)


def test_a_new_rule_needs_only_a_table_entry():
    """Check the extensibility claim for real: HighLife must be addable in one line."""
    highlife = Rule(
        name="highlife",
        max_level=1,
        next_level=lambda level, n: 1 if (level == 0 and n in (3, 6)) or (level and n in (2, 3)) else 0,
    )
    assert highlife.next_level(0, 6) == 1      # the birth rule unique to HighLife
    assert RULES["standard"].next_level(0, 6) == 0
