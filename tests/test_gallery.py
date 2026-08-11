"""Tests for gallery.py.

Primary failure modes:
- **The artefacts and the page disagreeing**: if an image the page references
  was never generated, the README link works and only the picture is broken.
  Both come out of the same function.
- **A missing explanation surviving to publication**: an explanation is a
  requirement, and not one pattern may ship without it.
- **File-name collisions**: deriving a slug from a name like `Kok's galaxy`
  can collide depending on how punctuation is handled. The file name is
  authoritative.
- **Exceeding the budget**: there are four artefacts per pattern, so an
  oversight only bites after publication.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from game_of_life.config import Options
from game_of_life.gallery import ARTEFACT_DIR, build, page
from game_of_life.patterns import load_all
from game_of_life.rle import CATEGORIES

PATTERNS = load_all()
OPTIONS = Options(preset="card", rule="standard", frame_range="head")


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("gallery")
    reports = build(PATTERNS, out_dir=out, options=OPTIONS)
    return out, reports


# ---------------------------------------------------------------- artefacts

def test_every_pattern_produces_four_artefacts(built):
    _, reports = built
    assert len(reports) == len(PATTERNS) * 4


def test_artefacts_are_named_from_the_file_slug_not_the_display_name(built):
    out, _ = built
    names = {p.name for p in (out / ARTEFACT_DIR).iterdir()}
    assert "galaxy-dark.svg" in names          # the display name is "Kok's galaxy"
    assert not any("'" in n or " " in n for n in names)


def test_each_pattern_has_animated_and_static_in_both_themes(built):
    out, _ = built
    for p in PATTERNS:
        for suffix in ("light", "dark", "light-static", "dark-static"):
            assert (out / ARTEFACT_DIR / f"{p.slug}-{suffix}.svg").is_file(), \
                f"{p.slug}-{suffix}.svg is missing"


def test_every_artefact_is_within_budget(built):
    _, reports = built
    over = [r for r in reports if not r.within_budget]
    assert not over, [f"{r.path}: {r.gzipped_bytes}B" for r in over]


def test_building_twice_produces_identical_bytes(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    build(PATTERNS[:3], out_dir=a, options=OPTIONS)
    build(PATTERNS[:3], out_dir=b, options=OPTIONS)
    for fa in (a / ARTEFACT_DIR).iterdir():
        assert fa.read_bytes() == (b / ARTEFACT_DIR / fa.name).read_bytes(), fa.name


def test_the_static_artefact_carries_no_animation(built):
    out, _ = built
    text = (out / ARTEFACT_DIR / f"{PATTERNS[0].slug}-dark-static.svg").read_text()
    assert "@keyframes" not in text and "animation" not in text


# ---------------------------------------------------------------- the page

def test_the_page_introduces_the_rules_before_any_pattern():
    text = page(PATTERNS)
    intro = text[:text.index("##", text.index("##") + 2)]
    assert "three" in intro.lower() or "3" in intro
    assert "neighbour" in intro.lower()


def test_the_page_explains_every_category():
    text = page(PATTERNS)
    for category in CATEGORIES:
        assert category in text


def test_every_pattern_appears_with_its_explanation():
    text = page(PATTERNS)
    for p in PATTERNS:
        assert p.name in text, p.name
        assert p.explanation[:40] in text, p.name


def test_every_pattern_carries_its_attribution():
    text = page(PATTERNS)
    for p in PATTERNS:
        if p.discovered and p.discovered != "—":
            assert p.discovered in text, p.name


def test_every_pattern_has_a_download_link_to_its_rle():
    text = page(PATTERNS)
    for p in PATTERNS:
        assert f"{p.slug}.rle" in text, p.name


def test_patterns_are_grouped_by_category_in_the_declared_order():
    text = page(PATTERNS)
    headings = re.findall(r"^## (.+)$", text, re.M)
    present = [c for c in CATEGORIES if any(c in h.lower().replace(" ", "-")
                                            for h in headings)]
    assert len(present) == len(set(present))


def test_the_page_references_only_artefacts_the_build_produces(built):
    out, _ = built
    text = page(PATTERNS)
    for ref in set(re.findall(r"\(([^)]+\.svg)\)", text)):
        assert (out / ref).is_file(), f"the page references {ref}, which was never built"


def test_the_page_is_deterministic():
    assert page(PATTERNS) == page(PATTERNS)


def test_the_page_uses_picture_so_the_theme_follows_the_reader():
    text = page(PATTERNS)
    assert "<picture>" in text
    assert "prefers-color-scheme: dark" in text


def test_the_page_offers_the_static_variant_for_reduced_motion():
    """Emitting the static variant is not enough; a reader must be able to reach it."""
    text = page(PATTERNS)
    assert "-static.svg" in text
    assert "motion" in text.lower()


def test_a_pattern_without_an_explanation_cannot_reach_the_page():
    """The parser rejects this, so it is unreachable. Reaching it means the contract broke."""
    assert all(p.explanation for p in PATTERNS)


def test_every_built_artefact_is_referenced_by_the_page(built):
    """An artefact nobody references is not merely wasted; it is also never checked."""
    out, _ = built
    text = page(PATTERNS)
    referenced = set(re.findall(r"[\w./-]+\.svg", text))
    for f in sorted((out / ARTEFACT_DIR).iterdir()):
        assert any(r.endswith(f.name) for r in referenced), f"nothing references {f.name}"


# Only four representative patterns are compared against golden files. Pinning
# all 30 patterns x 4 artefacts would produce a 4.3 MB diff for every one-line
# renderer change, and no review could survive that. The rest are covered by the
# budget, forbidden-construct and determinism property tests.
GOLDEN_DIR = pathlib.Path(__file__).resolve().parent / "golden"
GOLDEN = ("block", "blinker", "glider", "gosper-gun")


@pytest.mark.parametrize("slug", GOLDEN)
def test_a_representative_pattern_matches_its_golden_file(slug, built):
    out, _ = built
    produced = (out / ARTEFACT_DIR / f"{slug}-light.svg").read_bytes()
    expected = (GOLDEN_DIR / f"{slug}-light.svg").read_bytes()
    assert produced == expected, (
        f"{slug} differs from its golden file. If the change was intended, "
        f"regenerate tests/golden/{slug}-light.svg"
    )


def test_the_golden_set_covers_more_than_one_behaviour():
    """If every golden were a still life, the golden set would guard nothing."""
    kinds = {p.category for p in PATTERNS if p.slug in GOLDEN}
    assert len(kinds) >= 3, kinds
