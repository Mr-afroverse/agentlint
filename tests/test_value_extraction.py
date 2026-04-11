"""
Tests for AL-V01 — value extraction from source constants.

Covers:
  - Pass: documented value matches source constant
  - Pass: no source annotation with constant path → skip
  - Pass: inside code fence → skip
  - Fail: documented value differs from source constant
  - Fail: source file not found → warning
  - Fail: constant not found in source → warning
  - Handles: float values
  - Handles: dotted constant path (ClassName.attr)
  - Handles: type-annotated assignment (attr: int = 30)
  - Handles: multiple annotations on separate lines
  - AST: module-level constant
  - AST: class-scoped constant (ClassName.ATTR)
  - AST: deeply nested class (Outer.Inner.ATTR)
  - AST: annotated assignment
  - AST: negative numeric literal
  - AST: non-numeric constant returns None
  - AST: syntax error returns None
  - AST: class not found returns None
  - Integration: AST correctly scopes class vs module shadowing
  - Integration: negative constant round-trip via AST
  - Integration: non-.py file uses regex extractor
  - Integration: regex fallback fires when AST returns None
"""

from __future__ import annotations

from pathlib import Path

from agentlint.checks.value_extraction import (
    run,
    _extract_constant_value,
    _extract_constant_value_ast,
)
from agentlint.config import Config
from agentlint.models import InstructionFile, Role, Severity


def _make_file(tmp_path: Path, content: str, role: Role = Role.DOCS) -> InstructionFile:
    p = tmp_path / "doc.md"
    p.write_text(content, encoding="utf-8")
    return InstructionFile(
        path=p,
        content=content,
        lines=content.splitlines(),
        adapter="test",
        role=role,
        metadata={},
    )


def _make_source(tmp_path: Path, filename: str, content: str) -> None:
    (tmp_path / filename).write_text(content, encoding="utf-8")


# ---- pass cases ----


def test_v01_pass_value_matches(tmp_path: Path):
    _make_source(tmp_path, "constants.py", "THRESHOLD = 30\n")
    sf = _make_file(
        tmp_path, "Notification threshold: 30  (Source: constants.py:THRESHOLD)"
    )
    violations = run([sf], Config(), tmp_path)
    assert violations == []


def test_v01_pass_no_constant_path(tmp_path: Path):
    """Plain (Source: file.py) without :constant should be ignored by AL-V01."""
    sf = _make_file(tmp_path, "threshold: 30  (Source: constants.py)")
    violations = run([sf], Config(), tmp_path)
    assert violations == []


def test_v01_pass_code_fence_skipped(tmp_path: Path):
    _make_source(tmp_path, "constants.py", "THRESHOLD = 30\n")
    content = "```\nthreshold: 25  (Source: constants.py:THRESHOLD)\n```"
    sf = _make_file(tmp_path, content)
    violations = run([sf], Config(), tmp_path)
    assert violations == []


def test_v01_pass_float_value(tmp_path: Path):
    _make_source(tmp_path, "config.py", "RATIO = 3.14\n")
    sf = _make_file(tmp_path, "ratio: 3.14  (Source: config.py:RATIO)")
    violations = run([sf], Config(), tmp_path)
    assert violations == []


def test_v01_pass_typed_assignment(tmp_path: Path):
    _make_source(tmp_path, "agent.py", "minimum_risk_score: int = 30\n")
    sf = _make_file(
        tmp_path,
        "threshold: 30  (Source: agent.py:NotificationConfig.minimum_risk_score)",
    )
    violations = run([sf], Config(), tmp_path)
    assert violations == []


# ---- fail cases ----


def test_v01_fail_value_mismatch(tmp_path: Path):
    _make_source(tmp_path, "constants.py", "THRESHOLD = 30\n")
    sf = _make_file(
        tmp_path, "Notification threshold: 25  (Source: constants.py:THRESHOLD)"
    )
    violations = run([sf], Config(), tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-V01"
    assert violations[0].severity == Severity.ERROR
    assert "25" in violations[0].message
    assert "30" in violations[0].message


def test_v01_fail_source_file_missing(tmp_path: Path):
    sf = _make_file(tmp_path, "threshold: 25  (Source: nonexistent.py:THRESHOLD)")
    violations = run([sf], Config(), tmp_path)
    assert len(violations) == 1
    assert violations[0].severity == Severity.WARNING
    assert "not found" in violations[0].message


def test_v01_fail_constant_not_found(tmp_path: Path):
    _make_source(tmp_path, "constants.py", "OTHER_VALUE = 99\n")
    sf = _make_file(tmp_path, "threshold: 25  (Source: constants.py:THRESHOLD)")
    violations = run([sf], Config(), tmp_path)
    assert len(violations) == 1
    assert violations[0].severity == Severity.WARNING
    assert "Could not extract" in violations[0].message


def test_v01_fail_multiple_annotations(tmp_path: Path):
    _make_source(
        tmp_path,
        "constants.py",
        "MIN_SCORE = 30\nMAX_SCORE = 100\n",
    )
    content = (
        "min: 25  (Source: constants.py:MIN_SCORE)\n"
        "max: 100  (Source: constants.py:MAX_SCORE)\n"
    )
    sf = _make_file(tmp_path, content)
    violations = run([sf], Config(), tmp_path)
    # Only min is wrong
    assert len(violations) == 1
    assert "25" in violations[0].message
    assert "30" in violations[0].message


def test_v01_rightmost_number(tmp_path: Path):
    """When multiple numbers precede the annotation, use the rightmost one."""
    _make_source(tmp_path, "config.py", "MAX_SCORE = 74\n")
    sf = _make_file(
        tmp_path,
        "SEMI-BINDING \u2192 max 74  (Source: config.py:MAX_SCORE)",
    )
    violations = run([sf], Config(), tmp_path)
    assert violations == []


def test_v01_source_roots(tmp_path: Path):
    """Source file under a configured source_root should be resolved."""
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "config.py").write_text("LIMIT = 50\n", encoding="utf-8")
    cfg = Config()
    cfg.source_roots = ["src"]
    sf = _make_file(tmp_path, "limit: 50  (Source: config.py:LIMIT)")
    violations = run([sf], cfg, tmp_path)
    assert violations == []


# ---- unit helper ----


def test_extract_constant_value_simple():
    assert _extract_constant_value("X = 42\n", "X") == "42"


def test_extract_constant_value_typed():
    assert _extract_constant_value("score: int = 30\n", "Cls.score") == "30"


def test_extract_constant_value_missing():
    assert _extract_constant_value("OTHER = 99\n", "MISSING") is None


# ===========================================================================
# AST extractor — unit tests
# ===========================================================================


def test_ast_module_level_int():
    assert _extract_constant_value_ast("THRESHOLD = 30\n", "THRESHOLD") == "30"


def test_ast_module_level_float():
    assert _extract_constant_value_ast("RATIO = 3.14\n", "RATIO") == "3.14"


def test_ast_class_scoped():
    src = "class Config:\n    LIMIT = 50\n"
    assert _extract_constant_value_ast(src, "Config.LIMIT") == "50"


def test_ast_nested_class():
    src = "class Outer:\n    class Inner:\n        VALUE = 7\n"
    assert _extract_constant_value_ast(src, "Outer.Inner.VALUE") == "7"


def test_ast_annotated_assignment():
    src = "class Cfg:\n    score: int = 42\n"
    assert _extract_constant_value_ast(src, "Cfg.score") == "42"


def test_ast_negative_literal():
    assert _extract_constant_value_ast("OFFSET = -5\n", "OFFSET") == "-5"


def test_ast_non_numeric_returns_none():
    assert _extract_constant_value_ast('NAME = "hello"\n', "NAME") is None


def test_ast_syntax_error_returns_none():
    assert _extract_constant_value_ast("def broken(\n", "X") is None


def test_ast_class_not_found_returns_none():
    src = "THRESHOLD = 30\n"
    assert _extract_constant_value_ast(src, "NonExistent.THRESHOLD") is None


def test_ast_attr_not_found_returns_none():
    src = "class Config:\n    OTHER = 99\n"
    assert _extract_constant_value_ast(src, "Config.MISSING") is None


# ===========================================================================
# Integration: AST scope-awareness
# ===========================================================================


def test_v01_ast_class_scoped_correct(tmp_path: Path):
    """AST correctly reads class-level constant, not a module-level shadow."""
    src = "LIMIT = 99\n\nclass Config:\n    LIMIT = 50\n"
    (tmp_path / "config.py").write_text(src, encoding="utf-8")
    content = "limit is 50  (Source: config.py:Config.LIMIT)"
    sf = _make_file(tmp_path, content)
    assert run([sf], Config(), tmp_path) == []


def test_v01_ast_class_scoped_mismatch(tmp_path: Path):
    """Docs say 99 but class-level value is 50 — error fires."""
    src = "LIMIT = 99\n\nclass Config:\n    LIMIT = 50\n"
    (tmp_path / "config.py").write_text(src, encoding="utf-8")
    content = "limit is 99  (Source: config.py:Config.LIMIT)"
    sf = _make_file(tmp_path, content)
    violations = run([sf], Config(), tmp_path)
    assert len(violations) == 1
    assert violations[0].severity == Severity.ERROR
    assert "50" in violations[0].message


def test_v01_ast_negative_roundtrip(tmp_path: Path):
    """Negative constant is extracted correctly and matches docs."""
    (tmp_path / "config.py").write_text("MIN_DELTA = -1\n", encoding="utf-8")
    content = "min delta: -1  (Source: config.py:MIN_DELTA)"
    sf = _make_file(tmp_path, content)
    assert run([sf], Config(), tmp_path) == []


def test_v01_non_python_uses_regex(tmp_path: Path):
    """Non-.py source file (e.g. .yaml) uses regex extractor — still works."""
    (tmp_path / "config.yaml").write_text("LIMIT: 50\n", encoding="utf-8")
    content = "limit is 50  (Source: config.yaml:LIMIT)"
    cfg = Config()
    cfg.source_roots = ["."]
    sf = _make_file(tmp_path, content)
    # YAML regex won't find "LIMIT = 50" style — it returns None → warning.
    # This confirms the non-Python path is taken (no crash, graceful warn).
    violations = run([sf], cfg, tmp_path)
    # YAML uses `key: value` not `key = value`, so regex gets None → warning
    assert len(violations) == 1
    assert violations[0].severity == Severity.WARNING
    assert "Could not extract" in violations[0].message


def test_v01_ast_fallback_to_regex_on_syntax_error(tmp_path: Path):
    """When AST fails (syntax error in source), regex fallback runs."""
    # File has a syntax error but still contains a parseable constant via regex
    (tmp_path / "broken.py").write_text("LIMIT = 42\ndef broken(\n", encoding="utf-8")
    content = "limit: 42  (Source: broken.py:LIMIT)"
    sf = _make_file(tmp_path, content)
    # AST will fail → regex fallback finds LIMIT = 42 → pass
    assert run([sf], Config(), tmp_path) == []
