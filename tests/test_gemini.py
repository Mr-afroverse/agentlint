from __future__ import annotations

from pathlib import Path

from agentlint.adapters.gemini import GeminiAdapter

_ADAPTER = GeminiAdapter()


# ---------------------------------------------------------------------------
# detect()
# ---------------------------------------------------------------------------


def test_gemini_detect_via_gemini_md(tmp_path: Path):
    (tmp_path / "GEMINI.md").write_text("# Gemini\n", encoding="utf-8")
    assert _ADAPTER.detect(tmp_path) is True


def test_gemini_detect_via_rules_dir(tmp_path: Path):
    rules_dir = tmp_path / ".gemini" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "coding.md").write_text("# Coding\n", encoding="utf-8")
    assert _ADAPTER.detect(tmp_path) is True


def test_gemini_no_detect_empty(tmp_path: Path):
    assert _ADAPTER.detect(tmp_path) is False


# ---------------------------------------------------------------------------
# collect() — DISPATCH role
# ---------------------------------------------------------------------------


def test_gemini_collect_dispatch(tmp_path: Path):
    (tmp_path / "GEMINI.md").write_text("# Global\n", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 1
    assert files[0].role.value == "dispatch"
    assert files[0].adapter == "gemini"


# ---------------------------------------------------------------------------
# collect() — SKILL role (rules dir)
# ---------------------------------------------------------------------------


def test_gemini_collect_rules_as_skill(tmp_path: Path):
    rules_dir = tmp_path / ".gemini" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "style.md").write_text("# Style guide\n", encoding="utf-8")
    (rules_dir / "security.md").write_text("# Security\n", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    roles = [f.role.value for f in files]
    assert roles.count("skill") == 2


def test_gemini_collect_both(tmp_path: Path):
    (tmp_path / "GEMINI.md").write_text("# Dispatch\n", encoding="utf-8")
    rules_dir = tmp_path / ".gemini" / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "api.md").write_text("# API rules\n", encoding="utf-8")
    files = _ADAPTER.collect(tmp_path)
    assert len(files) == 2
    dispatch = [f for f in files if f.role.value == "dispatch"]
    skills = [f for f in files if f.role.value == "skill"]
    assert len(dispatch) == 1
    assert len(skills) == 1


def test_gemini_collect_empty(tmp_path: Path):
    files = _ADAPTER.collect(tmp_path)
    assert files == []
