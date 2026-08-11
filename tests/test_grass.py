"""Tests for grass.py.

Primary failure modes:
- **`viewer` quietly drawing an empty board**: under a workflow token `viewer`
  resolves to `github-actions[bot]`. The calendar comes back empty, nothing
  raises, and a blank widget is published. **The only fix is to forbid it
  structurally.**
- **Daily variation not actually happening**: two designs failed here in a row.
  A continuation-based design repeated on 13 days out of 30; plain statelessness
  repeated on 20 out of 30, and 25 out of 30 in the worst case. **The comparison
  is made on the baked frame sequence, not on the initial board** — different
  boards can converge on the same attractor.
- **Hard-coding the shape**: the window covers 365 or 366 days, buckets into 52
  to 54 weeks, and the first and last weeks are partial. Fixing 53x7=371
  rejects legitimate responses.
"""

from __future__ import annotations

import datetime

import pytest

from game_of_life.evolve import sequence, slice_range
from game_of_life.grass import (
    GRAPHQL_QUERY, calendar_to_board, fetch_calendar, is_lively, perturb,
)
from game_of_life.render import bake
from game_of_life.rules import RULES
from game_of_life.theme import theme_of
from game_of_life.config import Options
from tests.fixtures_calendar import REAL_CALENDAR_LEVELS

DECAY = RULES["decay"]
OPTIONS = Options(preset="grass", rule="decay", frame_range="head", limit=120)


def api_response(levels, start=datetime.date(2025, 8, 10)):
    """Build a GraphQL response. Bucketed by week; the first and last may be partial."""
    weeks, current = [], []
    for i, level in enumerate(levels):
        day = start + datetime.timedelta(days=i)
        current.append({"date": day.isoformat(), "weekday": day.isoweekday() % 7,
                        "contributionLevel": ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE",
                                              "THIRD_QUARTILE", "FOURTH_QUARTILE"][level]})
        if current[-1]["weekday"] == 6:
            weeks.append({"contributionDays": current}); current = []
    if current:
        weeks.append({"contributionDays": current})
    return {"data": {"user": {"login": "someone", "contributionsCollection":
                              {"contributionCalendar": {"weeks": weeks}}}}}


def fake_fetch(payload):
    calls = []

    def _fetch(query, variables, token):
        calls.append((query, variables, token))
        return payload
    _fetch.calls = calls
    return _fetch


# ---------------------------------------------------------------- fetching

def test_the_query_addresses_a_named_user():
    assert "user(login:" in GRAPHQL_QUERY.replace(" ", "")


def test_the_query_never_uses_viewer():
    """Under a workflow token viewer is the bot, which quietly draws an empty board."""
    assert "viewer" not in GRAPHQL_QUERY


def test_the_query_asks_for_level_and_not_for_the_exact_count():
    """An exact commit count is more precision than the widget should expose."""
    assert "contributionLevel" in GRAPHQL_QUERY
    assert "contributionCount" not in GRAPHQL_QUERY


def test_the_login_and_token_are_passed_through():
    f = fake_fetch(api_response([0] * 365))
    fetch_calendar("octocat", token="t0k3n", fetch=f)
    _, variables, token = f.calls[0]
    assert variables["login"] == "octocat"
    assert token == "t0k3n"


def test_an_unexpected_shape_fails_rather_than_yielding_an_empty_calendar():
    with pytest.raises(ValueError):
        fetch_calendar("x", token="t", fetch=fake_fetch({"data": {"user": None}}))


def test_a_graphql_error_response_fails():
    with pytest.raises(ValueError, match="GraphQL"):
        fetch_calendar("x", token="t",
                       fetch=fake_fetch({"errors": [{"message": "Bad credentials"}]}))


def test_an_empty_week_list_fails():
    payload = api_response([])
    with pytest.raises(ValueError):
        fetch_calendar("x", token="t", fetch=fake_fetch(payload))


# ---------------------------------------------------------------- building the board

def test_the_board_takes_its_width_from_the_response():
    cal = fetch_calendar("x", token="t", fetch=fake_fetch(api_response([0] * 365)))
    board = calendar_to_board(cal)
    assert board.width == cal.weeks
    assert board.height == 7


@pytest.mark.parametrize("days", [364, 365, 366, 371])
def test_windows_of_different_lengths_are_all_accepted(days):
    """52 to 54 weeks, with partial ones. Hard-coding 53x7 rejects valid responses."""
    cal = fetch_calendar("x", token="t", fetch=fake_fetch(api_response([1] * days)))
    board = calendar_to_board(cal)
    assert board.live_count == days


def test_a_day_without_contributions_leaves_its_cell_dead():
    cal = fetch_calendar("x", token="t",
                         fetch=fake_fetch(api_response([0, 2, 0] + [0] * 362)))
    assert calendar_to_board(cal).live_count == 1


def test_levels_map_one_to_one_from_the_quartiles():
    cal = fetch_calendar("x", token="t",
                         fetch=fake_fetch(api_response([1, 2, 3, 4] + [0] * 361)))
    assert sorted(v for _, v in calendar_to_board(cal).levels) == [1, 2, 3, 4]


def test_a_date_keeps_its_weekday_row():
    """The row being fixed by the date is also why sliding the window changes so little."""
    cal = fetch_calendar("x", token="t", fetch=fake_fetch(
        api_response([0] * 3 + [4] + [0] * 361, start=datetime.date(2025, 8, 10))))
    rows = {pos[1] for pos, _ in calendar_to_board(cal).levels}
    assert rows == {datetime.date(2025, 8, 13).isoweekday() % 7}


# ------------------------------------------------- perturbation and daily variation

def test_the_perturbation_sets_exactly_one_cell_to_the_maximum():
    board = calendar_to_board(fetch_calendar(
        "x", token="t", fetch=fake_fetch(api_response([0] * 365))))
    out = perturb(board, datetime.date(2026, 8, 10), max_level=4)
    assert out.live_count == 1
    assert {v for _, v in out.levels} == {4}


def test_the_perturbation_is_deterministic_for_a_date():
    board = calendar_to_board(fetch_calendar(
        "x", token="t", fetch=fake_fetch(api_response([0] * 365))))
    day = datetime.date(2026, 8, 10)
    assert perturb(board, day, 4) == perturb(board, day, 4)


def test_the_perturbation_moves_with_the_date():
    board = calendar_to_board(fetch_calendar(
        "x", token="t", fetch=fake_fetch(api_response([0] * 365))))
    a = perturb(board, datetime.date(2026, 8, 10), 4)
    c = perturb(board, datetime.date(2026, 8, 11), 4)
    assert a != c


def test_a_perturbation_landing_on_a_live_cell_only_raises_its_level():
    """The path that could be a no-op. Check the cell count does not grow."""
    board = calendar_to_board(fetch_calendar(
        "x", token="t", fetch=fake_fetch(api_response([1] * 365))))
    out = perturb(board, datetime.date(2026, 8, 10), 4)
    assert out.live_count == board.live_count
    assert sorted(v for _, v in out.levels).count(4) >= 1


def _baked(levels, day):
    cal = fetch_calendar("x", token="t", fetch=fake_fetch(api_response(levels)))
    board = perturb(calendar_to_board(cal), day, DECAY.max_level)
    frames = slice_range(sequence(board, DECAY, limit=OPTIONS.limit), "head")
    return bake(frames, rule=DECAY, theme=theme_of("dark"), options=OPTIONS, title="t")


def test_two_consecutive_days_differ_even_when_the_later_day_is_empty():
    """**The requirement's own test. Two designs failed here in a row.**

    The comparison is on the baked frames themselves. A difference in the
    initial board is not enough: different boards can converge on the same
    attractor.
    """
    base = list(REAL_CALENDAR_LEVELS)
    today = base[1:] + [0]          # the window advances a day; today has no contributions
    a = _baked(base, datetime.date(2026, 8, 10))
    c = _baked(today, datetime.date(2026, 8, 11))
    assert a != c


def test_thirty_consecutive_empty_days_never_repeat_an_animation():
    """The worst case: without the perturbation, 25 of 30 days repeat (measured)."""
    levels = list(REAL_CALENDAR_LEVELS)
    day = datetime.date(2026, 8, 10)
    seen = set()
    for i in range(30):
        window = levels[i + 1:] + [0] * (i + 1)
        seen.add(_baked(window, day + datetime.timedelta(days=i)))
    assert len(seen) == 30


def test_the_same_calendar_and_date_reproduce_the_same_bytes():
    """Idempotent with respect to the calendar, not with respect to the date."""
    levels = list(REAL_CALENDAR_LEVELS)
    day = datetime.date(2026, 8, 10)
    assert _baked(levels, day) == _baked(levels, day)


# ---------------------------------------------------------------- pinned measurements

def test_the_real_calendar_collapses_under_the_standard_rule():
    """120 -> 24. A property of the real data's clustering that random data lacks."""
    cal = fetch_calendar("x", token="t",
                         fetch=fake_fetch(api_response(list(REAL_CALENDAR_LEVELS))))
    board = calendar_to_board(cal)
    assert board.live_count == 120
    run = sequence(board.clamped(1), RULES["standard"], limit=2)
    assert run.frames[1].live_count == 24


def test_the_real_calendar_recovers_under_decay():
    cal = fetch_calendar("x", token="t",
                         fetch=fake_fetch(api_response(list(REAL_CALENDAR_LEVELS))))
    run = sequence(calendar_to_board(cal), DECAY, limit=200)
    assert max(f.live_count for f in run.frames) > 150


# ---------------------------------------------------------------- density degradation

def test_a_lively_render_is_reported_as_lively():
    cal = fetch_calendar("x", token="t",
                         fetch=fake_fetch(api_response(list(REAL_CALENDAR_LEVELS))))
    board = perturb(calendar_to_board(cal), datetime.date(2026, 8, 10), 4)
    frames = slice_range(sequence(board, DECAY, limit=120), "head")
    assert is_lively(frames)


def test_a_frozen_render_is_reported_as_not_lively():
    """Judged by measuring the output, not the input density."""
    cal = fetch_calendar("x", token="t",
                         fetch=fake_fetch(api_response([0] * 365)))
    board = perturb(calendar_to_board(cal), datetime.date(2026, 8, 10), 4)
    frames = slice_range(sequence(board, DECAY, limit=120), "head")
    assert not is_lively(frames)


def test_liveliness_needs_at_least_two_frames():
    cal = fetch_calendar("x", token="t", fetch=fake_fetch(api_response([1] * 365)))
    assert not is_lively(slice_range(sequence(calendar_to_board(cal), DECAY, limit=1), "head"))


def test_the_package_contains_no_persistence_layer():
    """A run looks only at the calendar it fetched, never at what a previous run wrote.

    The continuation-based design was rejected by measurement (13 days out of 30
    repeated). This checks structurally that no seed of persistence has grown —
    which is also what keeps an unexplained state file out of an adopter's
    repository.
    """
    import pathlib
    import re
    package = pathlib.Path(__file__).resolve().parents[1] / "src/game_of_life"
    offenders = []
    for path in package.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        # Apart from the CLI and gallery, which write artefacts, no write path may exist.
        if path.name in ("__main__.py", "gallery.py"):
            continue
        for pattern in (r"\.write_text\(", r"\.write_bytes\(", r"\bopen\([^)]*[\"']w"):
            if re.search(pattern, source):
                offenders.append(f"{path.name}: {pattern}")
    assert not offenders, offenders


def test_nothing_in_the_package_reads_a_state_file():
    import pathlib
    package = pathlib.Path(__file__).resolve().parents[1] / "src/game_of_life"
    for path in package.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "state.json" not in text, path.name
