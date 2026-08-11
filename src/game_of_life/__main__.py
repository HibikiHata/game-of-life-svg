"""Command line interface.

    PYTHONPATH=src python3 -m game_of_life gallery --out docs
    PYTHONPATH=src python3 -m game_of_life grass --login <name> --out output
    PYTHONPATH=src python3 -m game_of_life patterns

`grass` reads its token from the `GITHUB_TOKEN` environment variable. Accepting
it as an argument would leave it in the process list and the shell history.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

from game_of_life.compose import board_for_preset
from game_of_life.config import PRESETS, Options
from game_of_life.evolve import sequence, slice_range
from game_of_life.gallery import ARTEFACT_DIR, build, page
from game_of_life.grass import calendar_to_board, fetch_calendar, is_lively, perturb
from game_of_life.patterns import by_category, load_all
from game_of_life.render import bake, bake_static, size_report
from game_of_life.rules import RULES
from game_of_life.theme import theme_of

GRAPHQL_URL = "https://api.github.com/graphql"


def http_fetch(query: str, variables: dict, token: str) -> dict:
    """One GraphQL call. This is the package's only network boundary."""
    body = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        GRAPHQL_URL, data=body,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "game-of-life-svg"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ValueError(f"GraphQL returned HTTP {exc.code}") from exc


def _report(reports) -> int:
    over = [r for r in reports if not r.within_budget]
    for r in reports:
        print(f"  {r.path}  raw {r.raw_bytes:>8}B  gzip {r.gzipped_bytes:>7}B"
              f"{'  **over budget**' if not r.within_budget else ''}")
    if over:
        print(f"{len(over)} artefact(s) exceed the budget", file=sys.stderr)
        return 1
    return 0


def cmd_gallery(args) -> int:
    patterns = load_all()
    options = Options(preset="card", rule="standard", frame_range="head")
    out = pathlib.Path(args.out)
    reports = build(patterns, out_dir=out, options=options)
    (out / "patterns.md").write_text(page(patterns), encoding="utf-8")
    print(f"{len(patterns)} patterns -> {out}/patterns.md and {out}/{ARTEFACT_DIR}/")
    return _report(reports)


def cmd_grass(args) -> int:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("the GITHUB_TOKEN environment variable is empty", file=sys.stderr)
        return 2
    rule = RULES[args.rule]
    options = Options(preset="grass", rule=args.rule, frame_range="head",
                      limit=args.limit)
    calendar = fetch_calendar(args.login, token=token, fetch=http_fetch)
    # A calendar always produces levels 1 to 4. When the standard rule (maximum
    # 1) is chosen, the levels are lowered explicitly here: nothing rounds
    # implicitly, so it is the caller's responsibility.
    board = perturb(calendar_to_board(calendar).clamped(rule.max_level),
                    datetime.date.fromisoformat(args.date), rule.max_level)
    frames = slice_range(sequence(board, rule, limit=options.limit), options.frame_range)

    lively = is_lively(frames)
    if not lively:
        # Judged on the rendered result, not the input density. Publishing a
        # still image is more honest than presenting a frozen board as an
        # animation.
        print("the animation barely moves; emitting the static variant only",
              file=sys.stderr)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    reports = []
    for mode in ("light", "dark"):
        theme = theme_of(mode)
        title = f"Game of Life seeded by {calendar.login}'s contributions"
        if lively:
            data = bake(frames, rule=rule, theme=theme, options=options, title=title)
            (out / f"life-{mode}.svg").write_bytes(data)
            reports.append(size_report(f"life-{mode}.svg", data, options.budget_bytes))
        still = bake_static(frames[0], rule=rule, theme=theme, options=options,
                            title=f"{title} (first frame)")
        (out / f"life-{mode}-static.svg").write_bytes(still)
        reports.append(size_report(f"life-{mode}-static.svg", still, options.budget_bytes))

    print(f"{calendar.login}: {calendar.weeks} weeks / {board.live_count} live cells / "
          f"{len(frames)} frames / moving={lively}")
    return _report(reports)


def cmd_render(args) -> int:
    """Bake a library pattern with any preset and any rule.

    The board a pattern declares is a default, not a fixed property. A glider
    placed on square-l wraps at 100 cells, so the same pattern yields a
    different picture.
    """
    patterns = {p.slug: p for p in load_all()}
    if args.pattern not in patterns:
        print(f"unknown pattern: {args.pattern} (list them with `patterns`)",
              file=sys.stderr)
        return 2
    pattern = patterns[args.pattern]
    rule = RULES[args.rule]

    if args.preset:
        board = board_for_preset(pattern, args.preset, level=rule.max_level)
        preset = args.preset
    else:
        board = pattern.to_board(level=rule.max_level)
        # Even when the pattern's own board is used, the budget and the
        # generation cap still come from some preset.
        preset = "card"
    options = Options(preset=preset, rule=args.rule,
                      frame_range=args.frame_range or pattern.frame_range,
                      limit=args.limit)
    frames = slice_range(sequence(board, rule, limit=options.limit), options.frame_range)

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    reports = []
    for mode in ("light", "dark"):
        data = bake(frames, rule=rule, theme=theme_of(mode), options=options,
                    title=pattern.name)
        name = f"{pattern.slug}-{preset}-{mode}.svg"
        (out / name).write_bytes(data)
        reports.append(size_report(name, data, options.budget_bytes))
    print(f"{pattern.name} on {preset} ({board.width}x{board.height}) / "
          f"{args.rule} / {options.frame_range} / {len(frames)} frames")
    return _report(reports)


def cmd_patterns(args) -> int:
    for category, group in by_category(load_all()).items():
        print(f"{category} ({len(group)})")
        for p in group:
            print(f"  {p.slug:18} {p.name:26} {p.board[0]}x{p.board[1]} "
                  f"{p.boundary:6} {p.frame_range}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="game_of_life", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("gallery", help="build every pattern's artefacts and the page")
    g.add_argument("--out", default="docs")
    g.set_defaults(func=cmd_gallery)

    r = sub.add_parser("grass", help="build the widget from a contribution graph")
    r.add_argument("--login", required=True)
    r.add_argument("--out", default="output")
    r.add_argument("--limit", type=int, default=120)
    r.add_argument("--rule", choices=sorted(RULES), default="decay",
                   help="defaults to decay; standard kills 80%% of the board in one step")
    r.add_argument("--date", default=datetime.date.today().isoformat(),
                   help="the date used for the perturbation; defaults to today")
    r.set_defaults(func=cmd_grass)

    d = sub.add_parser("render", help="bake one pattern with a chosen preset and rule")
    d.add_argument("--pattern", required=True)
    d.add_argument("--preset", choices=sorted(n for n, v in PRESETS.items() if v.size),
                   help="replace the canvas; defaults to the pattern's own board")
    d.add_argument("--rule", choices=sorted(RULES), default="standard")
    d.add_argument("--frame-range", dest="frame_range",
                   choices=("cycle", "full", "head"),
                   help="defaults to what the pattern declares")
    d.add_argument("--limit", type=int, default=None)
    d.add_argument("--out", default="output")
    d.set_defaults(func=cmd_render)

    p = sub.add_parser("patterns", help="list the pattern library")
    p.set_defaults(func=cmd_patterns)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
