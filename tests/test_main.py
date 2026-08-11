"""Tests for the command line interface.

Primary failure modes:
- **The token reaching an argument**: it would stay in the process list and the
  shell history. The environment is the only channel.
- **A budget overrun exiting 0**: CI would not notice and an oversized artefact
  would be published.
- **Presenting a frozen board as an animation**: there must be a path that
  degrades to the static variant.
"""

from __future__ import annotations

import datetime
import json

import pytest

from game_of_life.__main__ import main
from tests.fixtures_calendar import REAL_CALENDAR_LEVELS
from tests.test_grass import api_response

NAMES = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]


@pytest.fixture
def stub_http(monkeypatch):
    def install(levels):
        payload = api_response(levels)
        monkeypatch.setattr("game_of_life.__main__.http_fetch",
                            lambda q, v, t: payload)
    return install


def test_patterns_lists_every_category(capsys):
    assert main(["patterns"]) == 0
    out = capsys.readouterr().out
    assert "still-life" in out and "gun" in out


def test_gallery_writes_the_page_and_the_artefacts(tmp_path):
    assert main(["gallery", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "patterns.md").is_file()
    assert len(list((tmp_path / "patterns").iterdir())) >= 100


def test_grass_requires_a_token(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert main(["grass", "--login", "x", "--out", str(tmp_path)]) == 2
    assert "GITHUB_TOKEN" in capsys.readouterr().err


def test_grass_writes_both_themes(monkeypatch, tmp_path, stub_http):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    stub_http(list(REAL_CALENDAR_LEVELS))
    assert main(["grass", "--login", "x", "--out", str(tmp_path),
                 "--date", "2026-08-10"]) == 0
    for name in ("life-light.svg", "life-dark.svg",
                 "life-light-static.svg", "life-dark-static.svg"):
        assert (tmp_path / name).is_file(), name


def test_grass_is_deterministic_for_a_date(monkeypatch, tmp_path, stub_http):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    stub_http(list(REAL_CALENDAR_LEVELS))
    args = ["grass", "--login", "x", "--date", "2026-08-10", "--out"]
    main(args + [str(tmp_path / "a")])
    main(args + [str(tmp_path / "b")])
    for f in (tmp_path / "a").iterdir():
        assert f.read_bytes() == (tmp_path / "b" / f.name).read_bytes(), f.name


def test_grass_degrades_to_the_static_variant_when_nothing_moves(
        monkeypatch, tmp_path, stub_http, capsys):
    """A board that does not move must not be presented as an animation."""
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    stub_http([0] * 365)
    assert main(["grass", "--login", "x", "--out", str(tmp_path),
                 "--date", "2026-08-10"]) == 0
    assert not (tmp_path / "life-dark.svg").exists()
    assert (tmp_path / "life-dark-static.svg").is_file()
    assert "barely moves" in capsys.readouterr().err


def test_a_graphql_failure_exits_non_zero_and_writes_nothing(
        monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setattr("game_of_life.__main__.http_fetch",
                        lambda q, v, t: {"errors": [{"message": "Bad credentials"}]})
    assert main(["grass", "--login", "x", "--out", str(tmp_path)]) == 1
    assert not list(tmp_path.iterdir())


def test_the_token_is_never_a_command_line_argument():
    """As an argument it would stay in the process list and the shell history."""
    import game_of_life.__main__ as m
    import inspect
    source = inspect.getsource(m)
    assert '"--token"' not in source and "'--token'" not in source


# ---------------------------------------------------------------- render

def test_render_writes_both_themes(tmp_path):
    assert main(["render", "--pattern", "glider", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "glider-card-light.svg").is_file()
    assert (tmp_path / "glider-card-dark.svg").is_file()


def test_render_uses_the_preset_canvas_when_one_is_given(tmp_path):
    assert main(["render", "--pattern", "glider", "--preset", "square-l",
                 "--out", str(tmp_path)]) == 0
    svg = (tmp_path / "glider-square-l-dark.svg").read_text()
    assert 'viewBox="0 0 100 100"' in svg


def test_the_preset_changes_the_bytes_not_only_the_name(tmp_path):
    """If the dimensions have no effect, the argument was silently ignored."""
    main(["render", "--pattern", "glider", "--preset", "card", "--out", str(tmp_path)])
    main(["render", "--pattern", "glider", "--preset", "square-l", "--out", str(tmp_path)])
    a = (tmp_path / "glider-card-dark.svg").read_bytes()
    b = (tmp_path / "glider-square-l-dark.svg").read_bytes()
    # Which file is larger is not decided in one direction: a bigger canvas
    # carries a lower generation limit, so square-l bakes 128 frames and card
    # bakes 400. Only the difference in content is asserted.
    assert a != b
    assert b'viewBox="0 0 48 27"' in a and b'viewBox="0 0 100 100"' in b


def test_render_accepts_a_rule_override(tmp_path):
    """The rule must be selectable from the CLI. Decay emits paths for four colours."""
    main(["render", "--pattern", "r-pentomino", "--preset", "card",
          "--rule", "decay", "--limit", "40", "--out", str(tmp_path)])
    svg = (tmp_path / "r-pentomino-card-dark.svg").read_text()
    assert svg.count("#0e4429") >= 1        # the colour of the weakest decay level


def test_render_accepts_a_frame_range_override(tmp_path):
    """The frame range must be selectable from the CLI."""
    main(["render", "--pattern", "blinker", "--frame-range", "cycle",
          "--out", str(tmp_path)])
    cycle = (tmp_path / "blinker-card-dark.svg").read_text().count('class="f')
    main(["render", "--pattern", "blinker", "--frame-range", "head",
          "--limit", "20", "--out", str(tmp_path)])
    head = (tmp_path / "blinker-card-dark.svg").read_text().count('class="f')
    assert cycle == 2 and head == 20


def test_render_rejects_an_unknown_pattern(tmp_path, capsys):
    assert main(["render", "--pattern", "nope", "--out", str(tmp_path)]) == 2
    assert "patterns" in capsys.readouterr().err


def test_render_rejects_a_pattern_that_does_not_fit(tmp_path, capsys):
    assert main(["render", "--pattern", "simkin-gun", "--preset", "banner",
                 "--out", str(tmp_path)]) == 1
    assert "does not fit" in capsys.readouterr().err


def test_grass_accepts_a_rule_override(monkeypatch, tmp_path, stub_http):
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    stub_http(list(REAL_CALENDAR_LEVELS))
    assert main(["grass", "--login", "x", "--rule", "standard",
                 "--date", "2026-08-10", "--out", str(tmp_path)]) == 0
