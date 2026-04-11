"""Tests for AL-FRESH01 — stale date detection."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from agentlint.checks.freshness import _parse_date, run
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


def _cfg(stale_days: int = 180) -> Config:
    c = Config()
    c.stale_days = stale_days
    return c


def _old_iso(days: int = 400) -> str:
    """Return an ISO-8601 date string that is `days` days in the past."""
    return (date.today() - timedelta(days=days)).isoformat()


def _new_iso(days: int = 10) -> str:
    """Return an ISO-8601 date string that is `days` days in the past."""
    return (date.today() - timedelta(days=days)).isoformat()


# ---------------------------------------------------------------------------
# _parse_date unit tests
# ---------------------------------------------------------------------------


def test_parse_date_iso():
    d = _parse_date("2022-06-15", "%Y-%m-%d")
    assert d == date(2022, 6, 15)


def test_parse_date_slash():
    d = _parse_date("2022/06/15", "%Y/%m/%d")
    assert d == date(2022, 6, 15)


def test_parse_date_long_month():
    d = _parse_date("January 15, 2022", None)
    assert d == date(2022, 1, 15)


def test_parse_date_short_month():
    d = _parse_date("Jan 15, 2022", None)
    assert d == date(2022, 1, 15)


def test_parse_date_day_first_long():
    d = _parse_date("15 January 2022", None)
    assert d == date(2022, 1, 15)


def test_parse_date_day_first_short():
    d = _parse_date("15 Jan 2022", None)
    assert d == date(2022, 1, 15)


def test_parse_date_invalid_returns_none():
    assert _parse_date("not-a-date", "%Y-%m-%d") is None


# ---------------------------------------------------------------------------
# Disabled by default (stale_days = 0)
# ---------------------------------------------------------------------------


def test_disabled_by_default(tmp_path: Path):
    f = _make_file(tmp_path / "SKILL.md", f"Last updated: {_old_iso()}")
    config = Config()
    assert config.stale_days == 0
    assert run([f], config, tmp_path) == []


# ---------------------------------------------------------------------------
# ISO-8601 stale date fires
# ---------------------------------------------------------------------------


def test_iso_stale_fires(tmp_path: Path):
    old = _old_iso(400)
    f = _make_file(tmp_path / "SKILL.md", f"Deployed on {old}.")
    violations = run([f], _cfg(180), tmp_path)
    assert len(violations) == 1
    v = violations[0]
    assert v.check_id == "AL-FRESH01"
    assert v.severity == Severity.WARNING
    assert old in v.message


# ---------------------------------------------------------------------------
# Recent date (within threshold) → no violation
# ---------------------------------------------------------------------------


def test_recent_date_no_violation(tmp_path: Path):
    recent = _new_iso(10)
    f = _make_file(tmp_path / "SKILL.md", f"Updated: {recent}")
    assert run([f], _cfg(180), tmp_path) == []


# ---------------------------------------------------------------------------
# Future date → no violation
# ---------------------------------------------------------------------------


def test_future_date_no_violation(tmp_path: Path):
    future = (date.today() + timedelta(days=30)).isoformat()
    f = _make_file(tmp_path / "SKILL.md", f"Scheduled for {future}")
    assert run([f], _cfg(180), tmp_path) == []


# ---------------------------------------------------------------------------
# Slash-format stale date fires
# ---------------------------------------------------------------------------


def test_slash_format_stale_fires(tmp_path: Path):
    old = (date.today() - timedelta(days=400)).strftime("%Y/%m/%d")
    f = _make_file(tmp_path / "SKILL.md", f"Snapshot taken {old}.")
    violations = run([f], _cfg(180), tmp_path)
    assert len(violations) == 1
    assert old in violations[0].message


# ---------------------------------------------------------------------------
# Named-month stale date fires
# ---------------------------------------------------------------------------


def test_named_month_stale_fires(tmp_path: Path):
    f = _make_file(tmp_path / "SKILL.md", "Published on January 15, 2022.")
    violations = run([f], _cfg(180), tmp_path)
    assert len(violations) == 1
    assert "January 15, 2022" in violations[0].message


# ---------------------------------------------------------------------------
# Day-first named-month stale date fires
# ---------------------------------------------------------------------------


def test_day_first_named_month_fires(tmp_path: Path):
    f = _make_file(tmp_path / "SKILL.md", "Released 15 March 2021.")
    violations = run([f], _cfg(180), tmp_path)
    assert len(violations) == 1
    assert "15 March 2021" in violations[0].message


# ---------------------------------------------------------------------------
# Date inside code fence → skipped
# ---------------------------------------------------------------------------


def test_date_inside_code_fence_skipped(tmp_path: Path):
    old = _old_iso(400)
    content = f"Normal text.\n```\ndate = {old}\n```\nEnd.\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    assert run([f], _cfg(180), tmp_path) == []


# ---------------------------------------------------------------------------
# Inline disable comment suppresses violation
# ---------------------------------------------------------------------------


def test_inline_disable_suppresses(tmp_path: Path):
    old = _old_iso(400)
    f = _make_file(
        tmp_path / "SKILL.md",
        f"Last updated: {old}  # agentlint: disable=AL-FRESH01",
    )
    assert run([f], _cfg(180), tmp_path) == []


# ---------------------------------------------------------------------------
# ignore_paths respected
# ---------------------------------------------------------------------------


def test_ignore_paths_respected(tmp_path: Path):
    old = _old_iso(400)
    f = _make_file(tmp_path / "archive" / "OLD.md", f"Date: {old}")
    config = _cfg(180)
    config.ignore_paths = ["archive/"]
    assert run([f], config, tmp_path) == []


# ---------------------------------------------------------------------------
# DOCS role also scanned
# ---------------------------------------------------------------------------


def test_docs_role_scanned(tmp_path: Path):
    old = _old_iso(400)
    f = _make_file(tmp_path / "docs" / "guide.md", f"As of {old}.", role=Role.DOCS)
    violations = run([f], _cfg(180), tmp_path)
    assert len(violations) == 1


# ---------------------------------------------------------------------------
# DISPATCH role also scanned
# ---------------------------------------------------------------------------


def test_dispatch_role_scanned(tmp_path: Path):
    old = _old_iso(400)
    f = _make_file(tmp_path / "CLAUDE.md", f"Config from {old}.", role=Role.DISPATCH)
    violations = run([f], _cfg(180), tmp_path)
    assert len(violations) == 1


# ---------------------------------------------------------------------------
# Exact boundary: age == stale_days → fires (>= threshold)
# ---------------------------------------------------------------------------


def test_boundary_age_equals_threshold_fires(tmp_path: Path):
    exactly = (date.today() - timedelta(days=180)).isoformat()
    f = _make_file(tmp_path / "SKILL.md", f"Updated {exactly}")
    violations = run([f], _cfg(180), tmp_path)
    assert len(violations) == 1


# ---------------------------------------------------------------------------
# One under boundary: age = stale_days - 1 → no violation
# ---------------------------------------------------------------------------


def test_boundary_one_under_no_violation(tmp_path: Path):
    almost = (date.today() - timedelta(days=179)).isoformat()
    f = _make_file(tmp_path / "SKILL.md", f"Updated {almost}")
    assert run([f], _cfg(180), tmp_path) == []


# ---------------------------------------------------------------------------
# Multiple stale dates on different lines → separate violations
# ---------------------------------------------------------------------------


def test_multiple_dates_multiple_violations(tmp_path: Path):
    old1 = _old_iso(400)
    old2 = (date.today() - timedelta(days=500)).isoformat()
    content = f"First: {old1}\nSecond: {old2}\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    violations = run([f], _cfg(180), tmp_path)
    assert len(violations) == 2
