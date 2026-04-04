"""
Tests for agentlint/report.py — format_text(), format_json(), format_badge(), and grade().

Builds LintResult / Violation objects directly (no filesystem, no adapters).
Covers:
  - format_text(): PASS output, fail output, grouping by file, fix hint, grade strings
  - format_json(): valid JSON, top-level keys, clean-run values, per-violation fields
  - format_badge(): valid SVG, correct grade embedded, colour differs by grade
  - LintResult.grade(): boundary cases A through F
  - _rel() resilience: path outside repo root does not raise
"""

from __future__ import annotations

import json
from pathlib import Path

from agentlint.models import LintResult, Severity, Violation
from agentlint.report import format_json, format_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _result(
    root: Path,
    violations: list[Violation] | None = None,
    files_scanned: int = 5,
    adapter: str = "copilot",
) -> LintResult:
    return LintResult(
        root=root,
        files_scanned=files_scanned,
        violations=violations or [],
        adapter=adapter,
    )


def _error(root: Path, *, filename: str = "skills/a.md", line: int = 1) -> Violation:
    return Violation(
        check_id="AL-D01",
        severity=Severity.ERROR,
        file=root / filename,
        line=line,
        message="Skill path not found on disk: `ghost/SKILL.md`",
        fix_hint="Create the file or correct the path.",
    )


def _warning(root: Path, *, filename: str = "skills/b.md", line: int = 5) -> Violation:
    return Violation(
        check_id="AL-N01",
        severity=Severity.WARNING,
        file=root / filename,
        line=line,
        message="Threshold number without source pointer: `≥ 90%`",
        fix_hint="Add a source pointer.",
    )


# ---------------------------------------------------------------------------
# format_text — pass branch
# ---------------------------------------------------------------------------


def test_format_text_pass_contains_pass_label(tmp_path: Path):
    text = format_text(_result(tmp_path), tmp_path)
    assert "PASS" in text


def test_format_text_pass_shows_grade_a(tmp_path: Path):
    text = format_text(_result(tmp_path), tmp_path)
    assert "Grade: A" in text


def test_format_text_pass_shows_file_count(tmp_path: Path):
    text = format_text(_result(tmp_path, files_scanned=7), tmp_path)
    assert "7" in text


# ---------------------------------------------------------------------------
# format_text — fail branch
# ---------------------------------------------------------------------------


def test_format_text_fail_shows_error_and_warning_counts(tmp_path: Path):
    violations = [_error(tmp_path), _warning(tmp_path)]
    text = format_text(_result(tmp_path, violations=violations), tmp_path)
    assert "1 error" in text
    assert "1 warning" in text


def test_format_text_fail_shows_check_ids(tmp_path: Path):
    violations = [_error(tmp_path), _warning(tmp_path)]
    text = format_text(_result(tmp_path, violations=violations), tmp_path)
    assert "AL-D01" in text
    assert "AL-N01" in text


def test_format_text_fail_shows_fix_hint(tmp_path: Path):
    text = format_text(_result(tmp_path, violations=[_error(tmp_path)]), tmp_path)
    assert "Create the file or correct the path" in text


def test_format_text_groups_multiple_violations_by_file(tmp_path: Path):
    """Two violations on the same file appear under a single file header."""
    shared_file = "skills/shared.md"
    v1 = _error(tmp_path, filename=shared_file, line=1)
    v2 = _warning(tmp_path, filename=shared_file, line=10)
    text = format_text(_result(tmp_path, violations=[v1, v2]), tmp_path)

    # Both check IDs appear
    assert "AL-D01" in text
    assert "AL-N01" in text
    # File path appears exactly once as the section header
    assert text.count("skills/shared.md") == 1


def test_format_text_shows_line_numbers(tmp_path: Path):
    v = _error(tmp_path, line=42)
    text = format_text(_result(tmp_path, violations=[v]), tmp_path)
    assert ":42" in text


def test_format_text_grade_b_one_error_one_file(tmp_path: Path):
    """1 error / 1 file → score = 80 → Grade B."""
    text = format_text(
        _result(tmp_path, violations=[_error(tmp_path)], files_scanned=1), tmp_path
    )
    assert "Grade: B" in text


def test_format_text_grade_f_many_errors_one_file(tmp_path: Path):
    """3 errors / 1 file → score = 40 → Grade F."""
    errors = [_error(tmp_path, line=i) for i in range(1, 4)]
    text = format_text(_result(tmp_path, violations=errors, files_scanned=1), tmp_path)
    assert "Grade: F" in text


# ---------------------------------------------------------------------------
# format_json
# ---------------------------------------------------------------------------


def test_format_json_is_valid_json(tmp_path: Path):
    output = format_json(_result(tmp_path), tmp_path)
    data = json.loads(output)  # raises json.JSONDecodeError if invalid
    assert isinstance(data, dict)


def test_format_json_top_level_keys_present(tmp_path: Path):
    data = json.loads(format_json(_result(tmp_path), tmp_path))
    for key in (
        "grade",
        "adapter",
        "files_scanned",
        "errors",
        "warnings",
        "violations",
    ):
        assert key in data, f"JSON output missing key: {key!r}"


def test_format_json_clean_run_values(tmp_path: Path):
    data = json.loads(format_json(_result(tmp_path), tmp_path))
    assert data["grade"] == "A"
    assert data["errors"] == 0
    assert data["warnings"] == 0
    assert data["violations"] == []
    assert data["files_scanned"] == 5
    assert data["adapter"] == "copilot"


def test_format_json_violation_fields_present(tmp_path: Path):
    """Each violation object in JSON contains all expected fields."""
    v = _error(tmp_path)
    data = json.loads(format_json(_result(tmp_path, violations=[v]), tmp_path))
    assert len(data["violations"]) == 1
    vj = data["violations"][0]
    for field in (
        "check_id",
        "severity",
        "file",
        "line",
        "message",
        "fix_hint",
        "auto_fixable",
    ):
        assert field in vj, f"Violation JSON missing field: {field!r}"


def test_format_json_violation_field_values(tmp_path: Path):
    """Violation field values are correctly serialised."""
    v = _error(tmp_path, filename="skills/a.md", line=7)
    data = json.loads(format_json(_result(tmp_path, violations=[v]), tmp_path))
    vj = data["violations"][0]
    assert vj["check_id"] == "AL-D01"
    assert vj["severity"] == "error"
    assert vj["line"] == 7
    assert vj["auto_fixable"] is False


def test_format_json_path_uses_posix_slashes(tmp_path: Path):
    """Violation file path in JSON uses forward slashes (posix), not backslashes."""
    v = _error(tmp_path, filename="skills/nested/a.md")
    data = json.loads(format_json(_result(tmp_path, violations=[v]), tmp_path))
    assert "\\" not in data["violations"][0]["file"]


def test_format_json_errors_and_warnings_counts(tmp_path: Path):
    violations = [_error(tmp_path), _error(tmp_path, line=2), _warning(tmp_path)]
    data = json.loads(format_json(_result(tmp_path, violations=violations), tmp_path))
    assert data["errors"] == 2
    assert data["warnings"] == 1


# ---------------------------------------------------------------------------
# LintResult.grade()
# ---------------------------------------------------------------------------


def test_grade_a_zero_violations(tmp_path: Path):
    assert _result(tmp_path).grade() == "A"


def test_grade_a_zero_files_scanned(tmp_path: Path):
    """0 files (no instruction files found) → Grade A, not a crash or ZeroDivisionError."""
    assert _result(tmp_path, files_scanned=0).grade() == "A"


def test_grade_b_one_error_one_file(tmp_path: Path):
    """score = 100 − 20 = 80 → Grade B."""
    r = _result(tmp_path, violations=[_error(tmp_path)], files_scanned=1)
    assert r.grade() == "B"


def test_grade_c_six_warnings_one_file(tmp_path: Path):
    """score = 100 − (6×5) = 70 → Grade C."""
    warnings = [_warning(tmp_path, line=i) for i in range(1, 7)]
    r = _result(tmp_path, violations=warnings, files_scanned=1)
    assert r.grade() == "C"


def test_grade_f_three_errors_one_file(tmp_path: Path):
    """score = 100 − (3×20) = 40 → Grade F."""
    errors = [_error(tmp_path, line=i) for i in range(1, 4)]
    r = _result(tmp_path, violations=errors, files_scanned=1)
    assert r.grade() == "F"


def test_grade_density_is_per_file_not_absolute(tmp_path: Path):
    """Grade uses violations-per-file density — 1 error across 10 files stays Grade A."""
    errors = [_error(tmp_path)]
    # 1 error / 10 files → density = 0.1 → score = 100 − 2 = 98 → Grade A
    r = _result(tmp_path, violations=errors, files_scanned=10)
    assert r.grade() == "A"


# ---------------------------------------------------------------------------
# _rel() resilience — path outside repo root
# ---------------------------------------------------------------------------


def test_format_json_path_outside_root_does_not_raise(tmp_path: Path):
    """A violation file path outside the repo root is serialised without raising."""
    outside = Path(tmp_path.root) / "some" / "external" / "path.md"
    v = Violation(
        check_id="AL-F01",
        severity=Severity.WARNING,
        file=outside,
        line=1,
        message="test",
        fix_hint="",
    )
    r = _result(tmp_path, violations=[v], files_scanned=1)
    output = format_json(r, tmp_path)  # must not raise
    data = json.loads(output)
    assert len(data["violations"]) == 1


def test_format_text_path_outside_root_does_not_raise(tmp_path: Path):
    outside = Path(tmp_path.root) / "external" / "file.md"
    v = Violation(
        check_id="AL-D01",
        severity=Severity.ERROR,
        file=outside,
        line=1,
        message="test",
        fix_hint="",
    )
    r = _result(tmp_path, violations=[v], files_scanned=1)
    text = format_text(r, tmp_path)  # must not raise
    assert "AL-D01" in text


# ---------------------------------------------------------------------------
# format_badge()
# ---------------------------------------------------------------------------


def test_format_badge_is_svg(tmp_path: Path):
    """format_badge returns a string that starts with <svg."""
    from agentlint.report import format_badge

    r = _result(tmp_path, files_scanned=2)
    svg = format_badge(r)
    assert svg.startswith("<svg")
    assert "</svg>" in svg


def test_format_badge_grade_a_embedded(tmp_path: Path):
    """Grade A is embedded in the badge SVG for a clean result."""
    from agentlint.report import format_badge

    r = _result(tmp_path, files_scanned=1)
    assert "Grade: A" in format_badge(r)


def test_format_badge_grade_f_embedded(tmp_path: Path):
    """Grade F is embedded in the badge SVG for a heavily failing result."""
    from agentlint.report import format_badge

    errors = [_error(tmp_path, line=i) for i in range(1, 4)]
    r = _result(tmp_path, violations=errors, files_scanned=1)
    assert r.grade() == "F"
    assert "Grade: F" in format_badge(r)


def test_format_badge_colours_differ_by_grade(tmp_path: Path):
    """Grade A and Grade F badges use different fill colours."""
    from agentlint.report import format_badge

    a_svg = format_badge(_result(tmp_path, files_scanned=1))
    errors = [_error(tmp_path, line=i) for i in range(1, 4)]
    f_svg = format_badge(_result(tmp_path, violations=errors, files_scanned=1))
    # Extract the first fill colour from each (the value-rect fill)
    import re

    def _color(svg: str) -> str:
        m = re.search(r'fill="(#[0-9a-fA-F]{6})"', svg)
        return m.group(1) if m else ""

    assert _color(a_svg) != _color(f_svg)
