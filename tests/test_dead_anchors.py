from __future__ import annotations

from pathlib import Path

from agentlint.checks.dead_anchors import _to_slug, run
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


# ---------------------------------------------------------------------------
# _to_slug helper
# ---------------------------------------------------------------------------


def test_slug_basic():
    assert _to_slug("My Heading") == "my-heading"


def test_slug_special_chars_stripped():
    assert _to_slug("What's New?") == "whats-new"


def test_slug_backtick_inline():
    assert _to_slug("Using `run()` method") == "using-run-method"


def test_slug_multiple_spaces():
    # Each space becomes its own hyphen (GitHub GFM behaviour).
    # After strip(), "  Hello   World  " → "Hello   World" → "hello---world".
    assert _to_slug("  Hello   World  ") == "hello---world"


def test_slug_ampersand_heading():
    # '&' is stripped, leaving two adjacent spaces, each → '-', so double hyphen.
    # Matches GitHub's slug for e.g. "## Testing & Validation" → #testing--validation
    assert _to_slug("Testing & Validation") == "testing--validation"


def test_slug_numbers():
    assert _to_slug("Section 1.2 Overview") == "section-12-overview"


# ---------------------------------------------------------------------------
# Clean — anchor resolves to heading
# ---------------------------------------------------------------------------


def test_clean_anchor_resolves(tmp_path: Path):
    content = "## My Section\n\nSee [here](#my-section).\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    violations = run([f], Config(), tmp_path)
    assert violations == []


def test_clean_multiple_headings(tmp_path: Path):
    content = (
        "# Overview\n\n"
        "## Details\n\n"
        "Back to [overview](#overview) or [details](#details).\n"
    )
    f = _make_file(tmp_path / "SKILL.md", content)
    violations = run([f], Config(), tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Violation — anchor does not resolve
# ---------------------------------------------------------------------------


def test_violation_dead_anchor(tmp_path: Path):
    content = "## Real Heading\n\nSee [this](#nonexistent-section).\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    violations = run([f], Config(), tmp_path)
    assert len(violations) == 1
    assert violations[0].check_id == "AL-F02"
    assert violations[0].severity == Severity.WARNING
    assert "nonexistent-section" in violations[0].message
    assert violations[0].line == 3


def test_violation_correct_line_number(tmp_path: Path):
    content = "# Intro\n\nLine 2.\n[click](#ghost)\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    violations = run([f], Config(), tmp_path)
    assert violations[0].line == 4


# ---------------------------------------------------------------------------
# Cross-file and external links are ignored
# ---------------------------------------------------------------------------


def test_cross_file_link_ignored(tmp_path: Path):
    content = "## Real\n\nSee [other](other.md#section).\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    violations = run([f], Config(), tmp_path)
    assert violations == []


def test_external_link_ignored(tmp_path: Path):
    content = "## Real\n\nSee [docs](https://example.com#section).\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    violations = run([f], Config(), tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Links inside code fences are skipped
# ---------------------------------------------------------------------------


def test_code_fence_skipped(tmp_path: Path):
    content = "## Real\n\n```\n[text](#ghost-anchor)\n```\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    violations = run([f], Config(), tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# Heading with inline code or bold in title
# ---------------------------------------------------------------------------


def test_heading_with_inline_code(tmp_path: Path):
    content = "## Using `run()` method\n\nSee [run](#using-run-method).\n"
    f = _make_file(tmp_path / "SKILL.md", content)
    violations = run([f], Config(), tmp_path)
    assert violations == []


# ---------------------------------------------------------------------------
# DISPATCH role is also checked
# ---------------------------------------------------------------------------


def test_dispatch_role_checked(tmp_path: Path):
    content = "# Main\n\nLink to [gone](#gone-section).\n"
    f = _make_file(tmp_path / "CLAUDE.md", content, role=Role.DISPATCH)
    violations = run([f], Config(), tmp_path)
    assert any(v.check_id == "AL-F02" for v in violations)


# ---------------------------------------------------------------------------
# ignore_paths suppresses the file
# ---------------------------------------------------------------------------


def test_ignore_paths_suppresses(tmp_path: Path):
    archive = tmp_path / "archive"
    archive.mkdir()
    instr = archive / "OLD.md"
    content = "## Real\n\nLink to [gone](#gone).\n"
    f = _make_file(instr, content)
    config = Config()
    config.ignore_paths = ["archive/"]
    violations = run([f], config, tmp_path)
    assert violations == []
