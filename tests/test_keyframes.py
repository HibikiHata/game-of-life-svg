"""Unit tests for keyframes.py.

Primary failure modes:
- **Blank wherever CSS does not run**: defaulting every frame to opacity:0
  means a renderer that does not run animation shows nothing. The 2026-08-10
  probe was exactly this. It **only looks correct while it is moving**, so
  still-image review can never find it.
- **Frames blending**: dropping `step-end` interpolates the intermediate
  states and the board melts.
- **Duration disagreeing with the frame count**: if one cycle's length is
  wrong, the loop jumps at the seam.
"""

from __future__ import annotations

import re

import pytest

from game_of_life.keyframes import frame_track


def track(n=120, fps=10):
    return frame_track(frame_count=n, fps=fps)


# ---------------------------------------------------------------- default visibility

def test_the_first_frame_is_visible_without_animation():
    """The single guard against the probe's blank-image defect returning."""
    t = track()
    assert t.first_frame_visible_css, "no rule makes the first frame visible by default"
    assert "opacity:1" in t.first_frame_visible_css.replace(" ", "")


def test_the_first_frame_rule_comes_after_the_hidden_default():
    """CSS is last-rule-wins, so the reverse order would disable the default."""
    css = track().css
    assert css.index("opacity:0") < css.index(".f0")


def test_a_single_frame_render_is_visible_too():
    assert "opacity:1" in track(n=1).first_frame_visible_css.replace(" ", "")


# ---------------------------------------------------------------- timing

def test_duration_is_frame_count_over_fps():
    assert "12s" in track(120, 10).css
    assert "6s" in track(60, 10).css


def test_timing_function_is_step_end_so_frames_snap():
    assert "step-end" in track().css


def test_the_animation_loops_forever():
    assert "infinite" in track().css


def test_each_frame_gets_its_own_negative_delay():
    delays = track(n=4, fps=10).delays
    assert delays == ("0s", "-0.1s", "-0.2s", "-0.3s")


def test_delays_cover_exactly_one_cycle():
    n = 24
    delays = track(n=n, fps=12).delays
    assert len(delays) == n
    assert len(set(delays)) == n


def test_the_visible_window_is_one_frame_wide():
    """The visible window in @keyframes must be 100/frame-count per cent."""
    m = re.search(r"0%\{opacity:1\}([\d.]+)%\{opacity:0\}", track(n=8).css.replace(" ", ""))
    assert m and float(m.group(1)) == pytest.approx(12.5, abs=0.01)


# ---------------------------------------------------------------- structure

def test_no_script_or_foreign_object_is_emitted():
    css = track().css
    assert "<script" not in css and "foreignObject" not in css


def test_only_one_keyframes_rule_is_emitted_regardless_of_frame_count():
    """One @keyframes per frame would blow up the byte count."""
    assert track(n=240).css.count("@keyframes") == 1


def test_frame_count_below_one_is_rejected():
    with pytest.raises(ValueError):
        frame_track(frame_count=0, fps=10)


def test_non_positive_fps_is_rejected():
    with pytest.raises(ValueError):
        frame_track(frame_count=10, fps=0)


def test_two_tracks_with_the_same_inputs_are_byte_identical():
    assert track().css == track().css
    assert track().delays == track().delays


def test_only_duration_and_delay_count_change_with_frame_count():
    """Changing the range must leave the rule name, the timing and the structure alone."""
    a, c = track(n=10), track(n=200)
    strip = lambda s: re.sub(r"[\d.]+s|[\d.]+%", "#", s)
    assert strip(a.css) == strip(c.css)
