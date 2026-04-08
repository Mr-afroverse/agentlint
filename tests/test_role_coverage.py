"""Tests for AL-D04 role coverage completeness."""

from __future__ import annotations

from pathlib import Path

from agentlint.adapters.copilot import CopilotAdapter
from agentlint.checks.role_coverage import run
from agentlint.config import Config
from agentlint.models import Severity

_ADAPTER = CopilotAdapter()


def _collect(root: Path):
    return _ADAPTER.collect(root)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_skill(root: Path, name: str, frontmatter_name: str | None = None) -> None:
    skill_dir = root / ".github" / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    if frontmatter_name:
        content = f"---\nname: {frontmatter_name}\n---\n# Skill\n"
    else:
        content = "# Skill\n"
    (skill_dir / "SKILL.md").write_text(content)


def _write_dispatch(root: Path, content: str = "# Dispatch\n") -> None:
    gh = root / ".github"
    gh.mkdir(parents=True, exist_ok=True)
    (gh / "copilot-instructions.md").write_text(content)


# ---------------------------------------------------------------------------
# AL-D04: no required_roles configured — always passes
# ---------------------------------------------------------------------------


def test_d04_pass_no_config(tmp_path: Path):
    """No required_roles in config — check is a no-op."""
    _write_dispatch(tmp_path)
    _write_skill(tmp_path, "eudr")
    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# AL-D04: all required roles present
# ---------------------------------------------------------------------------


def test_d04_pass_all_roles_present(tmp_path: Path):
    """Every required role has a matching SKILL file by directory name."""
    _write_dispatch(tmp_path)
    _write_skill(tmp_path, "eudr-standards")
    _write_skill(tmp_path, "security")
    _write_skill(tmp_path, "testing")

    cfg = Config()
    cfg.required_roles = ["eudr-standards", "security", "testing"]
    files = _collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    # Use the configured version
    violations = run(files, cfg, tmp_path)
    assert violations == []


def test_d04_pass_roles_matched_by_frontmatter_name(tmp_path: Path):
    """Role matched via frontmatter `name` field, not directory name."""
    _write_dispatch(tmp_path)
    _write_skill(tmp_path, "some-dir", frontmatter_name="security")

    cfg = Config()
    cfg.required_roles = ["security"]
    files = _collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# AL-D04: missing roles
# ---------------------------------------------------------------------------


def test_d04_fail_missing_role(tmp_path: Path):
    """One required role has no SKILL file."""
    _write_dispatch(tmp_path)
    _write_skill(tmp_path, "eudr-standards")

    cfg = Config()
    cfg.required_roles = ["eudr-standards", "security"]
    files = _collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    d04 = [v for v in violations if v.check_id == "AL-D04"]
    assert len(d04) == 1
    assert "security" in d04[0].message
    assert d04[0].severity == Severity.ERROR


def test_d04_fail_all_roles_missing(tmp_path: Path):
    """No SKILL files at all — all required roles fire."""
    _write_dispatch(tmp_path)

    cfg = Config()
    cfg.required_roles = ["eudr", "security", "testing"]
    files = _collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    d04 = [v for v in violations if v.check_id == "AL-D04"]
    assert len(d04) == 3
    missing = {v.message for v in d04}
    assert any("eudr" in m for m in missing)
    assert any("security" in m for m in missing)
    assert any("testing" in m for m in missing)


def test_d04_fail_reports_on_dispatch_file(tmp_path: Path):
    """Violation is reported on the dispatch file path."""
    dispatch_path = tmp_path / ".github" / "copilot-instructions.md"
    _write_dispatch(tmp_path)

    cfg = Config()
    cfg.required_roles = ["ghost"]
    files = _collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    d04 = [v for v in violations if v.check_id == "AL-D04"]
    assert len(d04) == 1
    assert d04[0].file == dispatch_path


def test_d04_fail_no_dispatch_reports_on_root(tmp_path: Path):
    """Without a dispatch file, violation is reported without crashing."""
    # A skill exists but no dispatch
    skill_dir = tmp_path / ".github" / "skills" / "eudr"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# EUDR")

    cfg = Config()
    cfg.required_roles = ["ghost"]
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    d04 = [v for v in violations if v.check_id == "AL-D04"]
    assert len(d04) == 1


# ---------------------------------------------------------------------------
# AL-D04: config loading from YAML
# ---------------------------------------------------------------------------


def test_d04_config_loaded_from_yaml(tmp_path: Path):
    """required_roles parsed from .agentlint.yml."""
    _write_dispatch(tmp_path)
    _write_skill(tmp_path, "eudr-standards")

    (tmp_path / ".agentlint.yml").write_text(
        "required_roles:\n  - eudr-standards\n  - missing-role\n"
    )
    cfg = Config.load(tmp_path)
    assert cfg.required_roles == ["eudr-standards", "missing-role"]

    files = _collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    d04 = [v for v in violations if v.check_id == "AL-D04"]
    assert len(d04) == 1
    assert "missing-role" in d04[0].message
