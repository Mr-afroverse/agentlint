from __future__ import annotations

from pathlib import Path

from agentlint.checks.frontmatter_schema import run
from agentlint.config import Config
from agentlint.models import InstructionFile, Role


def _skill(tmp_path: Path, metadata: dict, name: str = "SKILL.md") -> InstructionFile:
    p = tmp_path / name
    p.write_text("# content", encoding="utf-8")
    return InstructionFile(
        path=p,
        content="# content",
        lines=["# content"],
        adapter="copilot",
        role=Role.SKILL,
        metadata=metadata,
    )


def _dispatch(tmp_path: Path) -> InstructionFile:
    p = tmp_path / "copilot-instructions.md"
    p.write_text("", encoding="utf-8")
    return InstructionFile(
        path=p,
        content="",
        lines=[],
        adapter="copilot",
        role=Role.DISPATCH,
        metadata={},
    )


# ---------------------------------------------------------------------------
# disabled by default
# ---------------------------------------------------------------------------


def test_disabled_when_required_frontmatter_empty(tmp_path: Path):
    config = Config()  # required_frontmatter = [] by default
    f = _skill(tmp_path, {})
    assert run([f], config, tmp_path) == []


# ---------------------------------------------------------------------------
# passes when all required keys are present
# ---------------------------------------------------------------------------


def test_passes_when_all_keys_present(tmp_path: Path):
    config = Config()
    config.required_frontmatter = ["name", "description"]
    f = _skill(tmp_path, {"name": "my-skill", "description": "Does X"})
    assert run([f], config, tmp_path) == []


def test_passes_with_extra_keys_present(tmp_path: Path):
    config = Config()
    config.required_frontmatter = ["name"]
    f = _skill(tmp_path, {"name": "skill", "extra_key": "value"})
    assert run([f], config, tmp_path) == []


# ---------------------------------------------------------------------------
# fires when keys are missing
# ---------------------------------------------------------------------------


def test_fires_when_all_keys_missing(tmp_path: Path):
    config = Config()
    config.required_frontmatter = ["name", "description"]
    f = _skill(tmp_path, {})
    violations = run([f], config, tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-FM01"
    assert "name" in violations[0].message
    assert "description" in violations[0].message


def test_fires_when_one_key_missing(tmp_path: Path):
    config = Config()
    config.required_frontmatter = ["name", "description"]
    f = _skill(tmp_path, {"name": "present"})
    violations = run([f], config, tmp_path)
    assert len(violations) == 1
    assert "description" in violations[0].message
    assert "name" not in violations[0].message


def test_one_violation_per_file_not_per_key(tmp_path: Path):
    config = Config()
    config.required_frontmatter = ["a", "b", "c"]
    f = _skill(tmp_path, {})
    violations = run([f], config, tmp_path)
    assert len(violations) == 1


def test_violation_severity_is_warning(tmp_path: Path):
    config = Config()
    config.required_frontmatter = ["name"]
    f = _skill(tmp_path, {})
    violations = run([f], config, tmp_path)
    assert violations[0].severity.value == "warning"


# ---------------------------------------------------------------------------
# only SKILL files are checked
# ---------------------------------------------------------------------------


def test_dispatch_file_not_checked(tmp_path: Path):
    config = Config()
    config.required_frontmatter = ["name"]
    d = _dispatch(tmp_path)
    assert run([d], config, tmp_path) == []


# ---------------------------------------------------------------------------
# ignore_paths
# ---------------------------------------------------------------------------


def test_ignore_paths_respected(tmp_path: Path):
    config = Config()
    config.required_frontmatter = ["name"]
    config.ignore_paths = ["SKILL.md"]
    f = _skill(tmp_path, {})
    assert run([f], config, tmp_path) == []
