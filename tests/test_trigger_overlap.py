from __future__ import annotations

from pathlib import Path

from agentlint.adapters.copilot import CopilotAdapter
from agentlint.checks.trigger_overlap import run
from agentlint.config import Config

_ADAPTER = CopilotAdapter()


def _build(root: Path, skills: dict[str, str], dispatch_rows: list[str]) -> None:
    """skills = {folder_name: skill_content}, dispatch_rows = table body rows."""
    skills_dir = root / ".github" / "skills"
    header = (
        "| Skill | File | Trigger |\n"
        "|-------|------|--------|\n"
    )
    rows = "\n".join(dispatch_rows)
    (root / ".github").mkdir(parents=True, exist_ok=True)
    (root / ".github" / "copilot-instructions.md").write_text(
        header + rows + "\n", encoding="utf-8"
    )
    for name, content in skills.items():
        d = skills_dir / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(content, encoding="utf-8")


def test_t01_pass_distinct_triggers(tmp_path: Path):
    _build(
        tmp_path,
        {
            "eudr-standards": "# EUDR",
            "tdd-fastapi": "# TDD",
        },
        [
            "| `eudr` | `.github/skills/eudr-standards/SKILL.md` | Writing validation or GPS scoring code |",
            "| `tdd`  | `.github/skills/tdd-fastapi/SKILL.md`   | Adding any new route or endpoint |",
        ],
    )
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    assert [v for v in violations if v.check_id == "AL-T01"] == []


def test_t01_fail_high_overlap(tmp_path: Path):
    # Both triggers are nearly identical — should flag overlap
    _build(
        tmp_path,
        {
            "skill-a": "# A",
            "skill-b": "# B",
        },
        [
            "| `a` | `.github/skills/skill-a/SKILL.md` | Writing validation scoring code compliance |",
            "| `b` | `.github/skills/skill-b/SKILL.md` | Writing validation scoring code compliance |",
        ],
    )
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, Config(), tmp_path)
    t01 = [v for v in violations if v.check_id == "AL-T01"]
    assert len(t01) >= 1


def test_t01_disabled_via_config(tmp_path: Path):
    _build(
        tmp_path,
        {"a": "# A", "b": "# B"},
        [
            "| `a` | `.github/skills/a/SKILL.md` | Writing validation scoring code compliance |",
            "| `b` | `.github/skills/b/SKILL.md` | Writing validation scoring code compliance |",
        ],
    )
    cfg = Config()
    cfg.checks["trigger-overlap"] = False
    files = _ADAPTER.collect(tmp_path)
    violations = run(files, cfg, tmp_path)
    assert violations == []
