"""Unit tests for theme.py.

Primary failure modes:
- **Drifting from the specified constants**: the palettes are pinned here.
  Without that, light and dark could render as different pictures unnoticed.
- **Adjacent levels indistinguishable**: the four decay levels are carried by
  **colour alone**, so information disappears when neighbouring levels do not
  contrast. Giving `contrast_ratio` something real to check is this file's job.
"""

from __future__ import annotations

import pytest

from game_of_life.theme import MODES, Theme, contrast_ratio, theme_of

# Copied by hand from the specified constants table.
EXPECTED = {
    "dark": ("#0d1117", ("#0e4429", "#006d32", "#26a641", "#39d353")),
    "light": ("#ffffff", ("#9be9a8", "#40c463", "#30a14e", "#216e39")),
}


@pytest.mark.parametrize("mode", sorted(EXPECTED))
def test_palette_matches_the_specified_constants(mode):
    t = theme_of(mode)
    assert (t.background, t.levels) == EXPECTED[mode]


def test_both_modes_exist_and_nothing_else():
    assert set(MODES) == {"light", "dark"}


def test_an_unknown_mode_is_rejected_naming_the_allowed_values():
    with pytest.raises(ValueError, match="light"):
        theme_of("sepia")


def test_a_theme_is_frozen():
    with pytest.raises((AttributeError, TypeError)):
        theme_of("dark").background = "#000000"  # type: ignore[misc]


def test_contrast_ratio_of_black_against_white_is_twenty_one():
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.05)


def test_contrast_ratio_is_symmetric():
    assert contrast_ratio("#39d353", "#0d1117") == pytest.approx(
        contrast_ratio("#0d1117", "#39d353"))


def test_identical_colours_have_a_ratio_of_one():
    assert contrast_ratio("#26a641", "#26a641") == pytest.approx(1.0)


@pytest.mark.parametrize("mode", sorted(EXPECTED))
def test_every_level_is_distinguishable_from_the_background(mode):
    t = theme_of(mode)
    for i, colour in enumerate(t.levels):
        assert contrast_ratio(colour, t.background) > 1.2, f"{mode} level {i + 1}"


@pytest.mark.parametrize("mode", sorted(EXPECTED))
def test_adjacent_levels_are_distinguishable_from_each_other(mode):
    """Colour is the only signal for decay levels: collapsing two loses information."""
    levels = theme_of(mode).levels
    for i in range(len(levels) - 1):
        assert contrast_ratio(levels[i], levels[i + 1]) > 1.15, f"{mode} {i + 1}->{i + 2}"


@pytest.mark.parametrize("mode", sorted(EXPECTED))
def test_levels_increase_monotonically_in_luminance_contrast_against_the_background(mode):
    """The levels must be ordered by strength, with no pair swapped."""
    t = theme_of(mode)
    ratios = [contrast_ratio(c, t.background) for c in t.levels]
    assert ratios == sorted(ratios), f"{mode}: {ratios}"


def test_standard_rule_uses_the_strongest_level_only():
    assert theme_of("dark").colour_for(level=1, max_level=1) == "#39d353"


def test_decay_maps_each_level_to_its_own_colour():
    t = theme_of("dark")
    assert [t.colour_for(l, 4) for l in (1, 2, 3, 4)] == list(EXPECTED["dark"][1])


def test_a_level_outside_the_rules_range_is_rejected():
    with pytest.raises(ValueError):
        theme_of("dark").colour_for(level=5, max_level=4)
