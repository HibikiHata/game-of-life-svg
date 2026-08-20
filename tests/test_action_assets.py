"""Checks on action.yml and the daily workflow.

Primary failure modes:
- **The token reaches an argument or a log**: it is passed only through the
  environment.
- **A `${{ }}` value is interpolated raw into `run:`**: that is a workflow
  injection path. What is accepted here is the repository owner's own name and
  the adopter's own inputs, but adopters set those inputs freely, so raw
  interpolation stays in scope for review.
- **`permissions:` is forgotten**: on a repository whose default is broad, the
  job would silently run over-privileged.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
ACTION_PATH = ROOT / "action.yml"
DAILY_PATH = ROOT / ".github/workflows/daily.yml"
ACTION = yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))
DAILY = yaml.safe_load(DAILY_PATH.read_text(encoding="utf-8"))


def test_the_action_takes_a_user_name_and_an_optional_token():
    assert ACTION["inputs"]["github_user_name"]["required"] is True
    token = ACTION["inputs"]["github_token"]
    assert token["required"] is False
    assert "github.token" in token["default"]


def test_the_action_passes_the_token_only_through_the_environment():
    step = ACTION["runs"]["steps"][0]
    assert "GITHUB_TOKEN" in step["env"]
    assert "--token" not in step["run"]


def test_the_workflow_declares_permissions_explicitly():
    assert DAILY["permissions"] == {"contents": "write"}


def test_the_workflow_is_scheduled_with_cron():
    on = DAILY[True] if True in DAILY else DAILY["on"]
    assert "schedule" in on and "cron" in on["schedule"][0]


def test_the_workflow_can_be_run_by_hand():
    """The way back when sixty days of inactivity have disabled the schedule."""
    on = DAILY[True] if True in DAILY else DAILY["on"]
    assert "workflow_dispatch" in on


def test_third_party_actions_are_pinned_by_commit_sha():
    for job in DAILY["jobs"].values():
        for step in job["steps"]:
            if "uses" in step:
                ref = step["uses"].split("@")[1]
                assert re.fullmatch(r"[0-9a-f]{40}", ref), step["uses"]


def test_the_workflow_serialises_its_runs():
    assert DAILY["concurrency"]["cancel-in-progress"] is False


def test_the_push_step_refuses_to_publish_an_empty_directory():
    push = [s for s in DAILY["jobs"]["build"]["steps"] if s.get("name") == "Push"][0]
    assert "ls -A output" in push["run"]
    assert "set -euo pipefail" in push["run"]


def test_no_untrusted_event_field_is_interpolated_into_a_shell_command():
    """Interpolating github.event.* raw into `run:` is an injection path."""
    text = DAILY_PATH.read_text(encoding="utf-8")
    assert "github.event." not in text


def test_the_readme_publish_snippet_matches_the_workflow():
    """The README drifted from daily.yml: it published the directory itself,
    so every URL it then told the adopter to copy needed `output` twice."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "mv output/*.svg ." in readme
    assert "git add -f output\n" not in readme
