from __future__ import annotations

from pathlib import Path

from agentlint.checks.encoding_check import run
from agentlint.config import Config
from agentlint.models import InstructionFile, Role


def _make_file(
    tmp_path: Path, raw_bytes: bytes, role: Role = Role.SKILL
) -> InstructionFile:
    p = tmp_path / "test.md"
    p.write_bytes(raw_bytes)
    content = raw_bytes.decode("utf-8", errors="replace")
    return InstructionFile(
        path=p,
        content=content,
        lines=content.splitlines(),
        adapter="copilot",
        role=role,
        metadata={},
    )


# ---------------------------------------------------------------------------
# clean UTF-8 — no violations
# ---------------------------------------------------------------------------


def test_valid_utf8_passes(tmp_path: Path):
    f = _make_file(tmp_path, "# Hello — world\n".encode("utf-8"))
    assert run([f], Config(), tmp_path) == []


def test_valid_utf8_with_multibyte_chars(tmp_path: Path):
    f = _make_file(tmp_path, "こんにちは\n".encode("utf-8"))
    assert run([f], Config(), tmp_path) == []


def test_empty_file_passes(tmp_path: Path):
    f = _make_file(tmp_path, b"")
    assert run([f], Config(), tmp_path) == []


# ---------------------------------------------------------------------------
# non-UTF-8 — fires AL-ENC01
# ---------------------------------------------------------------------------


def test_latin1_byte_fires(tmp_path: Path):
    # 0xFF is valid Latin-1 but not valid UTF-8
    raw = b"# Title\nRating: \xff\n"
    f = _make_file(tmp_path, raw)
    violations = run([f], Config(), tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-ENC01"


def test_windows1252_byte_fires(tmp_path: Path):
    # 0x80 is a Windows-1252 euro sign — invalid UTF-8
    raw = b"Price: \x80100\n"
    f = _make_file(tmp_path, raw)
    violations = run([f], Config(), tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-ENC01"


def test_violation_message_includes_byte_offset(tmp_path: Path):
    raw = b"AB\xff"
    f = _make_file(tmp_path, raw)
    violations = run([f], Config(), tmp_path)
    assert "2" in violations[0].message  # byte offset 2


def test_violation_severity_is_error(tmp_path: Path):
    f = _make_file(tmp_path, b"\xff")
    violations = run([f], Config(), tmp_path)
    assert violations[0].severity.value == "error"


# ---------------------------------------------------------------------------
# roles — runs on SKILL, DISPATCH, DOCS
# ---------------------------------------------------------------------------


def test_fires_on_dispatch_file(tmp_path: Path):
    f = _make_file(tmp_path, b"# title\n\xff", role=Role.DISPATCH)
    violations = run([f], Config(), tmp_path)
    assert len(violations) == 1


def test_fires_on_docs_file(tmp_path: Path):
    f = _make_file(tmp_path, b"# title\n\xff", role=Role.DOCS)
    violations = run([f], Config(), tmp_path)
    assert len(violations) == 1


# ---------------------------------------------------------------------------
# ignore_paths
# ---------------------------------------------------------------------------


def test_ignore_paths_respected(tmp_path: Path):
    f = _make_file(tmp_path, b"\xff")
    config = Config()
    config.ignore_paths = ["test.md"]
    assert run([f], config, tmp_path) == []
