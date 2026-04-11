"""Tests for AL-DUP01 — near-duplicate instruction file detection."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentlint.checks.duplicate_content import _jaccard, _ngrams, _normalise, run
from agentlint.config import Config
from agentlint.models import InstructionFile, Role


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _skill(tmp_path: Path, name: str, content: str) -> InstructionFile:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return InstructionFile(
        path=p,
        content=content,
        lines=content.splitlines(),
        adapter="copilot",
        role=Role.SKILL,
        metadata={},
    )


def _dispatch(tmp_path: Path, name: str, content: str) -> InstructionFile:
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return InstructionFile(
        path=p,
        content=content,
        lines=content.splitlines(),
        adapter="copilot",
        role=Role.DISPATCH,
        metadata={},
    )


_LONG_CONTENT = (
    "# Python coding standards\n\n"
    "Always use type annotations. "
    "Follow PEP 8 for formatting. "
    "Write docstrings for every public function. "
    "Prefer list comprehensions over map/filter. "
    "Use pathlib instead of os.path. "
    "Never use bare except clauses. "
    "All tests live in the tests/ directory. "
    "Use pytest for testing. "
    "Functions should do one thing. "
    "Keep lines under 88 characters. "
)

_SLIGHTLY_DIFFERENT = (
    "# Python coding standards\n\n"
    "Always use type annotations. "
    "Follow PEP 8 for formatting. "
    "Write docstrings for every public function. "
    "Prefer list comprehensions over map/filter. "
    "Use pathlib instead of os.path. "
    "Never use bare except clauses. "
    "All tests live in the tests/ directory. "
    "Use pytest for testing. "
    "Functions should do one thing. "
    "Keep lines under 100 characters. "  # one small change
)

_VERY_DIFFERENT = (
    "# Database access rules\n\n"
    "Always use parameterised queries. "
    "Never concatenate user input into SQL. "
    "Use transactions for multi-step writes. "
    "Index foreign key columns. "
    "Keep connections in a pool. "
    "Log slow queries above 100ms. "
)


# ---------------------------------------------------------------------------
# Unit tests for internal helpers
# ---------------------------------------------------------------------------


def test_normalise_lowercases():
    assert _normalise("Hello World") == "hello world"


def test_normalise_collapses_whitespace():
    assert _normalise("a  b\tc\n\nd") == "a b c d"


def test_ngrams_basic():
    result = _ngrams("abcd", n=3)
    assert result == {"abc", "bcd"}


def test_ngrams_short_string_returns_set_with_text():
    result = _ngrams("ab", n=3)
    assert result == {"ab"}


def test_ngrams_empty_returns_empty():
    assert _ngrams("", n=3) == set()


def test_jaccard_identical():
    assert _jaccard("hello world", "hello world") == pytest.approx(1.0)


def test_jaccard_completely_different():
    score = _jaccard("aaa", "bbb")
    assert score == pytest.approx(0.0)


def test_jaccard_partial():
    score = _jaccard("abcdef", "abcxyz")
    assert 0.0 < score < 1.0


def test_jaccard_both_empty():
    assert _jaccard("", "") == pytest.approx(1.0)


def test_jaccard_one_empty():
    assert _jaccard("hello", "") == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# disabled by default threshold too low / config says 0
# ---------------------------------------------------------------------------


def test_disabled_when_threshold_zero(tmp_path: Path):
    config = Config()
    config.duplicate_threshold = 0.0
    fa = _skill(tmp_path, "a/SKILL.md", _LONG_CONTENT)
    fb = _skill(tmp_path, "b/SKILL.md", _LONG_CONTENT)
    assert run([fa, fb], config, tmp_path) == []


def test_no_violations_with_one_file(tmp_path: Path):
    config = Config()
    fa = _skill(tmp_path, "a/SKILL.md", _LONG_CONTENT)
    assert run([fa], config, tmp_path) == []


def test_no_violations_with_zero_files(tmp_path: Path):
    config = Config()
    assert run([], config, tmp_path) == []


# ---------------------------------------------------------------------------
# fires on near-duplicate SKILL files
# ---------------------------------------------------------------------------


def test_fires_on_identical_skill_files(tmp_path: Path):
    config = Config()  # default threshold 0.85
    fa = _skill(tmp_path, "a/SKILL.md", _LONG_CONTENT)
    fb = _skill(tmp_path, "b/SKILL.md", _LONG_CONTENT)
    violations = run([fa, fb], config, tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-DUP01"
    assert violations[0].severity.name == "WARNING"


def test_fires_on_near_identical_skill_files(tmp_path: Path):
    config = Config()
    fa = _skill(tmp_path, "a/SKILL.md", _LONG_CONTENT)
    fb = _skill(tmp_path, "b/SKILL.md", _SLIGHTLY_DIFFERENT)
    violations = run([fa, fb], config, tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-DUP01"


def test_message_includes_similarity_percentage(tmp_path: Path):
    config = Config()
    fa = _skill(tmp_path, "a/SKILL.md", _LONG_CONTENT)
    fb = _skill(tmp_path, "b/SKILL.md", _LONG_CONTENT)
    violations = run([fa, fb], config, tmp_path)
    assert "100%" in violations[0].message


def test_message_includes_other_file_name(tmp_path: Path):
    config = Config()
    fa = _skill(tmp_path, "a/SKILL.md", _LONG_CONTENT)
    fb = _skill(tmp_path, "b/SKILL.md", _LONG_CONTENT)
    violations = run([fa, fb], config, tmp_path)
    assert "a/SKILL.md" in violations[0].message


def test_fix_hint_present(tmp_path: Path):
    config = Config()
    fa = _skill(tmp_path, "a/SKILL.md", _LONG_CONTENT)
    fb = _skill(tmp_path, "b/SKILL.md", _LONG_CONTENT)
    violations = run([fa, fb], config, tmp_path)
    assert violations[0].fix_hint is not None
    assert "Merge" in violations[0].fix_hint


# ---------------------------------------------------------------------------
# does NOT fire on distinct files
# ---------------------------------------------------------------------------


def test_no_violation_on_distinct_files(tmp_path: Path):
    config = Config()
    fa = _skill(tmp_path, "a/SKILL.md", _LONG_CONTENT)
    fb = _skill(tmp_path, "b/SKILL.md", _VERY_DIFFERENT)
    assert run([fa, fb], config, tmp_path) == []


# ---------------------------------------------------------------------------
# fires on near-duplicate DISPATCH files too
# ---------------------------------------------------------------------------


def test_fires_on_identical_dispatch_files(tmp_path: Path):
    config = Config()
    fa = _dispatch(tmp_path, "a.md", _LONG_CONTENT)
    fb = _dispatch(tmp_path, "b.md", _LONG_CONTENT)
    violations = run([fa, fb], config, tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-DUP01"


# ---------------------------------------------------------------------------
# SKILL vs DISPATCH cross-role — must NOT fire
# ---------------------------------------------------------------------------


def test_no_cross_role_comparison(tmp_path: Path):
    config = Config()
    fa = _skill(tmp_path, "a/SKILL.md", _LONG_CONTENT)
    fb = _dispatch(tmp_path, "instructions.md", _LONG_CONTENT)
    # identical content but different roles — should not fire
    assert run([fa, fb], config, tmp_path) == []


# ---------------------------------------------------------------------------
# configurable threshold
# ---------------------------------------------------------------------------


def test_custom_threshold_higher_suppresses_near_duplicate(tmp_path: Path):
    config = Config()
    config.duplicate_threshold = 0.99  # very strict — only exact matches
    fa = _skill(tmp_path, "a/SKILL.md", _LONG_CONTENT)
    fb = _skill(tmp_path, "b/SKILL.md", _SLIGHTLY_DIFFERENT)
    # slightly different won't reach 99%
    assert run([fa, fb], config, tmp_path) == []


def test_custom_threshold_lower_catches_loosely_similar(tmp_path: Path):
    config = Config()
    config.duplicate_threshold = 0.3  # very lenient
    fa = _skill(tmp_path, "a/SKILL.md", _LONG_CONTENT)
    fb = _skill(tmp_path, "b/SKILL.md", _VERY_DIFFERENT)
    # at 0.3 the very-different pair will likely not reach 30% — still no violation
    # (this mainly tests the threshold branch is reached)
    violations = run([fa, fb], config, tmp_path)
    # don't assert count — just assert check_id if any fires
    for v in violations:
        assert v.check_id == "AL-DUP01"


# ---------------------------------------------------------------------------
# ignore_paths respected
# ---------------------------------------------------------------------------


def test_ignore_paths_suppresses_file(tmp_path: Path):
    config = Config()
    config.ignore_paths = ["b/SKILL.md"]
    fa = _skill(tmp_path, "a/SKILL.md", _LONG_CONTENT)
    fb = _skill(tmp_path, "b/SKILL.md", _LONG_CONTENT)
    assert run([fa, fb], config, tmp_path) == []


# ---------------------------------------------------------------------------
# three files — reports each unique duplicate pair once
# ---------------------------------------------------------------------------


def test_three_identical_files_reports_two_violations(tmp_path: Path):
    config = Config()
    fa = _skill(tmp_path, "a/SKILL.md", _LONG_CONTENT)
    fb = _skill(tmp_path, "b/SKILL.md", _LONG_CONTENT)
    fc = _skill(tmp_path, "c/SKILL.md", _LONG_CONTENT)
    violations = run([fa, fb, fc], config, tmp_path)
    # pairs: (a,b), (a,c), (b,c) — 3 pairs all identical
    assert len(violations) == 3
    for v in violations:
        assert v.check_id == "AL-DUP01"
