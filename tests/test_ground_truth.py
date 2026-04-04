"""
Tests for AL-G01 — ground-truth file checks.

Covers:
  - value_match: pass when doc value matches JSON truth
  - value_match: fail when doc value differs
  - value_match: warning when JSON file missing
  - value_match: warning when JSON path not found
  - value_match: warning when JSON invalid
  - no_stale_refs: pass when all refs are valid
  - no_stale_refs: fail when stale ref found
  - Handles: nested JSON path
  - Handles: array fan-out path (items[*].id)
  - Handles: glob patterns in target files
"""

from __future__ import annotations

import json
from pathlib import Path

from agentlint.checks.ground_truth import run, _navigate
from agentlint.config import Config
from agentlint.models import Severity


def _setup_json(root: Path, filename: str, data: dict) -> None:
    p = root / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data), encoding="utf-8")


def _setup_doc(root: Path, filename: str, content: str) -> None:
    p = root / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ---- value_match pass ----


def test_g01_pass_value_matches(tmp_path: Path):
    _setup_json(tmp_path, "results.json", {"passed": 623})
    _setup_doc(tmp_path, "README.md", "We have 623 passed tests.")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "TC",
            "json_file": "results.json",
            "json_path": "passed",
            "doc_pattern": r"\b(\d+) passed",
            "files": ["README.md"],
        }
    ]
    violations = run([], cfg, tmp_path)
    assert violations == []


def test_g01_pass_no_match_in_doc(tmp_path: Path):
    _setup_json(tmp_path, "results.json", {"passed": 623})
    _setup_doc(tmp_path, "README.md", "No test counts mentioned here.")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "TC",
            "json_file": "results.json",
            "json_path": "passed",
            "doc_pattern": r"\b(\d+) passed",
            "files": ["README.md"],
        }
    ]
    violations = run([], cfg, tmp_path)
    assert violations == []


# ---- value_match fail ----


def test_g01_fail_value_mismatch(tmp_path: Path):
    _setup_json(tmp_path, "results.json", {"passed": 623})
    _setup_doc(tmp_path, "README.md", "We have 497 passed tests.")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "TC",
            "json_file": "results.json",
            "json_path": "passed",
            "doc_pattern": r"\b(\d+) passed",
            "files": ["README.md"],
            "severity": "error",
            "reason": "Test count must match",
        }
    ]
    violations = run([], cfg, tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-G01"
    assert violations[0].severity == Severity.ERROR
    assert "497" in violations[0].message
    assert "623" in violations[0].message


def test_g01_fail_json_file_missing(tmp_path: Path):
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "TC",
            "json_file": "missing.json",
            "json_path": "passed",
            "doc_pattern": r"\b(\d+) passed",
            "files": ["README.md"],
        }
    ]
    violations = run([], cfg, tmp_path)
    assert len(violations) == 1
    assert "not found" in violations[0].message


def test_g01_fail_json_path_missing(tmp_path: Path):
    _setup_json(tmp_path, "results.json", {"other": 1})
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "TC",
            "json_file": "results.json",
            "json_path": "passed",
            "doc_pattern": r"\b(\d+) passed",
            "files": ["README.md"],
        }
    ]
    violations = run([], cfg, tmp_path)
    assert len(violations) == 1
    assert "not found" in violations[0].message


def test_g01_fail_invalid_json(tmp_path: Path):
    (tmp_path / "bad.json").write_text("{invalid", encoding="utf-8")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "TC",
            "json_file": "bad.json",
            "json_path": "x",
            "doc_pattern": r"(\d+)",
            "files": ["README.md"],
        }
    ]
    violations = run([], cfg, tmp_path)
    assert len(violations) == 1
    assert "Cannot parse" in violations[0].message


# ---- nested / array paths ----


def test_g01_nested_path(tmp_path: Path):
    _setup_json(tmp_path, "cfg.json", {"settings": {"max_retries": 5}})
    _setup_doc(tmp_path, "README.md", "max retries: 3")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "MR",
            "json_file": "cfg.json",
            "json_path": "settings.max_retries",
            "doc_pattern": r"max retries: (\d+)",
            "files": ["README.md"],
        }
    ]
    violations = run([], cfg, tmp_path)
    assert len(violations) == 1
    assert "3" in violations[0].message
    assert "5" in violations[0].message


def test_g01_array_fanout(tmp_path: Path):
    data = {"sources": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}
    _setup_json(tmp_path, "sources.json", data)
    _setup_doc(tmp_path, "README.md", "source: x-stale")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "SRC",
            "json_file": "sources.json",
            "json_path": "sources[*].id",
            "mode": "no_stale_refs",
            "ref_pattern": r"source: ([\w-]+)",
            "files": ["README.md"],
        }
    ]
    violations = run([], cfg, tmp_path)
    assert len(violations) == 1
    assert "x-stale" in violations[0].message


# ---- no_stale_refs pass ----


def test_g01_no_stale_refs_pass(tmp_path: Path):
    data = {"sources": [{"id": "alpha"}, {"id": "beta"}]}
    _setup_json(tmp_path, "sources.json", data)
    _setup_doc(tmp_path, "README.md", "source: alpha\nsource: beta")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "SRC",
            "json_file": "sources.json",
            "json_path": "sources[*].id",
            "mode": "no_stale_refs",
            "ref_pattern": r"source: ([\w-]+)",
            "files": ["README.md"],
        }
    ]
    violations = run([], cfg, tmp_path)
    assert violations == []


# ---- glob target files ----


def test_g01_glob_target_files(tmp_path: Path):
    _setup_json(tmp_path, "results.json", {"passed": 100})
    _setup_doc(tmp_path, "docs/a.md", "50 passed")
    _setup_doc(tmp_path, "docs/b.md", "100 passed")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "TC",
            "json_file": "results.json",
            "json_path": "passed",
            "doc_pattern": r"\b(\d+) passed",
            "files": ["docs/*.md"],
        }
    ]
    violations = run([], cfg, tmp_path)
    # Only docs/a.md should fail (50 ≠ 100)
    assert len(violations) == 1
    assert "50" in violations[0].message


# ---- _navigate unit tests ----


def test_navigate_simple():
    assert _navigate({"x": 42}, "x") == 42


def test_navigate_nested():
    assert _navigate({"a": {"b": 3}}, "a.b") == 3


def test_navigate_array_fanout():
    data = {"items": [{"id": "a"}, {"id": "b"}]}
    assert _navigate(data, "items[*].id") == ["a", "b"]


def test_navigate_missing_key():
    assert _navigate({"x": 1}, "y") is None


def test_navigate_dollar_prefix():
    assert _navigate({"x": 5}, "$.x") == 5
