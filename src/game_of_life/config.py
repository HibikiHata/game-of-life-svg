"""The settings a caller may pass in.

Invalid values raise `ValueError` instead of falling back to a default. A
misspelled preset that silently passes as `grass` would publish an artefact
that is not the one anyone asked for.

Generation limits are held per preset because holding frames is the only
unbounded consumer of memory in this design. The larger the area, the lower
the limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

RULES_ALLOWED = ("standard", "decay")
FRAME_RANGES = ("cycle", "full", "head")


@dataclass(frozen=True)
class Preset:
    name: str
    size: tuple[int, int] | None      # None = derived from the calendar at run time
    limit: int


PRESETS: Mapping[str, Preset] = {
    # Only the grass preset has no fixed size. The window covers 365 or 366
    # days and buckets into 52 to 54 weeks, so a fixed size would reject a
    # legitimate API response.
    "grass":    Preset("grass",    None,       400),
    "card":     Preset("card",     (48, 27),   400),
    "banner":   Preset("banner",   (80, 20),   400),
    "square-s": Preset("square-s", (50, 50),   300),
    # The limits for square-m and square-l are **measured ceilings under the
    # decay rule**. An earlier measurement used a synthetic board at 30 per cent
    # density under the standard rule, where the output is 8 to 18 times smaller
    # (square-l: 17 KB standard, 318 KB decay). The largest limits that fit the
    # budget are 176 and 141; these values keep about ten per cent of headroom.
    "square-m": Preset("square-m", (75, 75),   160),
    "square-l": Preset("square-l", (100, 100), 128),
}

DEFAULT_FPS = 10
DEFAULT_BUDGET_BYTES = 256_000        # gzipped decimal bytes, not raw


def _one_of(name: str, value: object, allowed: tuple[str, ...]) -> None:
    if value not in allowed:
        raise ValueError(f"invalid {name}: {value!r} (expected {' / '.join(allowed)})")


@dataclass(frozen=True)
class Options:
    preset: str
    rule: str = "decay"               # the grass default; standard kills 80% in one step
    frame_range: str = "cycle"
    # None = use the preset's limit. Do not use 0 as the sentinel: "zero
    # generations" is an invalid value rather than "unspecified", and
    # representing both with the same value disables the invalid-value check.
    # A test caught this first.
    limit: int | None = None
    fps: int = DEFAULT_FPS
    budget_bytes: int = DEFAULT_BUDGET_BYTES

    def __post_init__(self) -> None:
        _one_of("preset", self.preset, tuple(PRESETS))
        _one_of("rule", self.rule, RULES_ALLOWED)
        _one_of("frame.range", self.frame_range, FRAME_RANGES)
        cap = PRESETS[self.preset].limit
        if self.limit is None:
            object.__setattr__(self, "limit", cap)
        elif self.limit < 1:
            raise ValueError(f"limit must be at least 1: {self.limit}")
        elif self.limit > cap:
            # The limit is what guarantees the budget, so a caller must not be
            # able to exceed it silently.
            raise ValueError(
                f"limit exceeds the cap of {cap} for preset {self.preset}: {self.limit}"
            )
        if self.fps < 1:
            raise ValueError(f"fps must be at least 1: {self.fps}")
        if self.budget_bytes < 1:
            raise ValueError(f"budget_bytes must be at least 1: {self.budget_bytes}")

    @property
    def board_size(self) -> tuple[int, int] | None:
        return PRESETS[self.preset].size
