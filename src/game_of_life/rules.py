"""The Life rules.

A rule is a pure function `(own level, live neighbours) -> next level`. It
**cannot reach the board at all.** That is what backs the claim that adding a
new rule costs one table entry, and the claim is checked for real by
test_rules.py::test_a_new_rule_needs_only_a_table_entry.

Neighbours are counted by presence, never by level. Decay levels affect only
the drawing and the lifetime, never the neighbour arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

MAX_NEIGHBOURS = 8


@dataclass(frozen=True)
class Rule:
    """One rule. `max_level` belongs to the Rule, not to the Board."""

    name: str
    max_level: int
    next_level: Callable[[int, int], int]


def _checked(level: int, neighbours: int, max_level: int) -> None:
    """Refuse to paper over a caller's defect.

    There are only eight neighbours, so nine is unreachable, and a level cannot
    leave the rule's range. Reaching either means the board or the neighbour
    count is broken.
    """
    if not 0 <= neighbours <= MAX_NEIGHBOURS:
        raise ValueError(
            f"live neighbour count out of range: {neighbours} (0..{MAX_NEIGHBOURS})"
        )
    if not 0 <= level <= max_level:
        raise ValueError(f"level out of range: {level} (0..{max_level})")


def _standard(level: int, neighbours: int) -> int:
    """B3/S23. A single level of aliveness."""
    _checked(level, neighbours, 1)
    if level == 0:
        return 1 if neighbours == 3 else 0
    return 1 if neighbours in (2, 3) else 0


def _decay(level: int, neighbours: int) -> int:
    """The decay rule: four levels of aliveness plus death.

    Two properties make it work. **Birth happens at the maximum level**, so a
    new cell can survive four generations of failure. **Surviving raises the
    level**, so a stable region saturates rather than merely persisting.
    Together they let a dense board recover instead of collapsing (measured:
    120 -> 68 -> 176 live cells).
    """
    _checked(level, neighbours, 4)
    if level == 0:
        return 4 if neighbours == 3 else 0
    if neighbours in (2, 3):
        return min(4, level + 1)
    return level - 1


RULES: Mapping[str, Rule] = {
    "standard": Rule(name="standard", max_level=1, next_level=_standard),
    "decay": Rule(name="decay", max_level=4, next_level=_decay),
}
