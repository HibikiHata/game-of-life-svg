"""Unit tests for document.py.

Primary failure modes:
- **Missed escaping**: pattern names and explanations land in both attributes
  and text, so letting `&` or `<` through breaks the SVG — and it breaks by
  making part of the content disappear, which is easy to miss.
- **An external reference slipping in**: a single attribute containing `http`
  makes the file no longer self-contained. The namespace declaration is the
  only exception.
"""

from __future__ import annotations

import xml.dom.minidom

import pytest

from game_of_life.document import Svg, escape_text


# ---------------------------------------------------------------- escaping

@pytest.mark.parametrize("raw,expected", [
    ("a & b", "a &amp; b"),
    ("<tag>", "&lt;tag&gt;"),
    ('say "hi"', "say &quot;hi&quot;"),
    ("it's", "it&#39;s"),
    ("plain", "plain"),
])
def test_escape_text_covers_every_xml_significant_character(raw, expected):
    assert escape_text(raw) == expected


def test_ampersand_is_escaped_before_the_others():
    """In the wrong order, &lt; would become &amp;lt;."""
    assert escape_text("<&>") == "&lt;&amp;&gt;"


def test_non_string_values_are_accepted():
    assert escape_text(12) == "12"


# ---------------------------------------------------------------- assembly

def test_a_minimal_document_is_well_formed_xml():
    # What is parsed is this test's own output, not external input. It cannot
    # contain external entities, so there is no XXE path and the standard
    # library suffices — the package takes no third-party dependencies.
    svg = Svg(width=20, height=10, view_box="0 0 2 1", title="t")
    xml.dom.minidom.parseString(svg.render())


def test_the_document_declares_role_img_and_a_title():
    out = Svg(width=20, height=10, view_box="0 0 2 1", title="Life").render()
    assert 'role="img"' in out
    assert "<title>Life</title>" in out


def test_the_title_is_escaped():
    out = Svg(width=20, height=10, view_box="0 0 2 1", title="a & b").render()
    assert "a &amp; b" in out


def test_the_only_external_looking_string_is_the_svg_namespace():
    out = Svg(width=20, height=10, view_box="0 0 2 1", title="t").render()
    assert out.count("http") == 1
    assert 'xmlns="http://www.w3.org/2000/svg"' in out


def test_no_script_or_foreign_object_can_appear():
    out = Svg(width=20, height=10, view_box="0 0 2 1", title="t").render()
    assert "<script" not in out and "foreignObject" not in out


def test_appended_content_appears_in_order():
    svg = Svg(width=20, height=10, view_box="0 0 2 1", title="t")
    svg.append("<g id='a'/>")
    svg.append("<g id='b'/>")
    out = svg.render()
    assert out.index("id='a'") < out.index("id='b'")


def test_style_is_emitted_before_content():
    svg = Svg(width=20, height=10, view_box="0 0 2 1", title="t")
    svg.set_style(".f{opacity:0}")
    svg.append("<g/>")
    out = svg.render()
    assert out.index("<style>") < out.index("<g/>")


def test_two_documents_with_the_same_inputs_are_byte_identical():
    def build():
        s = Svg(width=20, height=10, view_box="0 0 2 1", title="t")
        s.set_style(".f{opacity:0}")
        s.append("<g/>")
        return s.render()
    assert build() == build()


def test_the_rendered_document_carries_no_newline_padding():
    """A convention for the byte budget. It also keeps diffs quiet."""
    out = Svg(width=20, height=10, view_box="0 0 2 1", title="t").render()
    assert "\n" not in out


@pytest.mark.parametrize("bad", [0, -1])
def test_non_positive_dimensions_are_rejected(bad):
    with pytest.raises(ValueError):
        Svg(width=bad, height=10, view_box="0 0 2 1", title="t")
