from __future__ import annotations

from pathlib import Path

from agentlint.checks.token_budget import _estimate_tokens, run
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
# _estimate_tokens helper
# ---------------------------------------------------------------------------


def test_estimate_tokens_basic():
    # 400 chars → 100 tokens
    assert _estimate_tokens("a" * 400) == 100


def test_estimate_tokens_minimum_one():
    assert _estimate_tokens("") == 1


# ---------------------------------------------------------------------------
# token_budget = 0 (default) → no violations
# ---------------------------------------------------------------------------


def test_disabled_by_default(tmp_path: Path):
    big_content = "x " * 10_000  # way over any budget
    f = _make_file(tmp_path / "SKILL.md", big_content)
    config = Config()
    assert config.token_budget == 0
    assert run([f], config, tmp_path) == []


# ---------------------------------------------------------------------------
# Under budget → no violation
# ---------------------------------------------------------------------------


def test_under_budget_no_violation(tmp_path: Path):
    content = "Short instruction.\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    config = Config()
    config.token_budget = 2000
    assert run([f], config, tmp_path) == []


# ---------------------------------------------------------------------------
# Over budget → violation
# ---------------------------------------------------------------------------


def test_over_budget_violation(tmp_path: Path):
    # 4000 chars → ~1000 tokens; budget 500
    content = "word " * 800  # ~4000 chars
    f = _make_file(tmp_path / "SKILL.md", content)
    config = Config()
    config.token_budget = 500
    violations = run([f], config, tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-TOK01"
    assert violations[0].severity == Severity.WARNING
    assert violations[0].line is None


# ---------------------------------------------------------------------------
# Violation message includes estimated count and budget
# ---------------------------------------------------------------------------


def test_violation_message_contains_numbers(tmp_path: Path):
    content = "a" * 4000  # 1000 tokens
    f = _make_file(tmp_path / "SKILL.md", content)
    config = Config()
    config.token_budget = 500
    violations = run([f], config, tmp_path)
    assert "1000" in violations[0].message
    assert "500" in violations[0].message


# ---------------------------------------------------------------------------
# DOCS role is not checked
# ---------------------------------------------------------------------------


def test_docs_role_not_checked(tmp_path: Path):
    content = "a" * 8000
    f = _make_file(tmp_path / "docs.md", content, role=Role.DOCS)
    config = Config()
    config.token_budget = 100
    assert run([f], config, tmp_path) == []


# ---------------------------------------------------------------------------
# DISPATCH role is checked
# ---------------------------------------------------------------------------


def test_dispatch_role_checked(tmp_path: Path):
    content = "a" * 4000
    f = _make_file(tmp_path / "CLAUDE.md", content, role=Role.DISPATCH)
    config = Config()
    config.token_budget = 500
    violations = run([f], config, tmp_path)
    assert any(v.check_id == "AL-TOK01" for v in violations)


# ---------------------------------------------------------------------------
# ignore_paths suppresses
# ---------------------------------------------------------------------------


def test_ignore_paths_suppresses(tmp_path: Path):
    archive = tmp_path / "archive"
    archive.mkdir()
    instr = archive / "SKILL.md"
    content = "a" * 8000
    f = _make_file(instr, content)
    config = Config()
    config.token_budget = 100
    config.ignore_paths = ["archive/"]
    assert run([f], config, tmp_path) == []


# ---------------------------------------------------------------------------
# Config loads token_budget from YAML
# ---------------------------------------------------------------------------


def test_config_loads_token_budget(tmp_path: Path):
    (tmp_path / ".agentlint.yml").write_text("token_budget: 1500\n", encoding="utf-8")
    from agentlint.config import Config as Cfg

    cfg = Cfg.load(tmp_path)
    assert cfg.token_budget == 1500
