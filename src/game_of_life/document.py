"""The minimal tools for assembling an SVG document.

Escaping is kept in one place. Pattern names and explanations end up in both
attributes and text, so letting `&` or `<` through breaks the document — and it
breaks it in the hard-to-notice way where only part of the content disappears.

No newlines are emitted, for the byte budget. It also keeps diffs quiet.
"""

from __future__ import annotations

_ESCAPES = (
    ("&", "&amp;"),        # Must come first, or &lt; would become &amp;lt;
    ("<", "&lt;"),
    (">", "&gt;"),
    ('"', "&quot;"),
    ("'", "&#39;"),
)


def escape_text(value: object) -> str:
    text = str(value)
    for raw, escaped in _ESCAPES:
        text = text.replace(raw, escaped)
    return text


class Svg:
    """A self-contained SVG document. Its only external reference is the namespace."""

    def __init__(self, *, width: int, height: int, view_box: str, title: str) -> None:
        if width < 1 or height < 1:
            raise ValueError(f"dimensions must be at least 1: {width}x{height}")
        self._width = width
        self._height = height
        self._view_box = view_box
        self._title = title
        self._style = ""
        self._body: list[str] = []

    def set_style(self, css: str) -> None:
        self._style = css

    def append(self, markup: str) -> None:
        self._body.append(markup)

    def render(self) -> str:
        head = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="{escape_text(self._view_box)}" '
            f'width="{self._width}" height="{self._height}" role="img">'
            f"<title>{escape_text(self._title)}</title>"
        )
        style = f"<style>{self._style}</style>" if self._style else ""
        return head + style + "".join(self._body) + "</svg>"
