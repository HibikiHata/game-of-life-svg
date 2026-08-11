"""Shared test configuration.

At run time the package is imported as `game_of_life` with `PYTHONPATH=<repo>/src`,
so the tests use the same import form.

The tests never touch the network. The calendar is only ever read through an
injected `fetch`, and boards are built from hand-computed fixtures.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
