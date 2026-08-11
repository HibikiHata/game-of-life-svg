"""Bake Conway's Game of Life into self-contained animated SVG files.

One engine produces two artefacts: a gallery of well-known patterns, each
downloadable as a single file, and a daily widget built from a GitHub
contribution graph.

The artefacts are drawn inside an `<img>` on GitHub, where JavaScript never
runs. Frames are therefore precomputed and switched with CSS `step-end` plus a
negative `animation-delay`.
"""
