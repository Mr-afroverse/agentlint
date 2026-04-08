from __future__ import annotations

from pathlib import Path

from agentlint.checks.vague_instructions import run
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
# Clean lines — no vague patterns
# ---------------------------------------------------------------------------


def test_clean_specific_instruction(tmp_path: Path):
    content = "Run `pytest -x` and ensure all tests pass before committing.\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    assert run([f], Config(), tmp_path) == []


def test_clean_empty_file(tmp_path: Path):
    f = _make_file(tmp_path / "SKILL.md", "")
    assert run([f], Config(), tmp_path) == []


# ---------------------------------------------------------------------------
# Positive detections
# ---------------------------------------------------------------------------


def test_q01_write_clean_code(tmp_path: Path):
    f = _make_file(tmp_path / "SKILL.md", "Always write clean code.\n")
    violations = run([f], Config(), tmp_path)
    assert any(v.check_id == "AL-Q01" for v in violations)


def test_q01_follow_best_practices(tmp_path: Path):
    f = _make_file(tmp_path / "SKILL.md", "Follow best practices at all times.\n")
    violations = run([f], Config(), tmp_path)
    assert any(v.check_id == "AL-Q01" for v in violations)


def test_q01_be_helpful(tmp_path: Path):
    f = _make_file(tmp_path / "SKILL.md", "Always be helpful to the user.\n")
    violations = run([f], Config(), tmp_path)
    assert any(v.check_id == "AL-Q01" for v in violations)


def test_q01_use_best_practices(tmp_path: Path):
    f = _make_file(tmp_path / "SKILL.md", "Use best practices when writing tests.\n")
    violations = run([f], Config(), tmp_path)
    assert any(v.check_id == "AL-Q01" for v in violations)


def test_q01_make_sure_it_works(tmp_path: Path):
    f = _make_file(tmp_path / "SKILL.md", "Make sure it works before submitting.\n")
    violations = run([f], Config(), tmp_path)
    assert any(v.check_id == "AL-Q01" for v in violations)


def test_q01_as_needed(tmp_path: Path):
    f = _make_file(tmp_path / "SKILL.md", "Update the config as needed.\n")
    violations = run([f], Config(), tmp_path)
    assert any(v.check_id == "AL-Q01" for v in violations)


def test_q01_use_common_sense(tmp_path: Path):
    f = _make_file(tmp_path / "SKILL.md", "Use common sense when in doubt.\n")
    violations = run([f], Config(), tmp_path)
    assert any(v.check_id == "AL-Q01" for v in violations)


# ---------------------------------------------------------------------------
# Severity is warning
# ---------------------------------------------------------------------------


def test_q01_severity_is_warning(tmp_path: Path):
    f = _make_file(tmp_path / "SKILL.md", "Be professional.\n")
    violations = run([f], Config(), tmp_path)
    q01 = [v for v in violations if v.check_id == "AL-Q01"]
    assert q01
    assert all(v.severity == Severity.WARNING for v in q01)


# ---------------------------------------------------------------------------
# Only one violation per line (first match wins)
# ---------------------------------------------------------------------------


def test_q01_only_one_per_line(tmp_path: Path):
    # Line contains both "best practices" and "be helpful" — only one violation
    f = _make_file(tmp_path / "SKILL.md", "Follow best practices and be helpful.\n")
    violations = run([f], Config(), tmp_path)
    assert len([v for v in violations if v.check_id == "AL-Q01"]) == 1


# ---------------------------------------------------------------------------
# Code fence lines skipped
# ---------------------------------------------------------------------------


def test_q01_code_fence_skipped(tmp_path: Path):
    content = "```\nAlways be helpful — this is an example.\n```\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    assert run([f], Config(), tmp_path) == []


# ---------------------------------------------------------------------------
# Inline disable comment suppresses
# ---------------------------------------------------------------------------


def test_q01_inline_disable(tmp_path: Path):
    content = "Follow best practices  # agentlint: disable=AL-Q01\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    assert run([f], Config(), tmp_path) == []


# ---------------------------------------------------------------------------
# ignore_paths suppresses file
# ---------------------------------------------------------------------------


def test_q01_ignore_paths(tmp_path: Path):
    archive = tmp_path / "archive"
    archive.mkdir()
    instr = archive / "SKILL.md"
    content = "Be helpful.\n"
    f = _make_file(instr, content)
    config = Config()
    config.ignore_paths = ["archive/"]
    assert run([f], config, tmp_path) == []


# ---------------------------------------------------------------------------
# DOCS role is not checked
# ---------------------------------------------------------------------------


def test_q01_docs_role_not_checked(tmp_path: Path):
    f = _make_file(tmp_path / "docs.md", "Be helpful.\n", role=Role.DOCS)
    assert run([f], Config(), tmp_path) == []


# ---------------------------------------------------------------------------
# DISPATCH role is checked
# ---------------------------------------------------------------------------


def test_q01_dispatch_role_checked(tmp_path: Path):
    f = _make_file(tmp_path / "CLAUDE.md", "Write clean code.\n", role=Role.DISPATCH)
    violations = run([f], Config(), tmp_path)
    assert any(v.check_id == "AL-Q01" for v in violations)


# ---------------------------------------------------------------------------
# Correct line number reported
# ---------------------------------------------------------------------------


def test_q01_correct_line_number(tmp_path: Path):
    content = "Line one: specific instruction.\nLine two: write clean code.\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    violations = run([f], Config(), tmp_path)
    q01 = [v for v in violations if v.check_id == "AL-Q01"]
    assert q01[0].line == 2


# ---------------------------------------------------------------------------
# AL-Q01 false-positive guard: 'be concise' with qualifier on same line
# ---------------------------------------------------------------------------


def test_q01_be_concise_but_descriptive_no_fire(tmp_path: Path):
    # 'be concise but descriptive' has a same-line qualifier — should not fire
    content = (
        "Title should be concise but descriptive (see existing entries for examples).\n"
    )
    f = _make_file(tmp_path / "SKILL.md", content)
    assert run([f], Config(), tmp_path) == []


def test_q01_be_concise_comma_list_no_fire(tmp_path: Path):
    # 'be concise, keyword-rich' is qualified by additional criteria — should not fire
    content = "The description should be concise, keyword-rich, and explain what users will learn.\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    assert run([f], Config(), tmp_path) == []


def test_q01_be_concise_standalone_still_fires(tmp_path: Path):
    # bare 'Be concise.' with no qualifier should still fire
    content = "Be concise.\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    assert any(v.check_id == "AL-Q01" for v in run([f], Config(), tmp_path))
