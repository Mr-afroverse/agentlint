"""
Tests for extra_paths — extending AL-P* and AL-F01 to general documentation files.

Covers:
  - Pass: no extra_paths configured → no extra scanning
  - Pass: extra markdown passes all checks
  - Pass: files already collected by adapter are deduped
  - Pass: ignore_paths respected for extra files
  - Fail: forbidden pattern in extra markdown file caught by AL-P*
  - Fail: broken file reference in extra markdown caught by AL-F01
  - AL-D01/AL-N01/AL-T01 do NOT fire on extra docs (scope isolation)
"""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from agentlint.cli import main, _collect_extra
from agentlint.config import Config
from agentlint.models import Role

_RUNNER = CliRunner()


def _make_copilot_repo(root: Path) -> None:
    """Minimal copilot repo — all instruction checks pass."""
    skill_dir = root / ".github" / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# My Skill\nWrite tests first.\n", encoding="utf-8"
    )
    dispatch = "| `my-skill` | `.github/skills/my-skill/SKILL.md` | any feature |\n"
    (root / ".github" / "copilot-instructions.md").write_text(
        dispatch, encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# _collect_extra unit tests
# ---------------------------------------------------------------------------


def test_collect_extra_empty_when_no_config(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Hello\n", encoding="utf-8")
    cfg = Config()  # extra_paths is []
    extra = _collect_extra(tmp_path, cfg, set())
    assert extra == []


def test_collect_extra_finds_markdown(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Hello\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "GUIDE.md").write_text("# Guide\n", encoding="utf-8")
    cfg = Config()
    cfg.extra_paths = ["**/*.md"]
    extra = _collect_extra(tmp_path, cfg, set())
    assert len(extra) == 2
    assert all(f.role == Role.DOCS for f in extra)
    assert all(f.adapter == "docs" for f in extra)


def test_collect_extra_dedupes_adapter_files(tmp_path: Path):
    _make_copilot_repo(tmp_path)
    (tmp_path / "README.md").write_text("# Hello\n", encoding="utf-8")
    cfg = Config()
    cfg.extra_paths = ["**/*.md"]
    # Simulate adapter already collected these
    already = {
        (tmp_path / ".github" / "copilot-instructions.md").resolve(),
        (tmp_path / ".github" / "skills" / "my-skill" / "SKILL.md").resolve(),
    }
    extra = _collect_extra(tmp_path, cfg, already)
    paths = {f.path.name for f in extra}
    assert "copilot-instructions.md" not in paths
    assert "SKILL.md" not in paths
    assert "README.md" in paths


def test_collect_extra_respects_ignore_paths(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Hello\n", encoding="utf-8")
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "OLD.md").write_text("# Old\n", encoding="utf-8")
    cfg = Config()
    cfg.extra_paths = ["**/*.md"]
    cfg.ignore_paths = ["archive/"]
    extra = _collect_extra(tmp_path, cfg, set())
    names = {f.path.name for f in extra}
    assert "README.md" in names
    assert "OLD.md" not in names


# ---------------------------------------------------------------------------
# Integration: forbidden pattern fires on extra docs
# ---------------------------------------------------------------------------


def test_forbidden_pattern_fires_on_extra_markdown(tmp_path: Path):
    _make_copilot_repo(tmp_path)
    (tmp_path / "README.md").write_text(
        "We have 1338 tests passing in CI.\n", encoding="utf-8"
    )

    # Write config with extra_paths
    cfg_content = "extra_paths:\n  - '**/*.md'\n"
    (tmp_path / ".agentlint.yml").write_text(cfg_content, encoding="utf-8")

    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert "AL-P01" in result.output
    assert "README.md" in result.output


def test_custom_forbidden_pattern_on_extra_docs(tmp_path: Path):
    _make_copilot_repo(tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "DEPLOY.md").write_text(
        "Use source eu-gdpr-main for ingestion.\n", encoding="utf-8"
    )
    cfg_content = (
        "extra_paths:\n"
        "  - 'docs/*.md'\n"
        "forbidden_patterns:\n"
        "  - id: STALE-SRC\n"
        "    pattern: '\\beu-gdpr-main\\b'\n"
        "    reason: 'Removed source ID'\n"
        "    severity: error\n"
    )
    (tmp_path / ".agentlint.yml").write_text(cfg_content, encoding="utf-8")

    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert "STALE-SRC" in result.output
    assert "DEPLOY.md" in result.output


# ---------------------------------------------------------------------------
# Integration: file reference check on extra docs
# ---------------------------------------------------------------------------


def test_file_reference_fires_on_extra_markdown(tmp_path: Path):
    _make_copilot_repo(tmp_path)
    (tmp_path / "README.md").write_text(
        "See `app/services/nonexistent.py` for details.\n", encoding="utf-8"
    )
    cfg_content = "extra_paths:\n  - '*.md'\n"
    (tmp_path / ".agentlint.yml").write_text(cfg_content, encoding="utf-8")

    result = _RUNNER.invoke(main, [str(tmp_path)])
    assert "AL-F01" in result.output
    assert "README.md" in result.output


# ---------------------------------------------------------------------------
# Scope isolation: instruction-only checks DON'T fire on extra docs
# ---------------------------------------------------------------------------


def test_n01_does_not_fire_on_extra_docs(tmp_path: Path):
    """AL-N01 (number sourcing) only scans SKILL files, not DOCS."""
    _make_copilot_repo(tmp_path)
    # This percentage in README would trigger AL-N01 if it were scanned as SKILL
    (tmp_path / "README.md").write_text(
        "Coverage is at 95% and improving.\n", encoding="utf-8"
    )
    cfg_content = "extra_paths:\n  - '*.md'\n"
    (tmp_path / ".agentlint.yml").write_text(cfg_content, encoding="utf-8")

    result = _RUNNER.invoke(main, [str(tmp_path)])
    # AL-N01 should NOT appear — it only fires on Role.SKILL
    assert "AL-N01" not in result.output
