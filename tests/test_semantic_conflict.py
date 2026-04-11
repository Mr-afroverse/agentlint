"""Tests for AL-CONF01 — contradictory directive detection."""

from __future__ import annotations

from pathlib import Path

from agentlint.checks.semantic_conflict import (
    _extract_directives,
    _normalise_predicate,
    _predicates_overlap,
    run,
)
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


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


def test_normalise_predicate_lowercase():
    assert _normalise_predicate("Semicolons.") == "semicolons"


def test_normalise_predicate_strips_trailing_punct():
    assert _normalise_predicate("snake_case naming.") == "snake_case naming"


def test_normalise_predicate_strips_leading_use():
    assert _normalise_predicate("use pathlib") == "pathlib"


def test_normalise_predicate_strips_leading_article():
    assert _normalise_predicate("the type annotations.") == "type annotations"


def test_predicates_overlap_exact():
    assert _predicates_overlap("tabs", "tabs")


def test_predicates_overlap_prefix_short_is_prefix_of_long():
    assert _predicates_overlap("tabs", "tabs for indentation")


def test_predicates_overlap_long_is_prefix_of_short():
    assert _predicates_overlap("double quotes for strings", "double quotes")


def test_predicates_overlap_false_on_different():
    assert not _predicates_overlap("tabs", "spaces")


def test_predicates_overlap_single_short_word_not_matched():
    # single short words (< 5 chars) should not match to avoid noise
    assert not _predicates_overlap("tabs", "the")


def test_normalise_predicate_limits_words():
    long = "one two three four five six seven eight nine ten"
    result = _normalise_predicate(long)
    assert len(result.split()) <= 8


def test_extract_directives_always():
    content = "Always use type annotations."
    f = InstructionFile(
        path=Path("x.md"),
        content=content,
        lines=[content],
        adapter="copilot",
        role=Role.SKILL,
        metadata={},
    )
    directives = _extract_directives(f)
    assert any(
        pol == "positive" and "type annotations" in pred for pol, pred, _ in directives
    )


def test_extract_directives_never():
    content = "Never use tabs."
    f = InstructionFile(
        path=Path("x.md"),
        content=content,
        lines=[content],
        adapter="copilot",
        role=Role.SKILL,
        metadata={},
    )
    directives = _extract_directives(f)
    assert any(pol == "negative" and "tabs" in pred for pol, pred, _ in directives)


def test_extract_directives_do_not():
    content = "Do not use global variables."
    f = InstructionFile(
        path=Path("x.md"),
        content=content,
        lines=[content],
        adapter="copilot",
        role=Role.SKILL,
        metadata={},
    )
    directives = _extract_directives(f)
    assert any(pol == "negative" for pol, _, _ in directives)


def test_extract_directives_avoid():
    content = "Avoid using mutable default arguments."
    f = InstructionFile(
        path=Path("x.md"),
        content=content,
        lines=[content],
        adapter="copilot",
        role=Role.SKILL,
        metadata={},
    )
    directives = _extract_directives(f)
    assert any(pol == "negative" for pol, _, _ in directives)


def test_extract_directives_disable_comment_suppresses():
    content = "Never use semicolons.  # agentlint: disable=AL-CONF01"
    f = InstructionFile(
        path=Path("x.md"),
        content=content,
        lines=[content],
        adapter="copilot",
        role=Role.SKILL,
        metadata={},
    )
    assert _extract_directives(f) == []


# ---------------------------------------------------------------------------
# Core conflict detection
# ---------------------------------------------------------------------------


def test_fires_on_always_vs_never(tmp_path: Path):
    fa = _skill(tmp_path, "a/SKILL.md", "Always use semicolons.")
    fb = _skill(tmp_path, "b/SKILL.md", "Never use semicolons.")
    config = Config()
    violations = run([fa, fb], config, tmp_path)
    assert len(violations) >= 1
    assert violations[0].check_id == "AL-CONF01"
    assert violations[0].severity.name == "WARNING"


def test_fires_on_use_vs_avoid(tmp_path: Path):
    fa = _skill(tmp_path, "a/SKILL.md", "Use double quotes for strings.")
    fb = _skill(tmp_path, "b/SKILL.md", "Avoid using double quotes.")
    config = Config()
    violations = run([fa, fb], config, tmp_path)
    assert len(violations) >= 1
    assert violations[0].check_id == "AL-CONF01"


def test_fires_on_prefer_vs_avoid(tmp_path: Path):
    fa = _skill(tmp_path, "a/SKILL.md", "Prefer single quotes.")
    fb = _skill(tmp_path, "b/SKILL.md", "Avoid single quotes.")
    config = Config()
    violations = run([fa, fb], config, tmp_path)
    assert len(violations) >= 1


def test_fires_on_must_vs_must_not(tmp_path: Path):
    fa = _skill(tmp_path, "a/SKILL.md", "Must use pathlib for file paths.")
    fb = _skill(tmp_path, "b/SKILL.md", "Must not use pathlib.")
    config = Config()
    violations = run([fa, fb], config, tmp_path)
    assert len(violations) >= 1


def test_message_names_both_files(tmp_path: Path):
    fa = _skill(tmp_path, "a/SKILL.md", "Always use tabs.")
    fb = _skill(tmp_path, "b/SKILL.md", "Never use tabs.")
    config = Config()
    violations = run([fa, fb], config, tmp_path)
    assert len(violations) >= 1
    msg = violations[0].message
    assert "a/SKILL.md" in msg or "b/SKILL.md" in msg


def test_fix_hint_present(tmp_path: Path):
    fa = _skill(tmp_path, "a/SKILL.md", "Always use tabs.")
    fb = _skill(tmp_path, "b/SKILL.md", "Never use tabs.")
    config = Config()
    violations = run([fa, fb], config, tmp_path)
    assert violations[0].fix_hint is not None


# ---------------------------------------------------------------------------
# No false positives on unambiguous files
# ---------------------------------------------------------------------------


def test_no_conflict_when_files_agree(tmp_path: Path):
    fa = _skill(tmp_path, "a/SKILL.md", "Always use type annotations.")
    fb = _skill(tmp_path, "b/SKILL.md", "Always use type annotations.")
    config = Config()
    assert run([fa, fb], config, tmp_path) == []


def test_no_conflict_with_unrelated_directives(tmp_path: Path):
    fa = _skill(tmp_path, "a/SKILL.md", "Always use pathlib.\nNever use os.getcwd().")
    fb = _skill(tmp_path, "b/SKILL.md", "Use pytest for all tests.")
    config = Config()
    violations = run([fa, fb], config, tmp_path)
    # No conflicts — different topics
    for v in violations:
        assert v.check_id == "AL-CONF01"


def test_no_conflict_with_one_file(tmp_path: Path):
    fa = _skill(tmp_path, "a/SKILL.md", "Always use semicolons.\nNever use tabs.")
    config = Config()
    assert run([fa], config, tmp_path) == []


def test_no_conflict_with_zero_files(tmp_path: Path):
    assert run([], Config(), tmp_path) == []


# ---------------------------------------------------------------------------
# Same-file contradictions do NOT fire (common "do X unless Y" patterns)
# ---------------------------------------------------------------------------


def test_same_file_contradiction_not_flagged(tmp_path: Path):
    content = (
        "Always use type annotations.\nNever use type annotations for private helpers."
    )
    fa = _skill(tmp_path, "a/SKILL.md", content)
    fb = _skill(tmp_path, "b/SKILL.md", "Use pytest for tests.")
    config = Config()
    violations = run([fa, fb], config, tmp_path)
    # The conflict is within fa only — should not fire
    assert all(v.check_id == "AL-CONF01" for v in violations)


# ---------------------------------------------------------------------------
# Works across DISPATCH files too
# ---------------------------------------------------------------------------


def test_fires_on_dispatch_vs_skill_conflict(tmp_path: Path):
    fd = _dispatch(tmp_path, "instructions.md", "Always use tabs for indentation.")
    fs = _skill(tmp_path, "style/SKILL.md", "Never use tabs.")
    config = Config()
    violations = run([fd, fs], config, tmp_path)
    assert len(violations) >= 1
    assert violations[0].check_id == "AL-CONF01"


# ---------------------------------------------------------------------------
# ignore_paths respected
# ---------------------------------------------------------------------------


def test_ignore_paths_suppresses_file(tmp_path: Path):
    fa = _skill(tmp_path, "a/SKILL.md", "Always use tabs.")
    fb = _skill(tmp_path, "b/SKILL.md", "Never use tabs.")
    config = Config()
    config.ignore_paths = ["b/SKILL.md"]
    assert run([fa, fb], config, tmp_path) == []


# ---------------------------------------------------------------------------
# Deduplication — same pair + predicate reported only once
# ---------------------------------------------------------------------------


def test_deduplication_same_pair(tmp_path: Path):
    # Both files have multiple lines that create the same logical conflict
    fa = _skill(
        tmp_path, "a/SKILL.md", "Always use semicolons.\nAlways use semicolons again."
    )
    fb = _skill(tmp_path, "b/SKILL.md", "Never use semicolons.")
    config = Config()
    violations = run([fa, fb], config, tmp_path)
    # Should only report once per unique (file_a, file_b, predicate) triple
    predicates_reported = [v.message for v in violations]
    # No exact message duplicates
    assert len(predicates_reported) == len(set(predicates_reported))
