"""The palettes.

GitHub's own contribution colours are used, because the widget reading as a
contribution graph is what makes it mean "this is my year".

For the four decay levels **colour is the only signal**, so information is lost
if adjacent levels do not contrast enough. That is what `contrast_ratio` is
for, and test_theme.py checks it for real.
"""

from __future__ import annotations

from dataclasses import dataclass

MODES = ("light", "dark")

_PALETTES = {
    "dark": ("#0d1117", ("#0e4429", "#006d32", "#26a641", "#39d353")),
    "light": ("#ffffff", ("#9be9a8", "#40c463", "#30a14e", "#216e39")),
}


@dataclass(frozen=True)
class Theme:
    mode: str
    background: str
    levels: tuple[str, str, str, str]

    def colour_for(self, level: int, max_level: int) -> str:
        """Map a level to a colour. The standard rule (max_level=1) uses the strongest."""
        if not 1 <= level <= max_level:
            raise ValueError(f"level out of range: {level} (1..{max_level})")
        if max_level == 1:
            return self.levels[-1]
        return self.levels[level - 1]


def theme_of(mode: str) -> Theme:
    if mode not in MODES:
        raise ValueError(f"invalid mode: {mode!r} (expected {' / '.join(MODES)})")
    background, levels = _PALETTES[mode]
    return Theme(mode=mode, background=background, levels=levels)


def _channel(value: int) -> float:
    c = value / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(colour: str) -> float:
    h = colour.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"colours must be given as #rrggbb: {colour!r}")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(a: str, b: str) -> float:
    """The WCAG contrast ratio: 1.0 (identical) to 21.0 (black against white)."""
    la, lb = _luminance(a), _luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)
