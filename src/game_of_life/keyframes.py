"""The CSS that switches frames.

Each frame is wrapped in a `<g class="f">` and shown one at a time by a single
`@keyframes` rule plus a negative `animation-delay`. `step-end` keeps the
renderer from interpolating between frames. That `steps()` timing works through
an `<img>` was measured twice on github.com, on 2026-08-02 and 2026-08-10.

**The first frame is visible by default.** The 2026-08-10 probe set every frame
to `opacity:0` and made visibility depend entirely on the animation. Renderers
that do not run CSS animation — rasterisers, link previews, PDF export —
therefore produced a **completely blank image**. The defect only looks correct
while it is moving, so no amount of still-image review can find it.
"""

from __future__ import annotations

from dataclasses import dataclass

EPSILON_DIGITS = 4


@dataclass(frozen=True)
class Track:
    css: str
    delays: tuple[str, ...]
    duration_seconds: float
    first_frame_visible_css: str


def _seconds(value: float) -> str:
    """Drop trailing zeros: shorter, and still deterministic."""
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return f"{text or '0'}s"


def frame_track(*, frame_count: int, fps: int) -> Track:
    if frame_count < 1:
        raise ValueError(f"frame_count must be at least 1: {frame_count}")
    if fps < 1:
        raise ValueError(f"fps must be at least 1: {fps}")

    duration = frame_count / fps
    visible_pct = round(100.0 / frame_count, EPSILON_DIGITS)
    delays = tuple(_seconds(-i / fps) if i else "0s" for i in range(frame_count))

    # Last rule wins, so this must follow the default invisible rule.
    first_visible = ".f0{opacity:1}"
    css = (
        f".f{{opacity:0;animation:s {_seconds(duration)} step-end infinite}}"
        f"@keyframes s{{0%{{opacity:1}}{visible_pct}%{{opacity:0}}}}"
        f"{first_visible}"
    )
    return Track(css=css, delays=delays, duration_seconds=duration,
                 first_frame_visible_css=first_visible)
