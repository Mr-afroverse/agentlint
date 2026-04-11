from __future__ import annotations

from pathlib import Path

from agentlint.checks.deprecated_patterns import run
from agentlint.config import Config
from agentlint.models import InstructionFile, Role, Severity


def _make_file(tmp_path: Path, name: str, content: str) -> InstructionFile:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return InstructionFile(
        path=p,
        role=Role.DISPATCH,
        content=content,
        lines=content.splitlines(keepends=True),
        adapter="copilot",
    )


# ---------------------------------------------------------------------------
# Empty config — disabled by default
# ---------------------------------------------------------------------------


def test_no_patterns_no_violations(tmp_path: Path):
    f = _make_file(tmp_path, "SKILL.md", "Use gpt-4-0613 for everything.\n")
    cfg = Config()
    assert cfg.deprecated_patterns == []
    violations = run([f], cfg, tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Basic matching
# ---------------------------------------------------------------------------


def test_single_pattern_fires(tmp_path: Path):
    f = _make_file(tmp_path, "SKILL.md", "Use the gpt-4-0613 model.\n")
    cfg = Config()
    cfg.deprecated_patterns = [
        {
            "pattern": "gpt-4-0613",
            "reason": "Deprecated model.",
            "replacement": "gpt-4o",
        }
    ]
    violations = run([f], cfg, tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-DEP01"
    assert violations[0].severity == Severity.WARNING
    assert "Deprecated model" in violations[0].message
    assert "gpt-4o" in violations[0].fix_hint


def test_multiple_patterns_each_fire(tmp_path: Path):
    content = "Use gpt-4-0613 and text-davinci-003.\n"
    f = _make_file(tmp_path, "SKILL.md", content)
    cfg = Config()
    cfg.deprecated_patterns = [
        {"pattern": "gpt-4-0613", "reason": "Old model."},
        {"pattern": "text-davinci-003", "reason": "Legacy model."},
    ]
    violations = run([f], cfg, tmp_path)
    ids = {v.check_id for v in violations}
    assert ids == {"AL-DEP01", "AL-DEP02"}


def test_no_match_no_violation(tmp_path: Path):
    f = _make_file(tmp_path, "SKILL.md", "Use gpt-4o for everything.\n")
    cfg = Config()
    cfg.deprecated_patterns = [{"pattern": "gpt-4-0613", "reason": "Deprecated."}]
    violations = run([f], cfg, tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------


def test_error_severity_respected(tmp_path: Path):
    f = _make_file(tmp_path, "SKILL.md", "Use legacy-api-v1 here.\n")
    cfg = Config()
    cfg.deprecated_patterns = [
        {"pattern": "legacy-api-v1", "reason": "Removed.", "severity": "error"}
    ]
    violations = run([f], cfg, tmp_path)
    assert violations[0].severity == Severity.ERROR


def test_invalid_severity_falls_back_to_warning(tmp_path: Path):
    f = _make_file(tmp_path, "SKILL.md", "Use legacy-api-v1.\n")
    cfg = Config()
    cfg.deprecated_patterns = [
        {"pattern": "legacy-api-v1", "reason": "Removed.", "severity": "INVALID"}
    ]
    violations = run([f], cfg, tmp_path)
    assert violations[0].severity == Severity.WARNING


# ---------------------------------------------------------------------------
# Custom ID
# ---------------------------------------------------------------------------


def test_custom_id_used(tmp_path: Path):
    f = _make_file(tmp_path, "SKILL.md", "gpt-4-0613 here.\n")
    cfg = Config()
    cfg.deprecated_patterns = [
        {"pattern": "gpt-4-0613", "reason": "Old.", "id": "AL-MYORG01"}
    ]
    violations = run([f], cfg, tmp_path)
    assert violations[0].check_id == "AL-MYORG01"


def test_default_id_numbering(tmp_path: Path):
    content = "model-a and model-b.\n"
    f = _make_file(tmp_path, "SKILL.md", content)
    cfg = Config()
    cfg.deprecated_patterns = [
        {"pattern": "model-a", "reason": "Old."},
        {"pattern": "model-b", "reason": "Old."},
    ]
    violations = run([f], cfg, tmp_path)
    ids = sorted(v.check_id for v in violations)
    assert ids == ["AL-DEP01", "AL-DEP02"]


# ---------------------------------------------------------------------------
# ignore_paths
# ---------------------------------------------------------------------------


def test_ignore_paths_suppresses(tmp_path: Path):
    f = _make_file(tmp_path, "archive/SKILL.md", "Use gpt-4-0613.\n")
    cfg = Config()
    cfg.deprecated_patterns = [{"pattern": "gpt-4-0613", "reason": "Old."}]
    cfg.ignore_paths = ["archive/"]
    violations = run([f], cfg, tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Bad regex — skipped silently
# ---------------------------------------------------------------------------


def test_bad_regex_skipped_silently(tmp_path: Path):
    f = _make_file(tmp_path, "SKILL.md", "Use gpt-4-0613.\n")
    cfg = Config()
    cfg.deprecated_patterns = [
        {"pattern": "[invalid", "reason": "Bad pattern."},
        {"pattern": "gpt-4-0613", "reason": "Deprecated."},
    ]
    violations = run([f], cfg, tmp_path)
    # Bad pattern silently skipped; valid one fires
    assert len(violations) == 1
    assert violations[0].check_id == "AL-DEP02"


# ---------------------------------------------------------------------------
# Config loading from YAML
# ---------------------------------------------------------------------------


def test_config_loads_deprecated_patterns_from_yaml(tmp_path: Path):
    yml = tmp_path / ".agentlint.yml"
    yml.write_text(
        "deprecated_patterns:\n"
        "  - pattern: gpt-4-0613\n"
        "    reason: Deprecated model.\n"
        "    replacement: gpt-4o\n",
        encoding="utf-8",
    )
    cfg = Config.load(tmp_path)
    assert len(cfg.deprecated_patterns) == 1
    assert cfg.deprecated_patterns[0]["pattern"] == "gpt-4-0613"
    assert cfg.deprecated_patterns[0]["replacement"] == "gpt-4o"


# ---------------------------------------------------------------------------
# fix_hint absent when no replacement supplied
# ---------------------------------------------------------------------------


def test_no_replacement_means_empty_fix_hint(tmp_path: Path):
    f = _make_file(tmp_path, "SKILL.md", "Use gpt-4-0613.\n")
    cfg = Config()
    cfg.deprecated_patterns = [{"pattern": "gpt-4-0613", "reason": "Old."}]
    violations = run([f], cfg, tmp_path)
    assert violations[0].fix_hint == ""


# ---------------------------------------------------------------------------
# auto_fixable / fix_data
# ---------------------------------------------------------------------------


def test_with_replacement_is_auto_fixable(tmp_path: Path):
    f = _make_file(tmp_path, "SKILL.md", "Use gpt-4-0613 for everything.\n")
    cfg = Config()
    cfg.deprecated_patterns = [
        {"pattern": "gpt-4-0613", "reason": "Deprecated.", "replacement": "gpt-4o"}
    ]
    violations = run([f], cfg, tmp_path)
    assert violations[0].auto_fixable is True
    assert (
        violations[0].fix_data["old_line"].strip() == "Use gpt-4-0613 for everything."
    )
    assert violations[0].fix_data["new_line"].strip() == "Use gpt-4o for everything."


def test_without_replacement_not_auto_fixable(tmp_path: Path):
    f = _make_file(tmp_path, "SKILL.md", "Use gpt-4-0613 for everything.\n")
    cfg = Config()
    cfg.deprecated_patterns = [{"pattern": "gpt-4-0613", "reason": "Deprecated."}]
    violations = run([f], cfg, tmp_path)
    assert violations[0].auto_fixable is False
    assert violations[0].fix_data == {}
