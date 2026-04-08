from __future__ import annotations

from pathlib import Path

from agentlint.adapters.claudecode import ClaudeCodeAdapter
from agentlint.models import Role

_ADAPTER = ClaudeCodeAdapter()


# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------


def test_detect_true_with_claude_md(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("# instructions", encoding="utf-8")
    assert _ADAPTER.detect(tmp_path) is True


def test_detect_true_with_agents_dir(tmp_path: Path):
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    assert _ADAPTER.detect(tmp_path) is True


def test_detect_true_with_commands_dir(tmp_path: Path):
    (tmp_path / ".claude" / "commands").mkdir(parents=True)
    assert _ADAPTER.detect(tmp_path) is True


def test_detect_false_when_nothing_present(tmp_path: Path):
    assert _ADAPTER.detect(tmp_path) is False


# ---------------------------------------------------------------------------
# collect() — CLAUDE.md (DISPATCH)
# ---------------------------------------------------------------------------


def test_collect_dispatch_from_claude_md(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("# global instructions", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 1
    assert files[0].role == Role.DISPATCH
    assert files[0].adapter == "claudecode"
    assert files[0].path.name == "CLAUDE.md"


def test_collect_dispatch_content_read_correctly(tmp_path: Path):
    content = "Be helpful and concise.\n"
    (tmp_path / "CLAUDE.md").write_text(content, encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert files[0].content == content
    assert files[0].lines == ["Be helpful and concise."]


# ---------------------------------------------------------------------------
# collect() — .claude/agents/*.md (SKILL)
# ---------------------------------------------------------------------------


def test_collect_skill_from_agents_dir(tmp_path: Path):
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "reviewer.md").write_text("# Code Reviewer", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 1
    assert files[0].role == Role.SKILL
    assert files[0].path.name == "reviewer.md"
    assert files[0].adapter == "claudecode"


def test_collect_multiple_agent_files(tmp_path: Path):
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "alpha.md").write_text("# Alpha", encoding="utf-8")
    (agents_dir / "beta.md").write_text("# Beta", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    names = {f.path.name for f in files}
    assert names == {"alpha.md", "beta.md"}
    assert all(f.role == Role.SKILL for f in files)


# ---------------------------------------------------------------------------
# collect() — .claude/commands/*.md (SKILL)
# ---------------------------------------------------------------------------


def test_collect_skill_from_commands_dir(tmp_path: Path):
    commands_dir = tmp_path / ".claude" / "commands"
    commands_dir.mkdir(parents=True)
    (commands_dir / "review.md").write_text("# /review command", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 1
    assert files[0].role == Role.SKILL
    assert files[0].path.name == "review.md"


# ---------------------------------------------------------------------------
# collect() — all sources combined
# ---------------------------------------------------------------------------


def test_collect_all_sources_combined(tmp_path: Path):
    (tmp_path / "CLAUDE.md").write_text("# Global", encoding="utf-8")
    agents_dir = tmp_path / ".claude" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "analyst.md").write_text("# Analyst", encoding="utf-8")
    commands_dir = tmp_path / ".claude" / "commands"
    commands_dir.mkdir(parents=True)
    (commands_dir / "summarize.md").write_text("# /summarize", encoding="utf-8")

    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 3
    roles = [f.role for f in files]
    assert Role.DISPATCH in roles
    assert roles.count(Role.SKILL) == 2


def test_collect_empty_when_nothing_present(tmp_path: Path):
    files = _ADAPTER.collect(tmp_path)
    assert files == []
