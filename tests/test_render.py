"""Unit tests for render.py.

Primary failure modes:
- **A blank image wherever animation does not run.** The early probe was
  exactly this.
- **Losing determinism**: iteration order or float formatting makes the same
  input emit different bytes. The picture is identical, so only a golden diff
  shows it.
- **Measuring the budget raw**: delivery is gzipped, so judging on raw bytes is
  off by 5x to 30x.
- **Breaking self-containment**: a single external reference, absolute path or
  personal identifier stops the file from working as a distributable artefact.
"""

from __future__ import annotations

import gzip
import re
import xml.dom.minidom

import pytest

from game_of_life.board import Board
from game_of_life.config import Options
from game_of_life.render import bake, bake_static, size_report
from game_of_life.rules import RULES
from game_of_life.theme import theme_of

BLINKER = {(3, 2): 1, (3, 3): 1, (3, 4): 1}
DECAY_BOARD = {(1, 1): 1, (2, 1): 2, (3, 1): 3, (4, 1): 4}


def frames(levels_list, w=8, h=8):
    return [Board.of(width=w, height=h, boundary="torus", levels=l) for l in levels_list]


def render(levels_list=None, rule="standard", mode="dark", **opts):
    levels_list = levels_list or [BLINKER, {(2, 3): 1, (3, 3): 1, (4, 3): 1}]
    return bake(frames(levels_list), rule=RULES[rule], theme=theme_of(mode),
                options=Options(preset="card", rule=rule, **opts), title="Life")


# ---------------------------------------------------------------- structure

def test_the_output_is_well_formed_xml():
    # Only this test's own output is parsed, so there is no external-entity path.
    xml.dom.minidom.parseString(render().decode("utf-8"))


def test_every_frame_becomes_one_group():
    assert render().decode().count('class="f') == 2


def test_each_level_gets_its_own_path_within_a_frame():
    out = bake(frames([DECAY_BOARD]), rule=RULES["decay"], theme=theme_of("dark"),
               options=Options(preset="card"), title="t").decode()
    assert out.count("<path") == 4


def test_a_standard_render_uses_a_single_colour():
    out = render().decode()
    colours = set(re.findall(r"fill:(#[0-9a-f]{6})", out))
    assert len(colours - {theme_of("dark").background}) == 1


def test_cells_appear_in_row_then_column_order():
    out = render([{(5, 1): 1, (0, 0): 1}]).decode()
    assert out.index("M0 0") < out.index("M5 1")


# ---------------------------------------------------------------- default visibility

def test_the_first_frame_is_visible_when_animation_does_not_run():
    """If this fails, the artefact ships as a blank image wherever CSS is static."""
    out = render().decode()
    assert ".f0{opacity:1}" in out.replace(" ", "")
    assert out.index("opacity:0") < out.index(".f0")


def test_the_static_variant_carries_no_animation_at_all():
    out = bake_static(frames([BLINKER])[0], rule=RULES["standard"],
                      theme=theme_of("dark"), options=Options(preset="card"),
                      title="t").decode()
    assert "@keyframes" not in out and "animation" not in out
    assert "<path" in out


def test_the_static_variant_shows_the_frame_it_was_given():
    out = bake_static(frames([{(1, 1): 1}])[0], rule=RULES["standard"],
                      theme=theme_of("dark"), options=Options(preset="card"),
                      title="t").decode()
    assert "M1 1" in out


# ---------------------------------------------------------------- self-containment

def test_no_script_no_foreign_object_no_external_reference():
    out = render().decode()
    assert "<script" not in out and "foreignObject" not in out
    assert out.count("http") == 1          # the SVG namespace and nothing else


@pytest.mark.parametrize("forbidden", ["/Users/", "\\", "file://"])
def test_no_absolute_path_leaks(forbidden):
    assert forbidden not in render().decode()


def test_no_email_address_leaks():
    """A bare `@` occurs legitimately in `@keyframes`, so match the address shape."""
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", render().decode())


def test_the_document_declares_role_img_and_a_title():
    out = render().decode()
    assert 'role="img"' in out and "<title>Life</title>" in out


# ---------------------------------------------------------------- determinism

def test_two_renders_of_the_same_input_are_byte_identical():
    assert render() == render()


def test_the_background_is_drawn_before_the_frames():
    out = render().decode()
    assert out.index("<rect") < out.index('class="f')


def test_an_empty_frame_sequence_is_rejected():
    with pytest.raises(ValueError):
        bake([], rule=RULES["standard"], theme=theme_of("dark"),
             options=Options(preset="card"), title="t")


def test_frames_of_differing_dimensions_are_rejected():
    mixed = [Board.of(width=8, height=8, boundary="torus", levels=BLINKER),
             Board.of(width=9, height=8, boundary="torus", levels=BLINKER)]
    with pytest.raises(ValueError):
        bake(mixed, rule=RULES["standard"], theme=theme_of("dark"),
             options=Options(preset="card"), title="t")


# ---------------------------------------------------------------- budget

def test_the_size_report_measures_gzipped_bytes():
    data = render()
    r = size_report("x.svg", data, budget_bytes=256_000)
    assert r.raw_bytes == len(data)
    assert r.gzipped_bytes == len(gzip.compress(data, 9))
    assert r.gzipped_bytes < r.raw_bytes


def test_a_report_within_budget_is_flagged_as_such():
    assert size_report("x.svg", render(), budget_bytes=256_000).within_budget


def test_a_report_over_budget_is_flagged_by_the_gzipped_size_not_the_raw_one():
    """Judging the budget on raw bytes is off by 5x to 30x; the ratio is not constant."""
    data = render()
    budget = len(gzip.compress(data, 9)) - 1
    r = size_report("x.svg", data, budget_bytes=budget)
    assert not r.within_budget
    assert r.raw_bytes > budget          # measuring raw would reach the opposite verdict


def test_the_report_names_the_artefact():
    assert size_report("out/life-dark.svg", render(), budget_bytes=1).path == "out/life-dark.svg"


# ---------------------------------------------------------------- walking skeleton

def test_a_blinker_renders_to_a_two_frame_loop():
    """The first artefact the design named as a verification target."""
    out = render([BLINKER, {(2, 3): 1, (3, 3): 1, (4, 3): 1}]).decode()
    assert out.count('class="f') == 2
    assert "step-end" in out and "infinite" in out
    # Two frames at the default 10 fps, so one cycle lasts 0.2 seconds.
    assert "animation:s 0.2s step-end infinite" in out
    # Alternating means the two frames differ in content.
    assert out.count("M3 2") == 1 and out.count("M2 3") == 1
    xml.dom.minidom.parseString(out)
