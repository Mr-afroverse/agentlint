from __future__ import annotations

from pathlib import Path

import pytest

from agentlint.adapters.copilot import CopilotAdapter
from agentlint.checks.dispatch_coverage import run
from agentlint.config import Config
from agentlint.models import Severity


_ADAPTER = CopilotAdapter()


def _collect(root: Path):
    return _ADAPTER.collect(root)


# ---------------------------------------------------------------------------
# AL-D01: skill path referenced in dispatch → must exist on disk
# ---------------------------------------------------------------------------


def test_d01_pass_all_paths_exist(repo_root: Path):
    files = _collect(repo_root)
    violations = run(files, Config(), repo_root)
    d01 = [v for v in violations if v.check_id == "AL-D01"]
    assert d01 == [], "Expected no AL-D01 violations when all paths exist."


def test_d01_fail_missing_skill_file(tmp_path: Path):
    # Dispatch references a skill that doesn't exist on disk
    (tmp_path / ".github" / "skills" / "eudr-standards").mkdir(parents=True)
    dispatch = (
        "| `eudr` | `.github/skills/eudr-standards/SKILL.md` | Any scoring |\n"
        "| `ghost` | `.github/skills/ghost/SKILL.md` | Ghost skill |\n"
    )
    (tmp_path / ".github" / "copilot-instructions.md").write_text(dispatch)
    (tmp_path / ".github" / "skills" / "eudr-standards" / "SKILL.md").write_text("# EUDR")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d01 = [v for v in violations if v.check_id == "AL-D01"]
    assert len(d01) == 1
    assert "ghost" in d01[0].message
    assert d01[0].severity == Severity.ERROR


# ---------------------------------------------------------------------------
# AL-D02: skill on disk → must be referenced in dispatch
# ---------------------------------------------------------------------------


def test_d02_pass_all_skills_in_dispatch(repo_root: Path):
    files = _collect(repo_root)
    violations = run(files, Config(), repo_root)
    d02 = [v for v in violations if v.check_id == "AL-D02"]
    assert d02 == []


def test_d02_fail_skill_not_in_dispatch(tmp_path: Path):
    skills = tmp_path / ".github" / "skills"
    (skills / "eudr-standards").mkdir(parents=True)
    (skills / "orphan-skill").mkdir(parents=True)

    # Dispatch only references eudr, not orphan
    dispatch = "| `eudr` | `.github/skills/eudr-standards/SKILL.md` | Any scoring |\n"
    (tmp_path / ".github" / "copilot-instructions.md").write_text(dispatch)
    (skills / "eudr-standards" / "SKILL.md").write_text("# EUDR")
    (skills / "orphan-skill" / "SKILL.md").write_text("# Orphan")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    d02 = [v for v in violations if v.check_id == "AL-D02"]
    assert len(d02) == 1
    assert "orphan" in d02[0].message.lower()


def test_no_dispatch_file_returns_empty(tmp_path: Path):
    # No dispatch file at all — checks should return nothing gracefully
    skills = tmp_path / ".github" / "skills" / "my-skill"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("# My Skill")

    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert violations == []
