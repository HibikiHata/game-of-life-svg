"""Turn a contribution graph into a board.

The only external dependency in this package is contained here. The HTTP call
is injected, so the tests never touch the network.

**Never use `viewer`.** Under a workflow token `viewer` resolves to
`github-actions[bot]`, whose empty calendar publishes a blank widget without
raising anything. `user(login:)` names the target explicitly. That a workflow
token suffices is corroborated by `Platane/snk`, whose action defaults
`github_token` to `${{ github.token }}`.

Board dimensions are **derived from the response**. The window covers 365 or
366 days, buckets into 52 to 54 weeks, and the first and last weeks are
partial. Hard-coding 53x7 rejects legitimate responses.
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass
from typing import Callable, Sequence

from game_of_life.board import Board

GRAPHQL_QUERY = """
query($login: String!) {
  user(login: $login) {
    login
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date weekday contributionLevel } }
      }
    }
  }
}
"""

LEVELS = {
    "NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4,
}

# The line between a live and a frozen animation. Measured, a live board changes
# 120 to 190 cells per frame while a frozen one changes 0.5 to 0.8. The two are
# two orders of magnitude apart, so the result does not depend on the exact
# value of this threshold.
LIVELINESS_THRESHOLD = 8.0

Fetch = Callable[[str, dict, str], dict]


@dataclass(frozen=True)
class Calendar:
    login: str
    days: tuple[tuple[datetime.date, int], ...]     # ascending by date
    weeks: int


def fetch_calendar(login: str, *, token: str, fetch: Fetch) -> Calendar:
    """Fetch the calendar over GraphQL. An unexpected shape fails before anything is written."""
    payload = fetch(GRAPHQL_QUERY, {"login": login}, token)
    if "errors" in payload:
        raise ValueError(f"GraphQL returned an error: {payload['errors']}")
    try:
        user = payload["data"]["user"]
        weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"unexpected response shape: {exc}") from exc
    if not weeks:
        raise ValueError(
            "the calendar is empty: the login does not exist, or the token "
            "lacks the necessary access"
        )

    days: list[tuple[datetime.date, int]] = []
    for week in weeks:
        for day in week["contributionDays"]:
            level = LEVELS.get(day["contributionLevel"])
            if level is None:
                raise ValueError(
                    f"unknown contributionLevel: {day['contributionLevel']!r}"
                )
            days.append((datetime.date.fromisoformat(day["date"]), level))
    return Calendar(login=user["login"], days=tuple(sorted(days)), weeks=len(weeks))


def calendar_to_board(calendar: Calendar, *, boundary: str = "torus") -> Board:
    """Columns are weeks, rows are weekdays. The size comes from the response."""
    first = calendar.days[0][0]
    origin = first - datetime.timedelta(days=first.isoweekday() % 7)
    levels = {}
    for day, level in calendar.days:
        if level:
            column = (day - origin).days // 7
            levels[(column, day.isoweekday() % 7)] = level
    return Board.of(width=calendar.weeks, height=7, boundary=boundary, levels=levels)


def perturb(board: Board, day: datetime.date, max_level: int) -> Board:
    """Raise one date-derived cell to the maximum level.

    Without this, the board is unchanged on most days even as the window
    advances. The row is fixed by the weekday and the column only moves at a
    week boundary, so a weekday with no contributions produces exactly
    yesterday's board. Measured, 20 to 25 days out of 30 were duplicates.
    """
    digest = hashlib.sha256(day.isoformat().encode("utf-8")).digest()
    position = (digest[0] % board.width, digest[1] % board.height)
    return board.with_levels({**board.as_map(), position: max_level})


def is_lively(frames: Sequence[Board]) -> bool:
    """Whether the animation actually moves. **Judged on the output, not the input density.**

    The relation between density and survival is probabilistic: measured, two
    boards at the same 5 per cent density lived or died depending only on where
    the date-derived cell landed. Gating on density is wrong in both
    directions. The frames are already computed, so measuring the real result
    is both cheaper and correct.
    """
    if len(frames) < 2:
        return False
    churn = [
        len(set(frames[i].levels) ^ set(frames[i + 1].levels))
        for i in range(len(frames) - 1)
    ]
    return sum(churn) / len(churn) >= LIVELINESS_THRESHOLD
