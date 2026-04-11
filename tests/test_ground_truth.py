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


def test_navigate_fanout_key_on_non_dict():
    # key prefix in fan-out but current is not a dict → None
    assert _navigate([1, 2, 3], "items[*]") is None


def test_navigate_fanout_value_is_not_list():
    # key resolves but the value is a scalar, not a list → None
    assert _navigate({"items": 42}, "items[*].id") is None


def test_navigate_fanout_with_nested_remaining():
    # array fan-out with a dotted remaining path exercises the list-comprehension branch
    data = {"items": [{"sub": {"id": "x"}}, {"sub": {"id": "y"}}]}
    assert _navigate(data, "items[*].sub.id") == ["x", "y"]


def test_navigate_list_index_by_digit():
    # numeric part used as list index
    assert _navigate([10, 20, 30], "1") == 20


def test_g01_value_match_empty_doc_pattern(tmp_path: Path):
    # doc_pattern empty → early return, no violations
    _setup_json(tmp_path, "results.json", {"passed": 100})
    _setup_doc(tmp_path, "README.md", "100 passed")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "TC",
            "json_file": "results.json",
            "json_path": "passed",
            "doc_pattern": "",
            "files": ["README.md"],
        }
    ]
    assert run([], cfg, tmp_path) == []


def test_g01_value_match_bad_regex(tmp_path: Path):
    # invalid doc_pattern regex → silently skipped, no violations
    _setup_json(tmp_path, "results.json", {"passed": 100})
    _setup_doc(tmp_path, "README.md", "100 passed")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "TC",
            "json_file": "results.json",
            "json_path": "passed",
            "doc_pattern": "[invalid",
            "files": ["README.md"],
        }
    ]
    assert run([], cfg, tmp_path) == []


def test_g01_stale_refs_non_list_valid_ids(tmp_path: Path):
    # valid_ids is a scalar (non-list) → _check_stale_refs returns immediately
    _setup_json(tmp_path, "data.json", {"ids": "not-a-list"})
    _setup_doc(tmp_path, "README.md", "ref: stale")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "SR",
            "json_file": "data.json",
            "json_path": "ids",
            "mode": "no_stale_refs",
            "ref_pattern": r"ref: ([\w-]+)",
            "files": ["README.md"],
        }
    ]
    assert run([], cfg, tmp_path) == []


def test_g01_stale_refs_empty_valid_set(tmp_path: Path):
    # valid_ids list is all None → valid_set is empty → early return
    _setup_json(tmp_path, "data.json", {"ids": [None, None]})
    _setup_doc(tmp_path, "README.md", "ref: something")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "SR",
            "json_file": "data.json",
            "json_path": "ids",
            "mode": "no_stale_refs",
            "ref_pattern": r"ref: ([\w-]+)",
            "files": ["README.md"],
        }
    ]
    assert run([], cfg, tmp_path) == []


def test_g01_stale_refs_bad_regex(tmp_path: Path):
    # invalid ref_pattern → silently skipped
    data = {"ids": ["alpha"]}
    _setup_json(tmp_path, "data.json", data)
    _setup_doc(tmp_path, "README.md", "ref: alpha")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "SR",
            "json_file": "data.json",
            "json_path": "ids",
            "mode": "no_stale_refs",
            "ref_pattern": "[bad",
            "files": ["README.md"],
        }
    ]
    assert run([], cfg, tmp_path) == []


def test_g01_stale_refs_with_reason(tmp_path: Path):
    # stale ref violation message includes the reason field
    data = {"ids": ["alpha", "beta"]}
    _setup_json(tmp_path, "data.json", data)
    _setup_doc(tmp_path, "README.md", "ref: stale-id")
    cfg = Config()
    cfg.ground_truth_files = [
        {
            "id": "SR",
            "json_file": "data.json",
            "json_path": "ids",
            "mode": "no_stale_refs",
            "ref_pattern": r"ref: ([\w-]+)",
            "files": ["README.md"],
            "reason": "IDs must come from the approved list",
        }
    ]
    violations = run([], cfg, tmp_path)
    assert len(violations) == 1
    assert "stale-id" in violations[0].message
    assert "IDs must come from the approved list" in violations[0].message
