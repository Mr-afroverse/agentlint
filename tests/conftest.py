"""Shared fixtures for agentlint tests."""

from __future__ import annotations

from pathlib import Path
import pytest


# ---------------------------------------------------------------------------
# Minimal valid Copilot instruction set
# ---------------------------------------------------------------------------

DISPATCH_CONTENT = """\
# Copilot Instructions

## Active Skills

| Skill | File | Trigger |
|-------|------|---------|
| `eudr-standards` | `.github/skills/eudr-standards/SKILL.md` | Any validation or scoring code |
| `tdd-fastapi` | `.github/skills/tdd-fastapi/SKILL.md` | Adding any new feature or route |
"""

SKILL_EUDR_CONTENT = """\
````skill
---
name: eudr-standards
description: Use when writing validation or scoring code for EUDR compliance.
---

# EUDR Standards

> **Source of truth:** `app/services/validation/constants.py` — all thresholds.

Field weights come from `constants.py`. Always read it before writing scoring logic.
````
"""

SKILL_TDD_CONTENT = """\
````skill
---
name: tdd-fastapi
description: Use when adding any new feature or route to the FastAPI application.
---

# TDD FastAPI

Write the test first. Then implement. Always.
````
"""


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Minimal valid Copilot repo — all checks should pass."""
    _build_copilot_repo(
        tmp_path, DISPATCH_CONTENT, SKILL_EUDR_CONTENT, SKILL_TDD_CONTENT
    )
    return tmp_path


def _build_copilot_repo(
    root: Path,
    dispatch: str,
    skill_eudr: str = SKILL_EUDR_CONTENT,
    skill_tdd: str = SKILL_TDD_CONTENT,
) -> Path:
    skills = root / ".github" / "skills"
    (skills / "eudr-standards").mkdir(parents=True)
    (skills / "tdd-fastapi").mkdir(parents=True)
    (root / ".github" / "copilot-instructions.md").write_text(
        dispatch, encoding="utf-8"
    )
    (skills / "eudr-standards" / "SKILL.md").write_text(skill_eudr, encoding="utf-8")
    (skills / "tdd-fastapi" / "SKILL.md").write_text(skill_tdd, encoding="utf-8")
    return root
