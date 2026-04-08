from __future__ import annotations

from pathlib import Path

from agentlint.checks.inverse_claims import run
from agentlint.config import Config
from agentlint.models import InstructionFile, Role, Severity


def _make_file(path: Path, content: str, role: Role = Role.SKILL) -> InstructionFile:
    return InstructionFile(
        path=path,
        content=content,
        lines=content.splitlines(keepends=True),
        adapter="test",
        role=role,
    )


# ---------------------------------------------------------------------------
# No violation — negation claim but referenced path not on disk
# ---------------------------------------------------------------------------


def test_clean_when_path_not_on_disk(tmp_path: Path):
    instr = tmp_path / "LIMITATIONS.md"
    content = "There is no `agents/alerter.py` in this system.\n"
    instr.write_text(content, encoding="utf-8")
    violations = run([_make_file(instr, content)], Config(), tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# No violation — path exists but no negation on that line
# ---------------------------------------------------------------------------


def test_clean_no_negation_on_line(tmp_path: Path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "alerter.py").write_text("", encoding="utf-8")
    instr = tmp_path / "SKILL.md"
    content = "Use `agents/alerter.py` for all notification logic.\n"
    instr.write_text(content, encoding="utf-8")
    violations = run([_make_file(instr, content)], Config(), tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# No violation — backtick token is not path-like (no separator, no extension)
# ---------------------------------------------------------------------------


def test_clean_token_not_path_like(tmp_path: Path):
    instr = tmp_path / "SKILL.md"
    content = "This module does not have `streaming` support.\n"
    instr.write_text(content, encoding="utf-8")
    violations = run([_make_file(instr, content)], Config(), tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Violation: "there is no `X`" — path exists
# ---------------------------------------------------------------------------


def test_violation_neg_before_there_is_no(tmp_path: Path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "alerter.py").write_text("", encoding="utf-8")
    instr = tmp_path / "LIMITATIONS.md"
    content = "There is no `agents/alerter.py` in this codebase.\n"
    instr.write_text(content, encoding="utf-8")
    violations = run([_make_file(instr, content)], Config(), tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-INV01"
    assert violations[0].severity == Severity.WARNING
    assert violations[0].line == 1


# ---------------------------------------------------------------------------
# Violation: "does not have `X`" — path exists
# ---------------------------------------------------------------------------


def test_violation_neg_before_does_not_have(tmp_path: Path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "auth.py").write_text("", encoding="utf-8")
    instr = tmp_path / "ARCH.md"
    content = "The system does not have `config/auth.py`.\n"
    instr.write_text(content, encoding="utf-8")
    violations = run([_make_file(instr, content)], Config(), tmp_path)
    assert any(v.check_id == "AL-INV01" for v in violations)


# ---------------------------------------------------------------------------
# Violation: "`X` is not implemented" — path exists
# ---------------------------------------------------------------------------


def test_violation_neg_after_is_not_implemented(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "audit_log.py").write_text("", encoding="utf-8")
    instr = tmp_path / "SKILL.md"
    content = "`app/audit_log.py` is not implemented in this project.\n"
    instr.write_text(content, encoding="utf-8")
    violations = run([_make_file(instr, content)], Config(), tmp_path)
    assert any(v.check_id == "AL-INV01" for v in violations)


# ---------------------------------------------------------------------------
# Violation: "`X` is not supported" — path exists
# ---------------------------------------------------------------------------


def test_violation_neg_after_is_not_supported(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "alerting.py").write_text("", encoding="utf-8")
    instr = tmp_path / "SKILL.md"
    content = "`src/alerting.py` is not supported.\n"
    instr.write_text(content, encoding="utf-8")
    violations = run([_make_file(instr, content)], Config(), tmp_path)
    assert any(v.check_id == "AL-INV01" for v in violations)


# ---------------------------------------------------------------------------
# Violation: "doesn't include `X`" — contraction variant
# ---------------------------------------------------------------------------


def test_violation_contraction_doesnt(tmp_path: Path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "logger.py").write_text("", encoding="utf-8")
    instr = tmp_path / "SKILL.md"
    content = "This system doesn't include `lib/logger.py`.\n"
    instr.write_text(content, encoding="utf-8")
    violations = run([_make_file(instr, content)], Config(), tmp_path)
    assert any(v.check_id == "AL-INV01" for v in violations)


# ---------------------------------------------------------------------------
# No violation: ignored path
# ---------------------------------------------------------------------------


def test_ignore_paths_suppresses(tmp_path: Path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "alerter.py").write_text("", encoding="utf-8")
    archive = tmp_path / "archive"
    archive.mkdir()
    instr = archive / "LIMITATIONS.md"
    content = "There is no `agents/alerter.py`.\n"
    instr.write_text(content, encoding="utf-8")
    config = Config()
    config.ignore_paths = ["archive/"]
    violations = run([_make_file(instr, content)], config, tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Correct line number reported
# ---------------------------------------------------------------------------


def test_correct_line_number(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.py").write_text("", encoding="utf-8")
    instr = tmp_path / "SKILL.md"
    content = "Line one.\nLine two.\nThis does not include `src/auth.py`.\n"
    instr.write_text(content, encoding="utf-8")
    violations = run([_make_file(instr, content)], Config(), tmp_path)
    assert violations[0].line == 3


# ---------------------------------------------------------------------------
# Multiple refs on one line — only fires for paths that exist on disk
# ---------------------------------------------------------------------------


def test_multiple_refs_only_existing_fires(tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "real.py").write_text("", encoding="utf-8")
    # app/ghost.py does NOT exist
    instr = tmp_path / "SKILL.md"
    content = "There is no `app/real.py` or `app/ghost.py`.\n"
    instr.write_text(content, encoding="utf-8")
    violations = run([_make_file(instr, content)], Config(), tmp_path)
    assert len(violations) == 1
    assert "app/real.py" in violations[0].message


# ---------------------------------------------------------------------------
# DISPATCH and DOCS roles are also checked
# ---------------------------------------------------------------------------


def test_dispatch_role_checked(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "missing_module.py").write_text("", encoding="utf-8")
    instr = tmp_path / "CLAUDE.md"
    content = "No `src/missing_module.py` exists in this project.\n"
    instr.write_text(content, encoding="utf-8")
    violations = run(
        [_make_file(instr, content, role=Role.DISPATCH)], Config(), tmp_path
    )
    assert any(v.check_id == "AL-INV01" for v in violations)


# ---------------------------------------------------------------------------
# No violation — negation refers to a tool/feature, not to the backtick path
# (real-world pattern from microsoft/vscode copilot-instructions.md)
# ---------------------------------------------------------------------------


def test_clean_negation_refers_to_tool_not_path(tmp_path: Path):
    """'not available' describes a Copilot tool; path comes after the negation."""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "test.sh").write_text("", encoding="utf-8")
    instr = tmp_path / "SKILL.md"
    content = "If the tool is not available, you can use `scripts/test.sh` instead.\n"
    instr.write_text(content, encoding="utf-8")
    violations = run([_make_file(instr, content)], Config(), tmp_path)
    assert violations == []


def test_clean_conditional_availability_with_path_after(tmp_path: Path):
    """Negation clause precedes path clause separated by 'and'."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "tsconfig.json").write_text("", encoding="utf-8")
    instr = tmp_path / "SKILL.md"
    content = (
        "If the tool is not available and you changed code under `src/`, "
        "run compile-check-ts-native which validates `src/tsconfig.json`.\n"
    )
    instr.write_text(content, encoding="utf-8")
    violations = run([_make_file(instr, content)], Config(), tmp_path)
    assert violations == []
