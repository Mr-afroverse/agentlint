from __future__ import annotations

from pathlib import Path

from agentlint.adapters.copilot import CopilotAdapter
from agentlint.checks.forbidden_patterns import run
from agentlint.config import Config
from agentlint.models import Severity

_ADAPTER = CopilotAdapter()


def _make_skill(root: Path, content: str) -> None:
    skill_dir = root / ".github" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")
    dispatch = "| `t` | `.github/skills/test-skill/SKILL.md` | test |\n"
    (root / ".github" / "copilot-instructions.md").write_text(dispatch)


def test_p01_pass_no_bare_test_count(tmp_path: Path):
    _make_skill(tmp_path, "Run `pytest tests/ -q` for the live count.\n")
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert [v for v in violations if v.check_id == "AL-P01"] == []


def test_p01_fail_hardcoded_test_count(tmp_path: Path):
    _make_skill(tmp_path, "1338 tests passing in v2.0.\n")
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    p01 = [v for v in violations if v.check_id == "AL-P01"]
    assert len(p01) == 1
    assert p01[0].severity == Severity.ERROR


def test_custom_forbidden_pattern(tmp_path: Path):
    cfg = Config()
    cfg.forbidden_patterns.append(
        {
            "id": "MY001",
            "pattern": r"\bdo not use this\b",
            "reason": "Forbidden phrase.",
            "fix": "Remove it.",
            "severity": "warning",
        }
    )
    _make_skill(tmp_path, "Please do not use this pattern.\n")
    files = _ADAPTER.collect(tmp_path)
    run(files, Config(), tmp_path)  # default config has no custom pattern
    # Custom pattern added to instance, not global Config()
    violations2 = run(files, cfg, tmp_path)
    my = [v for v in violations2 if v.check_id == "MY001"]
    assert len(my) == 1
    assert my[0].severity == Severity.WARNING


def test_ignore_path_skips_file(tmp_path: Path):
    _make_skill(tmp_path, "1338 tests passing.\n")
    cfg = Config()
    cfg.ignore_paths = [".github/skills/test-skill"]
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    assert violations == []


def test_invalid_regex_pattern_skipped(tmp_path: Path):
    """A forbidden pattern with invalid regex is silently skipped, not a crash."""
    cfg = Config()
    cfg.forbidden_patterns = [
        {
            "id": "BAD-RE",
            "pattern": "[invalid regex",
            "reason": "broken",
            "fix": "fix it",
            "severity": "error",
        }
    ]
    _make_skill(tmp_path, "This content should not crash the checker.\n")
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    assert violations == []


def test_invalid_severity_falls_back_to_error(tmp_path: Path):
    """A forbidden pattern with an unrecognised severity falls back to ERROR."""
    cfg = Config()
    cfg.forbidden_patterns = [
        {
            "id": "BAD-SEV",
            "pattern": r"\bbad_word\b",
            "reason": "not allowed",
            "fix": "remove it",
            "severity": "INVALID_SEVERITY",
        }
    ]
    _make_skill(tmp_path, "Contains bad_word here.\n")
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    assert len(violations) == 1
    assert violations[0].severity == Severity.ERROR
