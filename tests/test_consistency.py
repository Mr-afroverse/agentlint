"""
Tests for AL-C01 — cross-file value consistency groups.

Covers:
  - Pass: all files agree on value
  - Pass: fewer than 2 files exist → skip
  - Pass: invalid regex → skip silently
  - Fail: one file has different value → flagged
  - Fail: multiple disagreeing files
  - Handles: no capture group (uses full match)
  - Handles: missing file skipped without error
"""

from __future__ import annotations

from pathlib import Path

from agentlint.checks.consistency import run
from agentlint.config import Config
from agentlint.models import Severity


def _setup(root: Path, file_contents: dict[str, str], pattern: str) -> Config:
    for rel, content in file_contents.items():
        fpath = root / rel
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
    cfg = Config()
    cfg.consistency_groups = [
        {
            "id": "test-count",
            "pattern": pattern,
            "files": list(file_contents.keys()),
            "severity": "error",
        }
    ]
    return cfg


def test_c01_pass_all_agree(tmp_path: Path):
    cfg = _setup(
        tmp_path,
        {"a.md": "623 passed, 2 skipped", "b.md": "623 passed tests"},
        r"\b(\d+)\s+passed",
    )
    violations = run([], cfg, tmp_path)
    assert violations == []


def test_c01_pass_fewer_than_2_files(tmp_path: Path):
    cfg = _setup(
        tmp_path,
        {"a.md": "623 passed"},
        r"\b(\d+)\s+passed",
    )
    # Only 1 file in the list — nothing to compare
    cfg.consistency_groups[0]["files"] = ["a.md"]
    violations = run([], cfg, tmp_path)
    assert violations == []


def test_c01_pass_invalid_regex(tmp_path: Path):
    cfg = _setup(
        tmp_path,
        {"a.md": "hello", "b.md": "hello"},
        r"[invalid",
    )
    violations = run([], cfg, tmp_path)
    assert violations == []


def test_c01_fail_one_differs(tmp_path: Path):
    cfg = _setup(
        tmp_path,
        {
            "a.md": "623 passed, 2 skipped",
            "b.md": "623 passed tests",
            "c.md": "497 passed, old count",
        },
        r"\b(\d+)\s+passed",
    )
    violations = run([], cfg, tmp_path)
    assert len(violations) == 1
    assert "497" in violations[0].message
    assert "623" in violations[0].message
    assert violations[0].severity == Severity.ERROR


def test_c01_fail_multiple_disagree(tmp_path: Path):
    cfg = _setup(
        tmp_path,
        {
            "a.md": "623 passed",
            "b.md": "497 passed",
            "c.md": "580 passed",
        },
        r"\b(\d+)\s+passed",
    )
    violations = run([], cfg, tmp_path)
    # All 3 different — no consensus majority, each has count 1
    # The first in counter wins; the other 2 are flagged
    assert len(violations) == 2


def test_c01_missing_file_skipped(tmp_path: Path):
    cfg = _setup(
        tmp_path,
        {"a.md": "623 passed", "b.md": "623 passed"},
        r"\b(\d+)\s+passed",
    )
    # Add a third file to the list that doesn't exist
    cfg.consistency_groups[0]["files"].append("nonexistent.md")
    violations = run([], cfg, tmp_path)
    assert violations == []


def test_c01_no_capture_group_uses_full_match(tmp_path: Path):
    cfg = _setup(
        tmp_path,
        {"a.md": "version 2.0", "b.md": "version 3.0"},
        r"version \d+\.\d+",
    )
    violations = run([], cfg, tmp_path)
    assert len(violations) == 1
    assert "version" in violations[0].message


def test_c01_severity_from_config(tmp_path: Path):
    cfg = _setup(
        tmp_path,
        {"a.md": "623 passed", "b.md": "497 passed"},
        r"\b(\d+)\s+passed",
    )
    cfg.consistency_groups[0]["severity"] = "warning"
    violations = run([], cfg, tmp_path)
    assert violations[0].severity == Severity.WARNING


def test_c01_invalid_severity_falls_back_to_error(tmp_path: Path):
    """An unrecognised severity string in consistency_groups falls back to ERROR."""
    cfg = _setup(
        tmp_path,
        {"a.md": "623 passed", "b.md": "497 passed"},
        r"\b(\d+)\s+passed",
    )
    cfg.consistency_groups[0]["severity"] = "INVALID_SEVERITY"
    violations = run([], cfg, tmp_path)
    assert len(violations) >= 1
    assert violations[0].severity == Severity.ERROR
