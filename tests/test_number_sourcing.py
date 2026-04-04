from __future__ import annotations

from pathlib import Path

from agentlint.adapters.copilot import CopilotAdapter
from agentlint.checks.number_sourcing import run
from agentlint.config import Config


_ADAPTER = CopilotAdapter()


def _make_skill(root: Path, content: str) -> Path:
    skill_dir = root / ".github" / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(content, encoding="utf-8")
    dispatch = "| `t` | `.github/skills/test-skill/SKILL.md` | test |\n"
    (root / ".github" / "copilot-instructions.md").write_text(dispatch)
    return root


def test_n01_pass_inline_source(tmp_path: Path):
    content = "The GREEN threshold is ≥ 90%. (Source: constants.py)\n"
    _make_skill(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert [v for v in violations if v.check_id == "AL-N01"] == []


def test_n01_pass_table_with_blockquote_above(tmp_path: Path):
    content = (
        "> **Source of truth:** `constants.py` — MANDATORY_FIELDS.\n"
        "\n"
        "| Field | Weight |\n"
        "|-------|--------|\n"
        "| GPS   | **30%** |\n"
        "| Supplier | **10%** |\n"
    )
    _make_skill(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert [v for v in violations if v.check_id == "AL-N01"] == []


def test_n01_fail_bare_percentage(tmp_path: Path):
    content = "The score must be ≥ 90% to pass.\n"
    _make_skill(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    n01 = [v for v in violations if v.check_id == "AL-N01"]
    assert len(n01) == 1


def test_n01_skip_code_blocks(tmp_path: Path):
    # Percentages inside code fences must be ignored
    content = "```python\nif score < 60%:\n    flag = True\n```\n"
    _make_skill(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert [v for v in violations if v.check_id == "AL-N01"] == []


def test_n01_non_percentage_bare_number_not_flagged(tmp_path: Path):
    # "≥ 20 connections" — no %, not a compliance threshold
    content = "You need PostgreSQL to allow ≥ 20 connections.\n"
    _make_skill(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert [v for v in violations if v.check_id == "AL-N01"] == []


def test_n01_heuristic_annotation_passes(tmp_path: Path):
    content = "95% of bugs are simple mistakes. (heuristic)\n"
    _make_skill(tmp_path, content)
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert [v for v in violations if v.check_id == "AL-N01"] == []
