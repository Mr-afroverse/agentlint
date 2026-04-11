"""
Unit tests for agentlint.fixer.apply_fixes().

Covers:
  - No fixable violations → returns empty applied list
  - Single fix applied and file updated correctly
  - Stale old_line → fix skipped
  - Multiple fixes in one file (different lines)
  - Two violations targeting same line → first wins, second skipped
  - Violation line number out of range → skipped
  - Multiple files → all applied
  - CRLF line endings preserved
  - Non-fixable violations not included in applied list
  - Returns correct skipped count
"""

from __future__ import annotations

from pathlib import Path

from agentlint.fixer import apply_fixes
from agentlint.models import Severity, Violation


def _make_violation(
    file: Path,
    line: int,
    old_line: str,
    new_line: str,
    auto_fixable: bool = True,
) -> Violation:
    return Violation(
        check_id="AL-DEP01",
        severity=Severity.WARNING,
        file=file,
        line=line,
        message="Deprecated pattern.",
        fix_hint="Replace it.",
        auto_fixable=auto_fixable,
        fix_data={"old_line": old_line, "new_line": new_line} if auto_fixable else {},
    )


# ---------------------------------------------------------------------------
# No fixable violations
# ---------------------------------------------------------------------------


def test_no_violations_returns_empty(tmp_path: Path):
    applied, skipped = apply_fixes([], tmp_path)
    assert applied == []
    assert skipped == 0


def test_non_fixable_violation_not_applied(tmp_path: Path):
    f = tmp_path / "SKILL.md"
    f.write_text("Use gpt-4-0613 here.\n", encoding="utf-8")
    v = _make_violation(
        f, 1, "Use gpt-4-0613 here.", "Use gpt-4o here.", auto_fixable=False
    )
    v.fix_data = {}
    applied, skipped = apply_fixes([v], tmp_path)
    assert applied == []
    assert skipped == 0
    assert f.read_text(encoding="utf-8") == "Use gpt-4-0613 here.\n"


# ---------------------------------------------------------------------------
# Single fix
# ---------------------------------------------------------------------------


def test_single_fix_writes_new_line(tmp_path: Path):
    f = tmp_path / "SKILL.md"
    f.write_text("Use gpt-4-0613 here.\n", encoding="utf-8")
    v = _make_violation(f, 1, "Use gpt-4-0613 here.", "Use gpt-4o here.")
    applied, skipped = apply_fixes([v], tmp_path)
    assert len(applied) == 1
    assert skipped == 0
    assert f.read_text(encoding="utf-8") == "Use gpt-4o here.\n"


def test_single_fix_returns_violation_in_applied(tmp_path: Path):
    f = tmp_path / "SKILL.md"
    f.write_text("Model: gpt-4-0613\n", encoding="utf-8")
    v = _make_violation(f, 1, "Model: gpt-4-0613", "Model: gpt-4o")
    applied, _ = apply_fixes([v], tmp_path)
    assert applied[0] is v


# ---------------------------------------------------------------------------
# Stale line (old_line no longer matches disk)
# ---------------------------------------------------------------------------


def test_stale_old_line_is_skipped(tmp_path: Path):
    f = tmp_path / "SKILL.md"
    # Write a different line than what fix_data expects
    f.write_text("Model: gpt-4o\n", encoding="utf-8")
    v = _make_violation(f, 1, "Model: gpt-4-0613", "Model: gpt-4o")
    applied, skipped = apply_fixes([v], tmp_path)
    assert applied == []
    assert skipped == 1
    # File unchanged
    assert f.read_text(encoding="utf-8") == "Model: gpt-4o\n"


# ---------------------------------------------------------------------------
# Line number edge cases
# ---------------------------------------------------------------------------


def test_line_number_out_of_range_skipped(tmp_path: Path):
    f = tmp_path / "SKILL.md"
    f.write_text("Line one.\n", encoding="utf-8")
    v = _make_violation(f, 99, "Line one.", "Fixed.")
    applied, skipped = apply_fixes([v], tmp_path)
    assert applied == []
    assert skipped == 1


# ---------------------------------------------------------------------------
# Multiple fixes in one file
# ---------------------------------------------------------------------------


def test_multiple_fixes_different_lines(tmp_path: Path):
    content = "Model: gpt-4-0613\nAlso use gpt-4-0613.\n"
    f = tmp_path / "SKILL.md"
    f.write_text(content, encoding="utf-8")
    v1 = _make_violation(f, 1, "Model: gpt-4-0613", "Model: gpt-4o")
    v2 = _make_violation(f, 2, "Also use gpt-4-0613.", "Also use gpt-4o.")
    applied, skipped = apply_fixes([v1, v2], tmp_path)
    assert len(applied) == 2
    assert skipped == 0
    assert f.read_text(encoding="utf-8") == "Model: gpt-4o\nAlso use gpt-4o.\n"


def test_duplicate_line_number_second_skipped(tmp_path: Path):
    f = tmp_path / "SKILL.md"
    f.write_text("gpt-4-0613 model\n", encoding="utf-8")
    v1 = _make_violation(f, 1, "gpt-4-0613 model", "gpt-4o model")
    v2 = _make_violation(f, 1, "gpt-4-0613 model", "gpt-4-turbo model")
    applied, skipped = apply_fixes([v1, v2], tmp_path)
    assert len(applied) == 1
    assert skipped == 1
    # First fix wins
    assert f.read_text(encoding="utf-8") == "gpt-4o model\n"


# ---------------------------------------------------------------------------
# Multiple files
# ---------------------------------------------------------------------------


def test_multiple_files_all_applied(tmp_path: Path):
    f1 = tmp_path / "SKILL1.md"
    f2 = tmp_path / "SKILL2.md"
    f1.write_text("old text\n", encoding="utf-8")
    f2.write_text("old text\n", encoding="utf-8")
    v1 = _make_violation(f1, 1, "old text", "new text")
    v2 = _make_violation(f2, 1, "old text", "new text")
    applied, skipped = apply_fixes([v1, v2], tmp_path)
    assert len(applied) == 2
    assert skipped == 0
    assert f1.read_text(encoding="utf-8") == "new text\n"
    assert f2.read_text(encoding="utf-8") == "new text\n"


# ---------------------------------------------------------------------------
# Line ending preservation
# ---------------------------------------------------------------------------


def test_crlf_line_endings_preserved(tmp_path: Path):
    f = tmp_path / "SKILL.md"
    f.write_bytes(b"gpt-4-0613 model\r\nSecond line.\r\n")
    v = _make_violation(f, 1, "gpt-4-0613 model", "gpt-4o model")
    applied, skipped = apply_fixes([v], tmp_path)
    assert len(applied) == 1
    # CRLF on the fixed line must be preserved
    assert f.read_bytes() == b"gpt-4o model\r\nSecond line.\r\n"


# ---------------------------------------------------------------------------
# Mixed fixable / non-fixable in same call
# ---------------------------------------------------------------------------


def test_only_fixable_applied_nonfixable_ignored(tmp_path: Path):
    f = tmp_path / "SKILL.md"
    f.write_text("old line\n", encoding="utf-8")
    fixable = _make_violation(f, 1, "old line", "new line")
    non_fixable = Violation(
        check_id="AL-N01",
        severity=Severity.WARNING,
        file=f,
        line=1,
        message="Some warning.",
        fix_hint="Manual fix needed.",
        auto_fixable=False,
    )
    applied, skipped = apply_fixes([fixable, non_fixable], tmp_path)
    # Only the fixable violation is applied; non-fixable is ignored (not skipped)
    assert len(applied) == 1
    assert applied[0] is fixable
