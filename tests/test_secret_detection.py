from __future__ import annotations

from pathlib import Path

from agentlint.adapters.claudecode import ClaudeCodeAdapter
from agentlint.checks.secret_detection import run
from agentlint.config import Config
from agentlint.models import InstructionFile, Severity

_ADAPTER = ClaudeCodeAdapter()


def _make_file(tmp_path: Path, content: str) -> list[InstructionFile]:
    """Write CLAUDE.md with given content and return collected files."""
    (tmp_path / "CLAUDE.md").write_text(content, encoding="utf-8")
    return _ADAPTER.collect(tmp_path)


# ---------------------------------------------------------------------------
# Clean file — no violations
# ---------------------------------------------------------------------------


def test_clean_file_no_violations(tmp_path: Path):
    files = _make_file(tmp_path, "Use environment variables for all credentials.\n")
    violations = run(files, Config(), tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Pattern: AWS Access Key
# ---------------------------------------------------------------------------


def test_s01_aws_access_key_detected(tmp_path: Path):
    # Use a synthetic key that does not trigger the placeholder filter
    files = _make_file(tmp_path, "key = AKIABCDEFGHIJKLMNOPQ\n")
    violations = run(files, Config(), tmp_path)
    ids = [v.check_id for v in violations]
    assert "AL-S01-AWS" in ids


# ---------------------------------------------------------------------------
# Pattern: GitHub classic token
# ---------------------------------------------------------------------------


def test_s01_github_classic_token_detected(tmp_path: Path):
    token = "ghp_" + "A" * 36
    files = _make_file(tmp_path, f"token: {token}\n")
    violations = run(files, Config(), tmp_path)
    ids = [v.check_id for v in violations]
    assert "AL-S01-GH" in ids


# ---------------------------------------------------------------------------
# Pattern: GitHub fine-grained PAT
# ---------------------------------------------------------------------------


def test_s01_github_fine_grained_pat_detected(tmp_path: Path):
    token = "github_pat_" + "B" * 59
    files = _make_file(tmp_path, f"auth = {token}\n")
    violations = run(files, Config(), tmp_path)
    ids = [v.check_id for v in violations]
    assert "AL-S01-GH-PAT" in ids


# ---------------------------------------------------------------------------
# Pattern: OpenAI key
# ---------------------------------------------------------------------------


def test_s01_openai_key_detected(tmp_path: Path):
    key = "sk-" + "a" * 48
    files = _make_file(tmp_path, f"OPENAI_API_KEY={key}\n")
    violations = run(files, Config(), tmp_path)
    ids = [v.check_id for v in violations]
    assert "AL-S01-OPENAI" in ids


# ---------------------------------------------------------------------------
# Pattern: Anthropic key
# ---------------------------------------------------------------------------


def test_s01_anthropic_key_detected(tmp_path: Path):
    key = "sk-ant-api03-" + "C" * 93
    files = _make_file(tmp_path, f"key = {key}\n")
    violations = run(files, Config(), tmp_path)
    ids = [v.check_id for v in violations]
    assert "AL-S01-ANTHROPIC" in ids


# ---------------------------------------------------------------------------
# Pattern: JWT
# ---------------------------------------------------------------------------


def test_s01_jwt_detected(tmp_path: Path):
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    files = _make_file(tmp_path, f"Authorization: Bearer {jwt}\n")
    violations = run(files, Config(), tmp_path)
    ids = [v.check_id for v in violations]
    assert "AL-S01-JWT" in ids


# ---------------------------------------------------------------------------
# Pattern: PEM private key
# ---------------------------------------------------------------------------


def test_s01_pem_private_key_detected(tmp_path: Path):
    files = _make_file(tmp_path, "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAK\n")
    violations = run(files, Config(), tmp_path)
    ids = [v.check_id for v in violations]
    assert "AL-S01-PEM" in ids


def test_s01_pem_ec_key_detected(tmp_path: Path):
    files = _make_file(tmp_path, "-----BEGIN EC PRIVATE KEY-----\nMHQCAQEE\n")
    violations = run(files, Config(), tmp_path)
    assert any(v.check_id == "AL-S01-PEM" for v in violations)


# ---------------------------------------------------------------------------
# Pattern: high-entropy hex assignment
# ---------------------------------------------------------------------------


def test_s01_hex_secret_detected(tmp_path: Path):
    hex_val = "a" * 32
    files = _make_file(tmp_path, f'api_key = "{hex_val}"\n')
    violations = run(files, Config(), tmp_path)
    ids = [v.check_id for v in violations]
    assert "AL-S01-HEX" in ids


# ---------------------------------------------------------------------------
# Placeholder suppression — no false positives
# ---------------------------------------------------------------------------


def test_placeholder_suppresses_your_api_key(tmp_path: Path):
    files = _make_file(tmp_path, "Set OPENAI_API_KEY=your-api-key-here\n")
    violations = run(files, Config(), tmp_path)
    assert violations == []


def test_placeholder_suppresses_example_token(tmp_path: Path):
    files = _make_file(tmp_path, "token: example_token_value_here\n")
    violations = run(files, Config(), tmp_path)
    assert violations == []


def test_placeholder_suppresses_angle_bracket_token(tmp_path: Path):
    files = _make_file(tmp_path, "Authorization: Bearer <TOKEN>\n")
    violations = run(files, Config(), tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# auto_fixable / fix_data
# ---------------------------------------------------------------------------


def test_secret_violation_is_always_auto_fixable(tmp_path: Path):
    key = "sk-" + "b" * 48
    files = _make_file(tmp_path, f"OPENAI_KEY={key}\n")
    violations = run(files, Config(), tmp_path)
    s01 = [v for v in violations if v.check_id == "AL-S01-OPENAI"]
    assert len(s01) == 1
    assert s01[0].auto_fixable is True


def test_secret_fix_data_redacts_matched_text(tmp_path: Path):
    key = "sk-" + "c" * 48
    line = f"api = {key}"
    files = _make_file(tmp_path, line + "\n")
    violations = run(files, Config(), tmp_path)
    s01 = [v for v in violations if v.check_id == "AL-S01-OPENAI"]
    assert len(s01) == 1
    assert s01[0].fix_data["old_line"] == line
    # The matched key must be replaced with <REDACTED>
    assert "<REDACTED>" in s01[0].fix_data["new_line"]
    assert key not in s01[0].fix_data["new_line"]


def test_placeholder_suppresses_dummy_key(tmp_path: Path):
    files = _make_file(tmp_path, f'secret_key = "dummy{"x" * 32}"\n')
    violations = run(files, Config(), tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# One violation per line (break after first match)
# ---------------------------------------------------------------------------


def test_one_violation_per_line_even_if_multiple_patterns(tmp_path: Path):
    # A line that matches both GH token and AWS key patterns — should yield only one violation
    gh = "ghp_" + "A" * 36
    aws = "AKIABCDEFGHIJKLMNOP"  # synthetic; avoids placeholder words
    files = _make_file(tmp_path, f"{gh} and {aws}\n")
    violations = run(files, Config(), tmp_path)
    # Should only produce one violation for this single line
    assert len(violations) == 1


# ---------------------------------------------------------------------------
# Severity — warnings, not errors
# ---------------------------------------------------------------------------


def test_violation_severity_is_warning(tmp_path: Path):
    files = _make_file(tmp_path, "key = AKIAIOSFODNN7EXAMPLE\n")
    violations = run(files, Config(), tmp_path)
    assert all(v.severity == Severity.WARNING for v in violations)


# ---------------------------------------------------------------------------
# ignore_paths skips file
# ---------------------------------------------------------------------------


def test_ignore_paths_skips_file(tmp_path: Path):
    files = _make_file(tmp_path, "key = AKIAIOSFODNN7EXAMPLE\n")
    cfg = Config()
    cfg.ignore_paths = ["CLAUDE.md"]
    violations = run(files, cfg, tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Line number is reported correctly
# ---------------------------------------------------------------------------


def test_violation_reports_correct_line_number(tmp_path: Path):
    content = "line one\nline two\nAKIABCDEFGHIJKLMNOPQ here\nline four\n"
    files = _make_file(tmp_path, content)
    violations = run(files, Config(), tmp_path)
    assert len(violations) == 1
    assert violations[0].line == 3
