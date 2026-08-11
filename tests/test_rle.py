"""Unit tests for rle.py.

Primary failure modes:
- **Failing to read standard RLE**: the `x = , y = , rule =` header and the
  `#N` / `#O` lines are part of the standard. Rejecting them makes every file
  from an external collection unusable, and "stored in the standard format"
  becomes a claim with nothing behind it.
- **Silently skipping an unknown token**: a cell that is not read simply
  vanishes from the picture without an error, and a subtly different pattern
  ships.
- **The header rule disagreeing with the run-time rule**: silently preferring
  one means the gallery can say "this pattern is B3/S23" while running it under
  something else.
"""

from __future__ import annotations

import pytest

from game_of_life.rle import RleError, parse_rle

BLINKER = """#N Blinker
#O John Conway, 1970
#C category: oscillator
#C board: 16x16
#C boundary: torus
#C frame_range: cycle
#C generations: 8
#C offset: 6,7
#C explanation: The smallest oscillator. Three cells in a row flip between
#C explanation: horizontal and vertical every generation.
x = 3, y = 1, rule = B3/S23
3o!
"""


def parse(text=BLINKER, **replace):
    for old, new in replace.items():
        text = text.replace(old.replace("_", " "), new)
    return parse_rle(text)


# ---------------------------------------------------------------- body parsing

def test_a_row_of_three_becomes_three_cells():
    assert parse().cells == frozenset({(0, 0), (1, 0), (2, 0)})


def test_run_counts_expand():
    p = parse_rle(BLINKER.replace("x = 3, y = 1", "x = 5, y = 1").replace("3o!", "2b3o!"))
    assert p.cells == frozenset({(2, 0), (3, 0), (4, 0)})


def test_dollar_starts_a_new_row():
    p = parse_rle(BLINKER.replace("x = 3, y = 1", "x = 3, y = 2").replace("3o!", "o$2bo!"))
    assert p.cells == frozenset({(0, 0), (2, 1)})


def test_a_run_count_before_dollar_skips_rows():
    """`o3$o!` puts cells on rows 0 and 3, so the height is 4."""
    p = parse_rle(BLINKER.replace("x = 3, y = 1", "x = 3, y = 4").replace("3o!", "o3$o!"))
    assert p.cells == frozenset({(0, 0), (0, 3)})


def test_content_after_the_terminator_is_ignored():
    p = parse_rle(BLINKER.replace("3o!", "3o!\nthis is a trailing note"))
    assert len(p.cells) == 3


def test_the_body_may_span_multiple_lines():
    p = parse_rle(BLINKER.replace("x = 3, y = 1", "x = 3, y = 2").replace("3o!", "o$\n2bo!"))
    assert p.cells == frozenset({(0, 0), (2, 1)})


def test_an_unknown_token_is_rejected_rather_than_skipped():
    with pytest.raises(RleError, match="z"):
        parse_rle(BLINKER.replace("3o!", "3ozo!"))


# ---------------------------------------------------------------- standard header

def test_the_standard_header_is_accepted_and_its_extents_recorded():
    p = parse()
    assert p.extents == (3, 1)


def test_the_header_rule_is_recorded():
    assert parse().header_rule == "B3/S23"


def test_a_header_rule_may_be_lowercase():
    assert parse_rle(BLINKER.replace("rule = B3/S23", "rule = b3/s23")).header_rule == "b3/s23"


def test_a_missing_header_is_rejected():
    with pytest.raises(RleError, match="header"):
        parse_rle(BLINKER.replace("x = 3, y = 1, rule = B3/S23\n", ""))


def test_n_and_o_comments_become_name_and_attribution():
    p = parse()
    assert p.name == "Blinker"
    assert p.discovered == "John Conway, 1970"


def test_cells_outside_the_declared_extents_are_rejected():
    with pytest.raises(RleError, match="outside"):
        parse_rle(BLINKER.replace("x = 3, y = 1", "x = 2, y = 1"))


# ---------------------------------------------------------------- metadata

def test_every_required_key_is_read():
    p = parse()
    assert (p.category, p.boundary, p.frame_range) == ("oscillator", "torus", "cycle")
    assert (p.board, p.generations, p.offset) == ((16, 16), 8, (6, 7))


def test_multi_line_explanation_lines_are_joined():
    assert "flip between horizontal and vertical" in parse().explanation


@pytest.mark.parametrize("key", ["category", "board", "boundary", "frame_range",
                                 "generations", "offset"])
def test_a_missing_required_key_is_rejected_naming_it(key):
    text = "\n".join(l for l in BLINKER.splitlines() if not l.startswith(f"#C {key}:"))
    with pytest.raises(RleError, match=key):
        parse_rle(text + "\n")


def test_a_missing_explanation_is_rejected():
    """Every pattern needs an explanation; none may ship without one."""
    text = "\n".join(l for l in BLINKER.splitlines()
                     if not l.startswith("#C explanation:"))
    with pytest.raises(RleError, match="explanation"):
        parse_rle(text + "\n")


def test_an_unknown_category_is_rejected():
    with pytest.raises(RleError, match="category"):
        parse_rle(BLINKER.replace("category: oscillator", "category: interesting"))


def test_an_unknown_boundary_is_rejected():
    with pytest.raises(RleError, match="boundary"):
        parse_rle(BLINKER.replace("boundary: torus", "boundary: donut"))


def test_an_unknown_frame_range_is_rejected():
    with pytest.raises(RleError, match="frame_range"):
        parse_rle(BLINKER.replace("frame_range: cycle", "frame_range: tail"))


def test_core_is_optional_and_absent_by_default():
    assert parse().core is None


def test_core_is_read_when_present():
    p = parse_rle(BLINKER.replace("#C offset: 6,7", "#C offset: 6,7\n#C core: 0,0,26,9"))
    assert p.core == (0, 0, 26, 9)


def test_a_gun_without_a_core_is_rejected():
    """Without a core there is no intactness check, so a self-destroying gun could ship."""
    with pytest.raises(RleError, match="core"):
        parse_rle(BLINKER.replace("category: oscillator", "category: gun"))


# ---------------------------------------------------------------- placement on the board

def test_cells_do_not_fit_the_declared_board_after_offset():
    with pytest.raises(RleError, match="do not fit"):
        parse_rle(BLINKER.replace("#C board: 16x16", "#C board: 8x8")
                  .replace("#C offset: 6,7", "#C offset: 7,7"))


def test_a_board_smaller_than_the_pattern_is_rejected():
    with pytest.raises(RleError):
        parse_rle(BLINKER.replace("#C board: 16x16", "#C board: 3x3")
                  .replace("#C offset: 6,7", "#C offset: 2,2"))


def test_to_board_places_the_pattern_at_its_offset():
    board = parse().to_board()
    assert (board.width, board.height) == (16, 16)
    assert set(dict(board.levels)) == {(6, 7), (7, 7), (8, 7)}


def test_to_board_uses_the_rules_max_level_so_decay_patterns_start_strong():
    board = parse().to_board(level=4)
    assert set(dict(board.levels).values()) == {4}


def test_a_gun_without_a_core_period_is_rejected():
    """Without the period the comparison drifts out of phase and an intact gun mismatches."""
    text = BLINKER.replace("category: oscillator", "category: gun").replace(
        "#C offset: 6,7", "#C offset: 6,7\n#C core: 0,0,3,1")
    with pytest.raises(RleError, match="core_period"):
        parse_rle(text)


def test_core_period_is_read_when_present():
    text = BLINKER.replace("category: oscillator", "category: gun").replace(
        "#C offset: 6,7", "#C offset: 6,7\n#C core: 0,0,3,1\n#C core_period: 30")
    assert parse_rle(text).core_period == 30


def test_core_period_is_absent_for_non_guns():
    assert parse().core_period is None
