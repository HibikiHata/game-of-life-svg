"""Unit tests for config.py.

Primary failure modes:
- **An invalid setting silently falls back to a default**: a misspelled preset
  passing as `grass` publishes an artefact nobody asked for. Everything raises
  ValueError instead.
- **The preset definitions drift from the specified constants**: board sizes
  and generation limits are pinned here, because the budget check rests on them.
- **Confusing the budget's unit**: the budget is in gzipped decimal bytes.
  Mistaking it for raw bytes is off by 6x to 30x, since the compression ratio
  is not a constant.
"""

from __future__ import annotations

import dataclasses

import pytest

from game_of_life.config import PRESETS, Options

# Copied by hand from the specified constants table.
EXPECTED_PRESETS = {
    "card": ((48, 27), 400),
    "banner": ((80, 20), 400),
    "square-s": ((50, 50), 300),
    "square-m": ((75, 75), 160),
    "square-l": ((100, 100), 128),
}


# ---------------------------------------------------------------- presets

def test_every_preset_in_the_design_exists_with_its_dimensions_and_limit():
    for name, (size, limit) in EXPECTED_PRESETS.items():
        assert (PRESETS[name].size, PRESETS[name].limit) == (size, limit), name


def test_grass_takes_its_size_from_the_calendar_not_from_a_constant():
    """Week counts vary from 52 to 54. A fixed size would reject a valid response."""
    assert PRESETS["grass"].size is None
    assert PRESETS["grass"].limit == 400


def test_the_registry_holds_exactly_the_six_presets_the_prd_lists():
    assert set(PRESETS) == {"grass", "card", "banner", "square-s", "square-m", "square-l"}


def test_larger_boards_carry_smaller_generation_limits():
    """Holding frames is the only unbounded memory consumer, so the limit falls
    as the area grows."""
    sized = [p for p in PRESETS.values() if p.size]
    ordered = sorted(sized, key=lambda p: p.size[0] * p.size[1])
    limits = [p.limit for p in ordered]
    assert limits == sorted(limits, reverse=True)


# ---------------------------------------------------------------- defaults

def test_defaults_match_the_decisions_the_prd_and_adr_recorded():
    o = Options(preset="grass")
    assert o.rule == "decay"            # standard kills 80% of the board in one step
    assert o.frame_range == "cycle"
    assert o.fps == 10
    assert o.budget_bytes == 256_000    # gzipped decimal bytes


def test_options_are_frozen():
    o = Options(preset="card")
    with pytest.raises(dataclasses.FrozenInstanceError):
        o.fps = 30  # type: ignore[misc]


def test_the_limit_defaults_to_the_preset_cap():
    assert Options(preset="square-l").limit == 128
    assert Options(preset="card").limit == 400


def test_an_explicit_limit_above_the_preset_cap_is_rejected():
    """The cap is what guarantees the budget, so a caller must not exceed it silently."""
    with pytest.raises(ValueError, match="128"):
        Options(preset="square-l", limit=1200)


# ---------------------------------------------------------------- validation

@pytest.mark.parametrize("field,value", [
    ("preset", "sqaure-s"),
    ("rule", "B3/S23"),
    ("frame_range", "head:120"),
    ("frame_range", "cyle"),
])
def test_an_invalid_value_is_rejected_rather_than_defaulted(field, value):
    with pytest.raises(ValueError, match=field.replace("_", ".")):
        Options(**{"preset": "card", field: value})


def test_the_error_names_the_allowed_values():
    with pytest.raises(ValueError) as exc:
        Options(preset="card", frame_range="tail")
    assert "cycle" in str(exc.value) and "full" in str(exc.value) and "head" in str(exc.value)


@pytest.mark.parametrize("limit", [0, -1])
def test_a_limit_below_one_is_rejected(limit):
    with pytest.raises(ValueError):
        Options(preset="card", limit=limit)


@pytest.mark.parametrize("fps", [0, -5])
def test_a_non_positive_fps_is_rejected(fps):
    with pytest.raises(ValueError):
        Options(preset="card", fps=fps)


def test_a_non_positive_budget_is_rejected():
    with pytest.raises(ValueError):
        Options(preset="card", budget_bytes=0)


def test_frame_range_head_is_a_plain_value_with_no_embedded_number():
    """The `head:N` string form is gone. The generation count lives in `limit`."""
    o = Options(preset="card", frame_range="head", limit=60)
    assert o.frame_range == "head"
    assert o.limit == 60
