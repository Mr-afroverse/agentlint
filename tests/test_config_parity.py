"""
Tests for AL-E01 — config file key parity (.env vs .env.example).

Covers:
  - Pass: template has all keys from source
  - Pass: source file missing → skip silently
  - Pass: template file missing → skip silently
  - Pass: excluded keys not flagged
  - Fail: missing key detected with correct message
  - Fail: multiple missing keys
  - Handles: export prefix, blank lines, comments, KEY= with no value
"""

from __future__ import annotations

from pathlib import Path

from agentlint.checks.config_parity import run
from agentlint.config import Config
from agentlint.models import Severity


def _setup(root: Path, source: str, template: str) -> Config:
    env = root / ".env"
    example = root / ".env.example"
    env.write_text(source, encoding="utf-8")
    example.write_text(template, encoding="utf-8")
    cfg = Config()
    cfg.config_parity = [{"source": ".env", "template": ".env.example"}]
    return cfg


def test_e01_pass_all_keys_present(tmp_path: Path):
    cfg = _setup(tmp_path, "A=1\nB=2\n", "A=\nB=\n")
    violations = run([], cfg, tmp_path)
    assert violations == []


def test_e01_pass_source_missing(tmp_path: Path):
    (tmp_path / ".env.example").write_text("A=\n", encoding="utf-8")
    cfg = Config()
    cfg.config_parity = [{"source": ".env", "template": ".env.example"}]
    violations = run([], cfg, tmp_path)
    assert violations == []


def test_e01_pass_template_missing(tmp_path: Path):
    (tmp_path / ".env").write_text("A=1\n", encoding="utf-8")
    cfg = Config()
    cfg.config_parity = [{"source": ".env", "template": ".env.example"}]
    violations = run([], cfg, tmp_path)
    assert violations == []


def test_e01_pass_excluded_key(tmp_path: Path):
    cfg = _setup(tmp_path, "A=1\nSECRET=x\n", "A=\n")
    cfg.config_parity[0]["exclude_keys"] = ["SECRET"]
    violations = run([], cfg, tmp_path)
    assert violations == []


def test_e01_fail_missing_key(tmp_path: Path):
    cfg = _setup(tmp_path, "A=1\nB=2\n", "A=\n")
    violations = run([], cfg, tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-E01"
    assert "B" in violations[0].message
    assert violations[0].severity == Severity.ERROR


def test_e01_fail_multiple_missing(tmp_path: Path):
    cfg = _setup(tmp_path, "A=1\nB=2\nC=3\n", "A=\n")
    violations = run([], cfg, tmp_path)
    assert len(violations) == 2
    keys = {v.message.split("`")[1] for v in violations}
    assert keys == {"B", "C"}


def test_e01_handles_export_prefix(tmp_path: Path):
    cfg = _setup(tmp_path, "export SECRET_KEY=abc\n", "")
    violations = run([], cfg, tmp_path)
    assert len(violations) == 1
    assert "SECRET_KEY" in violations[0].message


def test_e01_handles_comments_and_blanks(tmp_path: Path):
    source = "# DB config\n\nDB_HOST=localhost\n# DB_PORT=5432\n"
    cfg = _setup(tmp_path, source, "DB_HOST=\n")
    violations = run([], cfg, tmp_path)
    assert violations == []


def test_e01_severity_from_config(tmp_path: Path):
    cfg = _setup(tmp_path, "A=1\nB=2\n", "A=\n")
    cfg.config_parity[0]["severity"] = "warning"
    violations = run([], cfg, tmp_path)
    assert violations[0].severity == Severity.WARNING


def test_e01_invalid_severity_falls_back_to_error(tmp_path: Path):
    """An unrecognised severity string in config_parity falls back to ERROR."""
    cfg = _setup(tmp_path, "A=1\nB=2\n", "A=\n")
    cfg.config_parity[0]["severity"] = "INVALID_SEVERITY"
    violations = run([], cfg, tmp_path)
    assert len(violations) == 1
    assert violations[0].severity == Severity.ERROR
